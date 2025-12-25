
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from services.config import config
from services.logger import get_logger
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import traceback

logger = get_logger("gemini")

class GeminiService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiService, cls).__new__(cls)
            cls._instance.available_models = [] # List of model names sorted by priority
            # Do NOT trigger DB access (refresh_best_model) here.
            # It causes crashes if DB is not yet created (e.g. after reset).
            # It will be triggered lazily by _get_model_name() on first use.
        return cls._instance

    def _configure(self):
        api_key = config.get("gemini_api_key")
        if not api_key:
            return False
        genai.configure(api_key=api_key)
        return True

    def _get_model_name(self):
        # Return the best available model, or trigger refresh if empty
        if not self.available_models:
             if self._configure():
                 self.refresh_best_model()
        
        if not self.available_models:
             print("❌ Critical: No Gemini models found via API discovery.")
             return None

        return self.available_models[0]

    def get_flash_model_name(self):
        """
        Returns the best available Flash model from the discovery list.
        """
        if not self.available_models:
             self._get_model_name() # Trigger discovery
             
        # Find first model with 'flash' in name
        for m in self.available_models:
            if 'flash' in m.lower():
                return m
                
        # If no flash found, return best available (e.g. Pro) or None
        if not self.available_models:
            print("❌ Critical: No Gemini models found (Flash search).")
            return None
            
        return self.available_models[0]

    def refresh_best_model(self):
        """
        Discovers all available Gemini models and sorts them by preference.
        """
        if not self._configure():
            return

        try:
            import re
            models = list(genai.list_models())
            # Filter for generateContent support
            candidates = [m.name for m in models if "generateContent" in m.supported_generation_methods]
            
            def model_score(name):
                # Priority: Flash > Pro (for bulk tasks), Version (Newer > Older), Stability (Stable > Exp)
                # But wait, user prefers Pro for Logic? 
                # Actually for general Fallback, we want a robust list.
                # Let's verify 'flash' preference for bulk is handled by get_flash_model_name.
                # Here we just want a good sorted list.
                
                match = re.search(r"gemini-(\d+(?:\.\d+)?)-?([a-z]+)?", name)
                if not match: return (0, 0, 0)
                version = float(match.group(1)) if match.group(1) else 0.0
                
                tier_score = 1
                if "flash" in name: tier_score = 3 # Flash is safest fallback usually
                elif "pro" in name: tier_score = 2
                elif "ultra" in name: tier_score = 1
                
                stability_score = 0
                if "exp" in name or "preview" in name: stability_score = -1
                
                return (version, tier_score, stability_score)

            # Sort best first
            candidates.sort(key=model_score, reverse=True)
            self.available_models = candidates
            
            if candidates:
                logger.info(f"✨ Gemini Models Discovered: {candidates}")
                config.set("gemini_model", candidates[0])
            else:
                 logger.warning("⚠️ No valid Gemini models found.")

        except Exception as e:
            logger.error(f"⚠️ Failed to auto-detect models: {e}")

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
        wait=wait_exponential(multiplier=2, min=2, max=30), # Reduced max wait - switch faster
        stop=stop_after_attempt(3), # Fail faster to trigger rotation
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(f"⚠️ Rate limit. Retrying (Attempt {retry_state.attempt_number})...")
    )
    def _generate_safe(self, model, content, stream=False):
        """
        Safely generates content with exponential backoff.
        """
        return model.generate_content(content, stream=stream)

    def _generate_content_with_fallback(self, primary_model_name, content, stream=False, config=None):
        """
        Tries the primary model, then rotates through ALL available models on Rate Limit.
        """
        import google.generativeai as genai 
        
        def get_model(name):
             if config:
                 return genai.GenerativeModel(name, generation_config=genai.types.GenerationConfig(**config))
             return genai.GenerativeModel(name)
        
        # 1. Try Primary
        try:
            model = get_model(primary_model_name)
            return self._generate_safe(model, content, stream=stream)
        except ResourceExhausted:
            logger.warning(f"⚠️ Rate Limit on {primary_model_name}. Attempting Failover...")
            
            # 2. Rotate through available models
            # We skip the primary one since it just failed
            for fallback_name in self.available_models:
                if fallback_name == primary_model_name:
                    continue
                    
                logger.info(f"🔄 Failover: Trying {fallback_name}...")
                try:
                    fallback_model = get_model(fallback_name)
                    # Try once or twice, don't wait too long on fallback
                    return fallback_model.generate_content(content, stream=stream)
                except ResourceExhausted:
                    logger.warning(f"   Skip {fallback_name} (Rate Limited)")
                    continue
                except Exception as e:
                    logger.error(f"   Skip {fallback_name} (Error: {e})")
                    continue
            
            # If all fail
            logger.error("❌ All Gemini models exhausted.")
            raise

    def analyze_image(self, image_path: str) -> list[str]:
        """
        Generates tags for an image using Gemini.
        Returns a list of strings.
        """
        if not self._configure():
            logger.error("❌ Gemini API Key missing.")
            return []

        try:
            model_name = self._get_model_name()
            # removed direct instantiation here, handled in wrapper
            img = Image.open(image_path)
            
            prompt = "Analyze this image and provide 5-10 relevant tags describing the content, scene, objects, and especially the MOOD (e.g., Joyful, Melancholic) and FACIAL EXPRESSIONS (e.g., Happy, Surprised). For every English tag, also provide its Korean translation. Return ONLY the mixed list of English and Korean tags separated by commas."
            
            # Use wrapper
            response = self._generate_content_with_fallback(model_name, [prompt, img])
            text = response.text.strip()
            
            # Parse commas
            tags = [t.strip() for t in text.split(',')]
            return tags
        except Exception as e:
            logger.error(f"❌ Gemini Tagging Error: {e}")
            return []

    def generate_caption(self, image_path: str, names: list[str] = None, model_name: str = None) -> str:
        """
        Generates a detailed caption using Gemini.
        If names are provided, integrates them.
        """
        if not self._configure():
            return None

        try:
            target_model = model_name or self._get_model_name()
            # No need to instantiate model here, _generate_content_with_fallback does it via get_model helper
            # But wait, Helper logic in _generate_content_with_fallback uses `genai.GenerativeModel(name)`
            
            img = Image.open(image_path)
            
            people_context = ""
            if names:
                people_context = f"The following people are in this photo: {', '.join(names)}. "
            
            prompt = (
                f"{people_context}"
                "Describe this photo in detail. "
                "Include the setting, action, people's expressions, and the overall atmosphere. "
                "If people are identified, mention them naturally. "
                "Write in a warm, narrative style (1-2 sentences). "
                "Also provide a Korean translation of the description on a new line starting with '🇰🇷 '."
            )
            
            response = self._generate_content_with_fallback(target_model, [prompt, img])
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"❌ Gemini Caption Error: {e}")
            return None

    def chat_query(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, model_name: str = None) -> str:
        """
        Handles chat queries using Gemini.
        """
        if not self._configure():
            return "Gemini API Key is missing. Please set GEMINI_API_KEY in .env or configure in Settings."

        try:
            target_model = model_name or self._get_model_name()
            if not target_model:
                logger.error("❌ Chat Query Failed: No target model available.")
                return "AI Model setup failed."

            # Pass generation config for creativity control
            # model = genai.GenerativeModel(...) # Removed direct init
            
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = self._generate_content_with_fallback(target_model, full_prompt, config={"temperature": temperature})
            return response.text.strip()
        except Exception as e:
            logger.error(f"❌ Gemini Chat Error: {traceback.format_exc()}")
            return "Sorry, I encountered an error with the Gemini API."

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(10),
        before_sleep=lambda retry_state: logger.warning(f"⚠️ Embedding Rate Limit. Sleeping {retry_state.next_action.sleep:.1f}s... (Attempt {retry_state.attempt_number})")
    )
    def get_embedding(self, text: str) -> list[float]:
        """
        Generates 768-dim embeddings using models/text-embedding-004.
        Includes automatic retry for Rate Limits (429).
        """
        if not self._configure():
            return []
            
        # text-embedding-004 is current standard
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document",
            title=None
        )
        return result['embedding']

gemini_service = GeminiService()

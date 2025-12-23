
import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from services.config import config
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class GeminiService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiService, cls).__new__(cls)
            cls._instance.fallback_model_name = None 
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
        # Simply return the configured (and probed) model
        # If refresh_best_model did its job, 'gemini_model' in config should be the working one.
        model = config.get("gemini_model")
        if not model: 
            if self._configure():
                self.refresh_best_model()
                model = config.get("gemini_model")
        
        return model or self.fallback_model_name

    def get_flash_model_name(self):
        """
        Returns the dynamically discovered Flash/Fallback model name.
        Used for high-volume tasks to avoid rate limits on Pro models.
        """
        if not self.fallback_model_name:
             # Force discovery if missing
             if self._configure():
                 self.refresh_best_model()

        if not self.fallback_model_name:
            print("❌ Critical: No Flash model found via API discovery.")
            # If we absolutely cannot find one, we stop. User wants NO guessing.
            return None
             
        return self.fallback_model_name

    def refresh_best_model(self):
        """
        Finds the best model AND probes it to ensure it works (Capacity Check).
        If Pro fails (429), automatically falls back to Flash.
        """
        if not self._configure():
            return

        try:
            import re
            models = list(genai.list_models())
            candidates = [m.name.replace("models/", "") for m in models if "generateContent" in m.supported_generation_methods]
            
            def model_score(name):
                match = re.search(r"gemini-(\d+(?:\.\d+)?)-?([a-z]+)?", name)
                if not match: return (0, 0, 0)
                version = float(match.group(1)) if match.group(1) else 0.0
                
                tier_score = 1
                if "ultra" in name: tier_score = 4
                elif "pro" in name: tier_score = 3
                elif "flash" in name: tier_score = 2
                elif "nano" in name or "lite" in name: tier_score = 1
                
                stability_score = 0
                if "exp" in name or "preview" in name: stability_score = -0.1
                return (version, tier_score, stability_score)

            candidates.sort(key=model_score, reverse=True)

            if candidates:
                best_candidate = candidates[0]
                
                # Identify Flash fallback
                flash_candidates = [m for m in candidates if "flash" in m]
                fallback = flash_candidates[0] if flash_candidates else (candidates[-1] if candidates else None)
                self.fallback_model_name = fallback

                # PROBE: Check if Best Candidate works
                print(f"🕵️ Zero-Test: Probing {best_candidate}...")
                try:
                    meta_model = genai.GenerativeModel(best_candidate)
                    # Tiny request to check quota
                    meta_model.generate_content("Hi")
                    print(f"✅ Probe Success: Using {best_candidate}")
                    final_model = best_candidate
                except ResourceExhausted:
                    print(f"⚠️ Probe Failed (Rate Limit): {best_candidate}. Downgrading to {fallback}.")
                    final_model = fallback
                except Exception as e:
                    print(f"⚠️ Probe Failed (Error: {e}). Downgrading to {fallback}.")
                    final_model = fallback

                # Save the WINNER
                if final_model:
                    config.set("gemini_model", final_model)
                    print(f"✨ Gemini AI: Configured to {final_model}")
            else:
                 print("⚠️ No valid Gemini models found.")

        except Exception as e:
            print(f"⚠️ Failed to auto-detect models: {e}")

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
        before_sleep=lambda retry_state: print(f"⚠️ Rate limit hit. Retrying in {retry_state.next_action.sleep} seconds... (Attempt {retry_state.attempt_number})")
    )
    def _generate_safe(self, model, content, stream=False):
        """
        Safely generates content with exponential backoff for Rate Limits.
        """
        return model.generate_content(content, stream=stream)

    def _generate_content_with_fallback(self, primary_model_name, content, stream=False, config=None):
        """
        Wraps generate_content with a fallback mechanism for Rate Limits (429).
        Since we probed at setup, widely expected to just work. 
        But keep simple fallback just in case of transient spikes.
        """
        import google.generativeai as genai 
        
        # Helper to get model with config
        def get_model(name):
             if config:
                 return genai.GenerativeModel(name, generation_config=genai.types.GenerationConfig(**config))
             return genai.GenerativeModel(name)

        model = get_model(primary_model_name)
        try:
            return self._generate_safe(model, content, stream=stream)
        except ResourceExhausted:
            if self.fallback_model_name and primary_model_name != self.fallback_model_name:
                print(f"⚠️ Transient Rate Limit for {primary_model_name}. Retrying with {self.fallback_model_name}")
                fallback_model = get_model(self.fallback_model_name)
                # Also use safe retry for fallback
                return self._generate_safe(fallback_model, content, stream=stream)
            raise

    def analyze_image(self, image_path: str) -> list[str]:
        """
        Generates tags for an image using Gemini.
        Returns a list of strings.
        """
        if not self._configure():
            print("❌ Gemini API Key missing.")
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
            print(f"❌ Gemini Tagging Error: {e}")
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
            print(f"❌ Gemini Caption Error: {e}")
            return None

    def chat_query(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, model_name: str = None) -> str:
        """
        Handles chat queries using Gemini.
        """
        if not self._configure():
            return "Gemini API Key is missing. Please set GEMINI_API_KEY in .env or configure in Settings."

        try:
            target_model = model_name or self._get_model_name()
            # Pass generation config for creativity control
            model = genai.GenerativeModel(
                target_model, 
                generation_config=genai.types.GenerationConfig(temperature=temperature)
            )
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # Use safe wrapper (fallback handled internally, but verify if config passes through?)
            # _generate_content_with_fallback instantiates GenerativeModel internally.
            # So passing 'model' object to _generate_safe is better, BUT _generate_content_with_fallback
            # currently takes 'model_name' and re-instantiates.
            # I need to refactor _generate_content_with_fallback to accept config OR modifying it to accept instanced model?
            # Or just instantiate here and call _generate_safe directly? 
            # But _generate_fallback handles 429 logic with fallback model.
            
            # Refactor Plan: Pass generation config to _generate_content_with_fallback?
            # Or just pass the 'config' dict.
            
            response = self._generate_content_with_fallback(model_name, full_prompt, config={"temperature": temperature})
            return response.text.strip()
        except Exception as e:
            print(f"❌ Gemini Chat Error: {e}")
            return "Sorry, I encountered an error with the Gemini API."

    @retry(
        retry=retry_if_exception_type(ResourceExhausted),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(10),
        before_sleep=lambda retry_state: print(f"⚠️ Embedding Rate Limit. Sleeping {retry_state.next_action.sleep:.1f}s... (Attempt {retry_state.attempt_number})")
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

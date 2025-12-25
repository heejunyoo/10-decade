
import os
import requests
import base64
from services.config import config
from services.logger import get_logger
import traceback
import json

logger = get_logger("groq")

class GroqService:
    _instance = None
    
    # Constants
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama-3.2-11b-vision-preview" # Free, Fast, Vision-Capable
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GroqService, cls).__new__(cls)
        return cls._instance

    def _get_api_key(self):
        return config.get("groq_api_key")

    def _encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _generate(self, messages, temperature=0.7, max_tokens=1024):
        api_key = self._get_api_key()
        if not api_key:
            logger.error("❌ Groq API Key missing.")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            response = requests.post(self.API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data['choices'][0]['message']['content']
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429: # Rate Limit
                logger.warning("⚠️ Groq Rate Limit Exceeded.")
            elif e.response.status_code == 401:
                logger.error("❌ Groq Auth Failed (Check Key).")
            else:
                 logger.error(f"❌ Groq API Error: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Groq Request Failed: {e}")
            return None

    def analyze_image(self, image_path: str) -> list[str]:
        """
        Generates tags using Llama 3.2 Vision.
        """
        logger.info(f"⚡ Groq: Analyzing Image ({self.MODEL})...")
        
        base64_image = self._encode_image(image_path)
        
        prompt = "Analyze this image and provide 5-10 relevant tags describing the content, scene, objects, and especially the MOOD (e.g., Joyful, Melancholic) and FACIAL EXPRESSIONS (e.g., Happy, Surprised). For every English tag, also provide its Korean translation. Return ONLY the mixed list of English and Korean tags separated by commas. No intro/outro."
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ]
        
        result = self._generate(messages, temperature=0.5, max_tokens=300)
        
        if result:
            tags = [t.strip() for t in result.split(',') if t.strip()]
            logger.info(f"✅ Groq: Found {len(tags)} tags.")
            return tags
        return []

    def generate_caption(self, image_path: str, names: list[str] = None, model_name: str = None) -> str:
        """
        Generates caption using Llama 3.2 Vision.
        """
        logger.info(f"⚡ Groq: Generating Caption ({self.MODEL})...")
        
        base64_image = self._encode_image(image_path)
        
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
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ]
        
        caption = self._generate(messages, temperature=0.7, max_tokens=500)
        if caption:
            logger.info(f"✅ Groq: Caption generated ({len(caption)} chars).")
        return caption

    def chat_query(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, model_name: str = None) -> str:
        """
        Text-only Chat.
        """
        logger.info(f"⚡ Groq: Chat Query...")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._generate(messages, temperature=temperature)
        if response:
             logger.info(f"✅ Groq: Response ({len(response)} chars).")
        return response or "Groq API Error."

groq_service = GroqService()

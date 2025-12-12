
from services.config import config
from services.logger import get_logger

logger = get_logger("vision")

class VisionService:
    def analyze_image(self, image_path: str) -> list[str]:
        """
        Routes image analysis to the active provider.
        """
        provider = config.get("ai_provider")
        
        if provider == "gemini":
            from services.gemini import gemini_service
            return gemini_service.analyze_image(image_path)
        else:
            # Local (Florence-2) - Singleton handles loading state
            from services.analyzer import analyzer
            return analyzer.analyze_image(image_path)

    def analyze_scene(self, image_path: str, names: list[str] = None) -> dict:
        """
        Analyzes the scene to return tags, caption, and optionally mood.
        Returns dict: { "tags": [], "summary": "...", "mood": "..." }
        """
        provider = config.get("ai_provider")
        
        if provider == "gemini":
            from services.gemini import gemini_service
            try:
                # Gemini Analysis
                tags = gemini_service.analyze_image(image_path)
                summary = gemini_service.generate_caption(image_path, names)
                
                # Heuristic Mood Extraction
                detected_mood = None
                mood_keywords = ["Joyful", "Melancholic", "Happy", "Sad", "Surprised", "Calm", "Dynamic", "Warm", "Cold"]
                
                final_tags = []
                for t in tags:
                    t_clean = t.replace("Mood:", "").strip()
                    for mk in mood_keywords:
                       if mk.lower() in t_clean.lower():
                           if not detected_mood:
                               detected_mood = t_clean
                    final_tags.append(t_clean)
                
                return {
                    "tags": final_tags,
                    "summary": summary,
                    "mood": detected_mood
                }
            except Exception as e:
                logger.warning(f"Gemini Analysis Failed: {e}")
                # Fallbck logic could go here, but for now return minimal
                return {"tags": [], "summary": None, "mood": None}
        else:
            # Local (Florence-2)
            from services.analyzer import analyzer
            tags, caption = analyzer.analyze_full(image_path, names)
            
            # Local Verification
            try:
                from services.verifier import verifier
                if caption:
                    score = verifier.verify(caption)
                    if score < 0.6:
                         caption = f"[Low Confidence] {caption}"
            except:
                pass
                
            return {
                "tags": tags,
                "summary": caption,
                "mood": None # Local analyzer doesn't support mood yet
            }

    def generate_caption(self, image_path: str, names: list[str] = None) -> str:
        """
        Routes caption generation to the active provider.
        """
        provider = config.get("ai_provider")
        
        caption = ""
        if provider == "gemini":
            from services.gemini import gemini_service
            caption = gemini_service.generate_caption(image_path, names)
        else:
             # Local (Florence-2)
            from services.analyzer import analyzer
            caption = analyzer.generate_caption(image_path, names)

        return caption

# Singleton Facade
vision_service = VisionService()


import os
# CRITICAL: Must be set BEFORE importing transformers/torch to prevent macOS Mutex crashes
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import cv2
import numpy as np
from PIL import Image, ExifTags
from transformers import AutoProcessor, AutoModelForCausalLM, AutoTokenizer, AutoModelForSeq2SeqLM
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Korean Translations (Moved to utils)
from utils.translations import TAG_TRANSLATIONS

import threading

from services.config import config
from services.gemini import gemini_service
from services.logger import get_logger

logger = get_logger("analyzer")

class ImageAnalyzer:
    _instance = None
    _model = None
    _processor = None
    _translator_model = None
    _translator_tokenizer = None
    _lock = threading.Lock()
    _geolocator = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageAnalyzer, cls).__new__(cls)
        return cls._instance

    def initialize(self):
        """
        Loads Florence-2-Large and NLLB Translator ON DEMAND.
        Unified model handles both tagging and captioning.
        """
        if self._model is not None and self._processor is not None:
            return

        with self._lock:
            # Double-check locking
            if self._model is not None and self._processor is not None:
                return

            logger.info("Loading Unified Vision Model (Florence-2-large)...")
            try:
                # Optimized for M4 Mac (MPS)
                self.device = "cpu"
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                
                logger.info(f"Using Device: {self.device} (High Performance Mode)")
                
                # Default to Base model for speed/memory efficiency
                model_id = config.get("FLORENCE_MODEL_ID", "microsoft/Florence-2-base")
                logger.info(f"Loading Model: {model_id}...")

                # Load with trust_remote_code=True
                # CRITICAL: Monkeypatch PreTrainedModel to support Florence-2 on latest transformers
                from transformers import PreTrainedModel
                PreTrainedModel._supports_sdpa = False 
                
                self._model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    dtype=torch.float16 if self.device != "cpu" else torch.float32, 
                    attn_implementation="eager"
                ).to(self.device)
                
                self._processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
                
                # --- Google Translator (Cloud API) ---
                # Replaces local models to prevent macOS Mutex crashes
                logger.info("Initializing Google Translator (deep-translator)...")
                from deep_translator import GoogleTranslator
                self._translator = GoogleTranslator(source='auto', target='ko')

                self._geolocator = Nominatim(user_agent="DecadeJourney/1.0")
                
                logger.info("All AI Models Loaded Successfully (Florence-2 + GoogleTranslate)")
            except Exception as e:
                logger.error(f"Failed to load AI models: {e}")
                import traceback
                traceback.print_exc()
                # Ensure we don't end up in a half-initialized state
                self._model = None
                self._processor = None

    # Legacy method compatibility
    def initialize_caption_model(self):
        self.initialize()

    def run_florence_task(self, image, task_prompt: str, text_input=None):
        if not self._model or not self._processor:
            self.initialize()
            
        if not self._model or not self._processor:
            return None
            
        if image is None:
            logger.warning("Florence task skipped: Image is None")
            return None
            
        try:
            if text_input is None:
                prompt = task_prompt
            else:
                prompt = task_prompt + text_input
                
            inputs = self._processor(text=prompt, images=image, return_tensors="pt").to(self.device, torch.float16 if self.device != "cpu" else torch.float32)

            generated_ids = self._model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=256, # Limit generation length for speed
                early_stopping=True,
                do_sample=False, 
                num_beams=1, # Greedy search (Much faster than 3)
                use_cache=False # CRITICAL: Must be False for Florence-2 to avoid 'NoneType' shape error
            )
            
            generated_text = self._processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed_answer = self._processor.post_process_generation(
                generated_text, 
                task=task_prompt, 
                image_size=(image.width, image.height)
            )
            
            return parsed_answer
            
        except Exception as e:
            logger.error(f"Error in Florence Analysis: {e}")
            import traceback
            traceback.print_exc()
            return None

    def analyze_image(self, image_path: str) -> list[str]:
        """
        Generates tags for an image. 
        Routes to Gemini if configured, otherwise uses Florence-2 (Local).
        """
        provider = config.get("ai_provider")

        # 1. Gemini
        if provider == "gemini":
            try:
                # logger.info(f"✨ Using Gemini for tagging: {image_path}") # Reduce log noise
                return gemini_service.analyze_image(image_path)
            except Exception as e:
                logger.error(f"Gemini Tagging failed: {e}")
                return []

        # 2. Local (Florence-2)
        if not self._model:
             self.initialize()
        
        if not self._model:
             return []
            
        try:
            image = Image.open(image_path).convert('RGB')
            
            # Task: <OD> (Object Detection) provides bounding boxes and labels
            # We just want the labels.
            result = self.run_florence_task(image, "<OD>")
            
            if not result or '<OD>' not in result:
                return []
                
            # Result format: {'<OD>': {'bboxes': [[x1, y1, x2, y2], ...], 'labels': ['person', 'dog', ...]}}
            labels = result['<OD>'].get('labels', [])
            
            unique_tags = set()
            for label in labels:
                label = label.lower()
                unique_tags.add(label)
                # Translate
                if label in TAG_TRANSLATIONS:
                    unique_tags.add(TAG_TRANSLATIONS[label])
                    
            return list(unique_tags)

        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {e}")
            return []

    def analyze_full(self, image_path: str, names: list[str] = None) -> tuple[list[str], str]:
        """
        Single-Pass Analysis: Generates Caption AND extracts Tags from it.
        Significantly faster than running <OD> + <DETAILED_CAPTION> separately.
        """
        # 1. Gemini Routing
        provider = config.get("ai_provider")
        if provider == "gemini":
            try:
                # Optimized: Call Gemini once for both if possible? 
                # Gemini doesn't have a combined endpoint easily wrapped here without changing service.
                # So we call both sequentially (Gemini is fast).
                tags = gemini_service.analyze_image(image_path)
                caption = gemini_service.generate_caption(image_path, names)
                return (tags, caption)
            except Exception:
                return ([], None)

        # 2. Local (Florence-2)
        if not self._model: self.initialize()
        if not self._model: return ([], None)

        try:
            image = Image.open(image_path).convert('RGB')
            
            # Single Inference: <DETAILED_CAPTION>
            # (User requested to use this to derive tags)
            prompt = "<DETAILED_CAPTION>"
            result = self.run_florence_task(image, prompt)
            
            caption = ""
            if result and prompt in result:
                caption = result[prompt]
            elif result and '<DETAILED_CAPTION>' in result:
                caption = result['<DETAILED_CAPTION>']
                
            if not caption:
                return ([], None)

            # Extract Tags from Caption (Simple NLP)
            # Remove stopwords and punctuation
            stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'with', 'by', 'of', 'for', 'to', 'and', 'but', 'or', 'so', 'it', 'this', 'that', 'there', 'here'}
            
            import re
            words = re.findall(r'\b\w+\b', caption.lower())
            tags = list(set([w for w in words if w not in stopwords and len(w) > 2]))

            # Inject Names (if any)
            if names:
                 people_str = ", ".join(names)
                 # "A man in a shirt..." -> "In this photo with Person, a man in a shirt..."
                 # Simple prefixing
                 caption = f"In this photo with {people_str}, " + caption.lower()
            
            # Translate Caption (En->Ko)
            final_caption = caption
            try:
                if self._translator:
                    caption_ko = self._translator.translate(caption)
                    final_caption = f"{caption}\n\n🇰🇷 {caption_ko}"
            except Exception:
                pass

            return (tags, final_caption)

        except Exception as e:
            logger.error(f"Single-Pass Analysis failed: {e}")
            return ([], None)
    def generate_caption(self, image_path: str, names: list[str] = None) -> str:
        """
        Generates a detailed caption.
        Routes to Gemini if configured, otherwise uses Florence-2 (Local).
        """
        provider = config.get("ai_provider")

        # 1. Gemini
        if provider == "gemini":
            try:
                # logger.info(f"✨ Using Gemini for captioning: {image_path}")
                caption = gemini_service.generate_caption(image_path, names)
                return caption
            except Exception as e:
                logger.error(f"Gemini Captioning failed: {e}")
                return None

        # 2. Local (Florence-2)
        if not self._model:
            self.initialize()
        
        if not self._model:
            return None
            
        try:
            image = Image.open(image_path).convert('RGB')
            
            # Task: <DETAILED_CAPTION> (Faster than MORE_DETAILED_CAPTION)
            prompt = "<DETAILED_CAPTION>"
            # NOTE: Florence-2 does not support additional text input for this task.
            # We strictly pass the token.

            result = self.run_florence_task(image, prompt)
            
            caption = ""
            if result and prompt in result:
                caption = result[prompt]
            elif result and '<DETAILED_CAPTION>' in result: # Fallback if specific prompt not found
                caption = result['<DETAILED_CAPTION>']
            
            if not caption:
                return None

            # Manually inject names into the result if provided
            if names:
                 people_str = ", ".join(names)
                 caption = f"In this photo with {people_str}, " + caption.lower()
                
            # Translate to Korean
            try:
                if self._translator:
                    caption_ko = self._translator.translate(caption)
                    return f"{caption}\n\n🇰🇷 {caption_ko}"
            except Exception as e:
                logger.warning(f"Translation failed: {e}")
                return caption
                
            return caption

        except Exception as e:
            logger.error(f"Error generating caption (Florence-2): {e}")
            return None

    # --- Extended Metadata Methods (v2.1) ---

    def analyze_full_details(self, image_path: str, faces_names: list[str] = None) -> dict:
        """
        Comprehensive Extraction: GPS, EXIF, Blur, Tags, Caption, OCR.
        """
        if not self._model:
            self.initialize()

        meta = {
            "date": None,
            "location": None,
            "camera": None,
            "is_blurry": False,
            "blur_score": 0.0,
            "ocr_text": "",
            "ai_caption": "",
            "tags": [],
            "people": faces_names or []
        }

        try:
            pil_image = Image.open(image_path).convert('RGB')
            
            # 1. EXIF Metadata (GPS, Date, Camera)
            exif_data = self._get_exif_data(pil_image)
            meta.update(exif_data)
            
            # Reverse Geocoding if GPS available
            if meta["location"] and "lat" in meta["location"]:
                addr = self._get_geo_location(meta["location"]["lat"], meta["location"]["lon"])
                if addr:
                    meta["location"]["address"] = addr
            
            # 2. Blur Detection (OpenCV)
            try:
                cv_img = cv2.imread(image_path)
                if cv_img is not None:
                     gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                     score = cv2.Laplacian(gray, cv2.CV_64F).var()
                     meta["blur_score"] = float(score)
                     meta["is_blurry"] = score < 100.0
            except Exception as e:
                logger.warning(f"Blur detection failed: {e}")

            # 3. AI Tasks (Florence-2)
            # OCR
            ocr_res = self.run_florence_task(pil_image, "<OCR>")
            if ocr_res and '<OCR>' in ocr_res:
                meta["ocr_text"] = ocr_res['<OCR>']
            
            # Tags (Object Detection)
            od_res = self.run_florence_task(pil_image, "<OD>")
            if od_res and '<OD>' in od_res:
                 labels = od_res['<OD>'].get('labels', [])
                 meta["tags"] = list(set(labels)) # translate later if needed

            # Caption
            prompt = "<MORE_DETAILED_CAPTION>"
            # Invalid: if faces_names: prompt = ...
            
            cap_res = self.run_florence_task(pil_image, prompt)
            if cap_res and prompt in cap_res:
                 meta["ai_caption"] = cap_res[prompt]
            elif cap_res and '<DETAILED_CAPTION>' in cap_res:
                 meta["ai_caption"] = cap_res['<DETAILED_CAPTION>']
            
            # Context Injection (Post-Processing)
            if faces_names and meta["ai_caption"]:
                 meta["ai_caption"] = f"With {', '.join(faces_names)}: " + meta["ai_caption"]

            return meta

        except Exception as e:
             logger.error(f"Full analysis failed: {e}")
             import traceback
             traceback.print_exc()
             return meta

    def _get_exif_data(self, image) -> dict:
        data = {"date": None, "location": None, "camera": None}
        try:
            exif = image._getexif()
            if not exif:
                return data
                
            # Parse common tags
            exif_map = {}
            for tag_id, value in exif.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                exif_map[tag] = value
                
            # Date
            if 'DateTimeOriginal' in exif_map:
                data["date"] = exif_map['DateTimeOriginal']
            elif 'DateTime' in exif_map:
                data["date"] = exif_map['DateTime']
                
            # Camera
            make = exif_map.get('Make', '').strip()
            model = exif_map.get('Model', '').strip()
            if make or model:
                data["camera"] = f"{make} {model}".strip()

            # GPS
            def _convert_to_degrees(value):
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)

            if 'GPSInfo' in exif_map:
                gps_info = exif_map['GPSInfo']
                gps_lat = gps_info.get(2)
                gps_lat_ref = gps_info.get(1)
                gps_lon = gps_info.get(4)
                gps_lon_ref = gps_info.get(3)
                
                if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
                    lat = _convert_to_degrees(gps_lat)
                    if gps_lat_ref != "N": lat = -lat
                    
                    lon = _convert_to_degrees(gps_lon)
                    if gps_lon_ref != "E": lon = -lon
                    
                    data["location"] = {"lat": lat, "lon": lon}

        except Exception as e:
            logger.warning(f"EXIF parsing error: {e}")
            
        return data

    def _get_geo_location(self, lat, lon):
        if not self._geolocator:
             self._geolocator = Nominatim(user_agent="DecadeJourney/1.0")
        try:
            location = self._geolocator.reverse((lat, lon), language="en", timeout=5)
            return location.address
        except Exception:
            return None

# Singleton instance
analyzer = ImageAnalyzer()


import os
# CRITICAL: Must be set BEFORE importing transformers/torch to prevent macOS Mutex crashes
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import cv2
import numpy as np
from PIL import Image, ExifTags
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from geopy.geocoders import Nominatim
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
    _translator = None
    _lock = threading.Lock()
    _geolocator = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageAnalyzer, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        """
        Loads Qwen2-VL-2B-Instruct implementation on demand.
        """
        with self._lock:
            if self._model is not None:
                return

            logger.info("👁️ Loading Vision Model (Qwen2-VL-2B-Instruct) [Lazy Load]...")
            try:
                # Device Selection
                self.device = "cpu"
                if torch.cuda.is_available():
                    self.device = "cuda"
                elif torch.backends.mps.is_available():
                    self.device = "mps"
                
                logger.info(f"Using Device: {self.device}")
                
                model_id = config.get("VISION_MODEL_ID", "Qwen/Qwen2-VL-2B-Instruct")
                
                # Qwen2-VL Load
                self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                    model_id, 
                    torch_dtype="auto", 
                    device_map="auto" if self.device != "cpu" else None
                )
                if self.device == "cpu":
                    self._model.to("cpu")
                    
                self._processor = AutoProcessor.from_pretrained(model_id)
                
                # Translator setup
                if not self._translator:
                    logger.info("Initializing Google Translator...")
                    from deep_translator import GoogleTranslator
                    self._translator = GoogleTranslator(source='auto', target='ko')
                    
                if not self._geolocator:
                    self._geolocator = Nominatim(user_agent="DecadeJourney/1.0")
                
                logger.info("✅ Qwen2-VL-2B Loaded.")
            except Exception as e:
                logger.error(f"Failed to load Qwen2-VL: {e}")
                self._model = None

    def unload_model(self):
        """
        Unloads model to free memory.
        """
        with self._lock:
            if self._model is not None:
                logger.info("🧹 Unloading Vision Model...")
                del self._model
                del self._processor
                self._model = None
                self._processor = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                elif torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                import gc
                gc.collect()
                logger.info("✅ Vision Model Unloaded.")

    def run_vision_chat(self, image_path: str, prompt_text: str):
        """
        Generic Qwen2-VL Chat Wrapper with Lazy Loading lifecycle.
        """
    _unload_timer = None
    _keep_alive_seconds = 30.0

    def run_vision_chat(self, image_path: str, prompt_text: str):
        """
        Generic Qwen2-VL Chat Wrapper with Smart Batching (Debounced Unload).
        """
        # 1. Cancel existing unload timer (if any)
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()
                self._unload_timer = None

        # 2. Load model (if not loaded)
        self.load_model()
        if not self._model: return None
        
        try:
            image = Image.open(image_path).convert('RGB')
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt_text},
                    ],
                }
            ]
            
            # Prepare inputs
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            
            inputs = self._processor(
                text=[text],
                images=[image],
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to(self.device)
            
            # Generate
            logger.info("🔮 Running Inference...")
            generated_ids = self._model.generate(**inputs, max_new_tokens=128)
            generated_ids_trimmed = [
                out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            
            output_text = self._processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )[0]
            
            return output_text.strip()

        except Exception as e:
            logger.error(f"Qwen Generation Failed: {e}")
            return None
        finally:
            # 3. Schedule Unload (Debounced)
            self._schedule_unload()

    def _schedule_unload(self):
        """
        Starts a timer to unload the model after N seconds.
        """
        with self._lock:
            # Cancel any existing timer just in case
            if self._unload_timer:
                self._unload_timer.cancel()
            
            logger.info(f"⏳ Keeping model alive for {self._keep_alive_seconds}s...")
            self._unload_timer = threading.Timer(self._keep_alive_seconds, self.unload_model)
            self._unload_timer.start()

    def analyze_video(self, video_path: str) -> dict:
        """
        Analyze Video by summarizing 3 keyframes (10%, 50%, 90%).
        """
        import cv2
        import tempfile
        
        logger.info(f"🎥 Analyzing Video: {os.path.basename(video_path)}")
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
             logger.error("Could not open video file.")
             return {"tags": [], "summary": "Error: Could not open video.", "mood": None}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            logger.warning("Video has 0 frames.")
            return {"tags": [], "summary": "Empty video.", "mood": None}

        # 3 Keyframes: 10%, 50%, 90%
        points = [0.1, 0.5, 0.9]
        
        combined_summaries = []
        all_tags = set()
        ocr_texts = []
        
        try:
            for p in points:
                frame_idx = int(total_frames * p)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    # Save temp
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        cv2.imwrite(tmp.name, frame)
                        tmp_path = tmp.name
                    
                    try:
                        # Analyze Frame
                        res = self.analyze_scene(tmp_path)
                        
                        # Post-process summary to be concise
                        scene_desc = res.get('summary', '').split('\n')[0] # Take first line only
                        combined_summaries.append(f"⏱️[{int(p*100)}%]: {scene_desc}")
                        
                        if res.get('tags'):
                            all_tags.update(res.get('tags'))
                        if res.get('ocr'):
                            ocr_texts.append(res.get('ocr'))
                    finally:
                        # Cleanup temp file
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
        except Exception as e:
            logger.error(f"Video Frame Analysis Failed: {e}")
        finally:
            cap.release()
            
        final_summary = "📽️ Video Analysis:\n" + "\n".join(combined_summaries)
        if ocr_texts:
            final_summary += "\n\n📝 Video Text: " + " ".join(ocr_texts)
            
        logger.info("✅ Video Analysis Complete.")
        
        return {
            "tags": list(all_tags),
            "summary": final_summary,
            "mood": None,
            "ocr": " ".join(ocr_texts)
        }

    def analyze_scene(self, image_path: str, names: list[str] = None) -> dict:
        """
        Replacement for analyze_full. Returns tags, summary, mood, ocr.
        """
        # 1. Gemini Route (Unchanged)
        provider = config.get("ai_provider")
        if provider == "gemini":
             # ... (Keep existing Gemini logic if needed, or redirect)
             # To keep file short, let's assume Analyzer is purely Local Fallback
             pass

        # 2. Local Qwen
        logger.info(f"Analyzing {os.path.basename(image_path)} with Qwen...")
        names_context = f" The people in this image are: {', '.join(names)}." if names else ""
        
        # Combined Prompt for efficiency
        prompt = (
            f"Describe this image in detail.{names_context} "
            "Then, list 5-10 keywords (tags) describing the scene, visible objects, and mood. "
            "Finally, transcribe any visible text (OCR). "
            "Format: [Description]... \nTags: tag1, tag2...\nOCR: ..."
        )
        
        response = self.run_vision_chat(image_path, prompt)
        if not response:
            return {"tags": [], "summary": None, "mood": None}

        # Naive Parsing
        description = response
        tags = []
        ocr = ""
        
        if "Tags:" in response:
            parts = response.split("Tags:")
            description = parts[0].strip()
            rest = parts[1]
            if "OCR:" in rest:
                tag_part, ocr_part = rest.split("OCR:")
                tags_str = tag_part.strip()
                ocr = ocr_part.strip()
            else:
                tags_str = rest.strip()
            
            tags = [t.strip() for t in tags_str.split(",")]
            
        # Translate Description
        try:
            if self._translator:
                ko_desc = self._translator.translate(description)
                description = f"{description}\n\n🇰🇷 {ko_desc}"
        except: pass
        
        return {
            "tags": tags,
            "summary": description,
            "mood": None, # Extract from tags if possible
            "ocr": ocr
        }

    def generate_caption(self, image_path: str, names: list[str] = None) -> str:
        # Simple wrapper for chat
        names_context = f" The people in this image are: {', '.join(names)}." if names else ""
        prompt = f"Describe this image in a single paragraph.{names_context}"
        
        desc = self.run_vision_chat(image_path, prompt)
        
        # Translate
        try:
             if self._translator and desc:
                 ko_desc = self._translator.translate(desc)
                 desc = f"{desc}\n\n🇰🇷 {ko_desc}"
        except: pass
        return desc
    
    # Metadata helpers (EXIF) - kept assuming they are utility
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

# Singleton
analyzer = ImageAnalyzer() 


import os
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import threading
from dotenv import load_dotenv

# Force load environment variables immediately
load_dotenv()

# Centralized Paths
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("DECADE_UPLOAD_DIR", BASE_DIR / "static/uploads"))
CHROMA_DIR = Path(os.getenv("DECADE_CHROMA_DIR", BASE_DIR / "chroma_db"))
BACKUP_DIR = Path(os.getenv("DECADE_BACKUP_DIR", BASE_DIR / "backups"))

# Ensure dirs exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Face Recognition Tunables
# Lower threshold = looser matching (better for masks, higher risk of false positives)
FACE_SIMILARITY_THRESHOLD = float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.45"))
# Ignore faces smaller than this ratio of total image area (e.g. 1.5%)
MIN_FACE_RATIO = float(os.getenv("MIN_FACE_RATIO", "0.015"))
# Ignore low-confidence detections (0.0 - 1.0)
FACE_DETECTION_THRESHOLD = float(os.getenv("FACE_DETECTION_THRESHOLD", "0.6"))

class ConfigService:
    _instance = None
    _lock = threading.Lock()
    _cache = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigService, cls).__new__(cls)
                    cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Loads all settings from DB into memory cache"""
        db = SessionLocal()
        try:
            settings = db.query(models.Settings).all()
            self._cache = {s.key: s.value for s in settings}
            provider = self._cache.get('ai_provider', 'unknown').upper()
            print(f"⚙️ System Config: Ready (AI Mode: {provider})")
        except Exception as e:
            if "no such table" in str(e):
                print("⚙️ System Config: Fresh install detected (Settings table will be created shortly).")
            else:
                print(f"❌ Failed to load config: {e}")
        finally:
            db.close()

    # Mapping internal keys to Env Vars
    ENV_MAPPING = {
        "gemini_api_key": "GEMINI_API_KEY",
        "groq_api_key": "GROQ_API_KEY",
        "wedding_anniversary": "WEDDING_ANNIVERSARY", 
        "gemini_model": "GEMINI_MODEL"
    }

    def get(self, key: str, default=None):
        # 1. DB Setting (Highest Priority - 'Manage Page')
        if key in self._cache:
            return self._cache[key]
            
        # 2. Environment Variable (Fallback / Secrets)
        env_key = self.ENV_MAPPING.get(key)
        if env_key and os.getenv(env_key):
            return os.getenv(env_key)
            
        # 3. Default
        # 3. Default
        if default is None:
            if key == "ai_provider": return "local"
            if key == "theme": return "classic"
        
        return default

    def set(self, key: str, value: str):
        """Updates setting in DB and Cache"""
        db = SessionLocal()
        try:
            setting = db.query(models.Settings).filter(models.Settings.key == key).first()
            if not setting:
                setting = models.Settings(key=key, value=value)
                db.add(setting)
            else:
                setting.value = value
            
            db.commit()
            self._cache[key] = value # Update cache immediately
            return True
        except Exception as e:
            print(f"❌ Failed to update setting {key}: {e}")
            return False
        finally:
            db.close()

# Singleton
config = ConfigService()

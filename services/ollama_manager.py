import subprocess
import time
import requests
import socket
from services.logger import get_logger

logger = get_logger("ollama_manager")

from services.config import config

class OllamaManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OllamaManager, cls).__new__(cls)
            # Startup Check
            cwd_provider = config.get("ai_provider")
            if cwd_provider == "local" or cwd_provider == "ollama":
                is_up = cls._instance.is_running()
                status = "Ready" if is_up else "Offline (Auto-start enabled)"
                icon = "✅" if is_up else "⚠️"
                print(f"{icon} Ollama: {status}")
            else:
                # Standby, silent or faint?
                pass
        return cls._instance

    def is_running(self):
        """Check if Ollama is responsive on port 11434"""
        try:
            # Quick socket check first
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', 11434))
                if result != 0:
                    return False
            
            # API Health check
            resp = requests.get("http://localhost:11434", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def ensure_running(self):
        """
        Checks if Ollama is running, and starts it if not.
        Returns True if successful, False otherwise.
        """
        if self.is_running():
            return True

        logger.info("🤖 Ollama is not running. Attempting auto-start...")
        
        try:
            # Spawn in background, detached from current process group so it survives restart
            # Using subprocess.Popen
            # We assume 'ollama' is in PATH (we verified this earlier: /opt/homebrew/bin/ollama)
            subprocess.Popen(
                ["ollama", "serve"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Wait loop (up to 10 seconds)
            logger.info("⏳ Waiting for Ollama to initialize...")
            for _ in range(20):
                time.sleep(0.5)
                if self.is_running():
                    logger.info("✅ Ollama Auto-Started successfully!")
                    return True
            
            logger.error("❌ Ollama failed to start within timeout.")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to spawn Ollama: {e}")
            return False

    def get_best_model(self):
        """
        Returns the best available model.
        Priority: llama3.1:8b > llama3.2:3b > any other llama
        """
        if not self.is_running():
            return "llama3.2:3b" # Fallback default
            
        try:
            # Check what's installed
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            output = result.stdout.lower()
            
            if "llama3.1:8b" in output:
                return "llama3.1:8b"
            elif "gemma2:9b" in output:
                return "gemma2:9b"
            elif "llama3.2:3b" in output:
                return "llama3.2:3b"
            else:
                return "llama3.2:3b" # Default fallback
        except Exception:
            return "llama3.2:3b"

    def ensure_model(self, model_name=None):
        """
        Ensures the specified model is pulled and available.
        If no name provided, ensures the best model.
        """
        if not model_name:
            model_name = self.get_best_model()

        if not self.is_running():
            return False
            
        try:
            # Simple check via 'ollama list' or just try pulling (it skips if present)
            # We use subprocess to pull in background or foreground? Foreground is safer for first run.
            logger.info(f"Checking if model '{model_name}' is available...")
            subprocess.run(["ollama", "pull", model_name], check=True)
            logger.info(f"✅ Model '{model_name}' is ready.")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False

ollama_manager = OllamaManager()

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

ollama_manager = OllamaManager()

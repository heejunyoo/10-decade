
from services.analyzer import analyzer
import sys

def preload():
    print("🚀 Preloading AI Models...")
    try:
        # This triggers download and loading of Florence-2 and NLLB
        analyzer.initialize()
        print("✅ Models (Florence-2 + NLLB) downloaded and cached successfully.")
    except Exception as e:
        print(f"❌ Error preloading models: {e}")
        sys.exit(1)

if __name__ == "__main__":
    preload()

import sys
import os
import time
from PIL import Image
from unittest.mock import patch

# Setup paths
sys.path.append(os.getcwd())

from services.analyzer import analyzer
from services.config import config

def verify_local_pipeline():
    print("🚀 Starting Local AI Pipeline Verification...")
    
    # 1. Setup Dummy Image
    img_path = "static/uploads/test_local_ai.jpg"
    if not os.path.exists("static/uploads"):
        os.makedirs("static/uploads")
        
    img = Image.new('RGB', (640, 480), color = 'blue')
    img.save(img_path)
    print(f"✅ Created dummy image: {img_path}")

    try:
        # 2. Force Local Mode
        print("2. Forcing 'AI_PROVIDER = local'...")
        # We patch config.get to emulate local mode even if DB says otherwise
        original_get = config.get
        
        def mock_get(key, default=None):
            if key == "ai_provider":
                return "local"
            return original_get(key, default)
            
        with patch.object(config, 'get', side_effect=mock_get):
            
            # 3. Initialize Model
            print("3. loading Florence-2 Model (This may take a moment)...")
            start_time = time.time()
            analyzer.initialize()
            print(f"✅ Model Loaded in {time.time() - start_time:.2f}s")
            
            # 4. Run Analysis
            print("4. Running analyze_full (Single Pass)...")
            tags, caption = analyzer.analyze_full(img_path)
            
            print(f"✅ Analysis Result:")
            print(f"   - Tags: {tags}")
            print(f"   - Caption: {caption}")
            
            if caption is None:
                print("❌ Verification Failed: Caption is None")
            else:
                print("✅ Verification Success: Local AI produced output.")

    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if os.path.exists(img_path):
            os.remove(img_path)

if __name__ == "__main__":
    verify_local_pipeline()

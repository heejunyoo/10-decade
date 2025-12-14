import sys
import os

sys.path.append(os.getcwd())

try:
    print("Attempting to import services.media...")
    import services.media
    print("✅ Import successful!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

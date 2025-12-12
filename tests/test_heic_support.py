
from PIL import Image
import pillow_heif
import os

def test_heic():
    # 1. Check Registration
    pillow_heif.register_heif_opener()
    print("✅ Registered HEIF opener")

    # 2. Create Dummy Iamge
    img = Image.new('RGB', (100, 100), color = 'red')
    
    # 3. Try to save as HEIC
    heic_path = "test_image.heic"
    try:
        img.save(heic_path, format="HEIF")
        print("✅ Saved HEIC image")
    except Exception as e:
        print(f"❌ Failed to save HEIC (Writer not supported?): {e}")
        return

    # 4. Try to open HEIC
    try:
        reopened = Image.open(heic_path)
        reopened.verify()
        print("✅ Successfully opened HEIC image")
        print(f"   Format: {reopened.format}, Size: {reopened.size}")
    except Exception as e:
        print(f"❌ Failed to open HEIC: {e}")
    finally:
        if os.path.exists(heic_path):
            os.remove(heic_path)
        
if __name__ == "__main__":
    test_heic()

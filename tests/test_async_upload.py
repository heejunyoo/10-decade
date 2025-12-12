
import os
import sys
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.media import process_upload_task
from database import SessionLocal
import models
from PIL import Image
import shutil

def test_async_processing():
    print("🧪 Starting Async Processing Test...")
    
    # 1. Setup
    temp_dir = "static/temp"
    upload_dir = "static/uploads"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Create a dummy image
    test_filename = "test_async_image.jpg"
    temp_path = os.path.join(temp_dir, test_filename)
    
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(temp_path)
    
    # Metadata
    metadata = {
        "title": "Async Test Title",
        "description": "Async Test Description",
        "tags": "test,async",
        "date": "2025-01-01"
    }
    
    # 2. Run Processing
    print(f"  Processing {temp_path}...")
    try:
        process_upload_task(temp_path, test_filename, metadata)
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        return

    # 3. Verify
    # Check DB
    db = SessionLocal()
    event = db.query(models.TimelineEvent).filter(models.TimelineEvent.title == "Async Test Title").first()
    
    if event:
        print(f"✅ DB Event Created: ID {event.id}")
        print(f"   Image URL: {event.image_url}")
        
        # Check File
        local_path = event.image_url.lstrip("/") # Remove leading /
        if os.path.exists(local_path):
            print(f"✅ File exists at {local_path}")
        else:
            print(f"❌ File missing at {local_path}")
            
        # Cleanup
        db.delete(event)
        db.commit()
        if os.path.exists(local_path):
            os.remove(local_path)
        print("🧹 Cleanup complete")
        
    else:
        print("❌ DB Event not found")
    
    db.close()

if __name__ == "__main__":
    test_async_processing()

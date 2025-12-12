import sys
import os
import time
from pathlib import Path
from PIL import Image
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine
import models
from services.tasks import process_ai_for_event
from services.grouping import grouping_service

def create_dummy_image(path):
    img = Image.new('RGB', (100, 100), color = 'red')
    img.save(path)

def verify():
    print("🚀 Starting Pipeline Verification...")
    
    # 1. Setup Data
    db = SessionLocal()
    upload_path = "static/uploads/test_dummy.jpg"
    create_dummy_image(upload_path)
    
    try:
        # Create Event
        print("1. Creating Dummy Event...")
        event = models.TimelineEvent(
            date="2025-01-01",
            image_url="/static/uploads/test_dummy.jpg",
            media_type="photo",
            capture_time=None # Will be None, might skip grouping time-check? 
                              # Grouping checks 'capture_time'. 
                              # Need to mock capture_time or let logic handle it.
        )
        # Manually set capture_time equivalent to 'date' for test
        from datetime import datetime
        event.capture_time = datetime.strptime("2025-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")
        
        db.add(event)
        db.commit()
        db.refresh(event)
        print(f"✅ Event Created: ID {event.id}")

        # 2. Run AI Process (Tags, Caption, Embedding, Grouping)
        print("2. Running AI Task (Sync)...")
        # Ensure ChromaDB is ready? (Auto initialized)
        
        # We call the task function directly (synchronously)
        process_ai_for_event(event.id)
        print("✅ AI Task Completed.")
        
        # 3. Verify Grouping Logic
        print("3. Checking Grouping Result...")
        db.refresh(event)
        
        # It should have blur score
        print(f"   Blur Score: {event.blur_score}")
        if event.blur_score is None:
            print("❌ Blur score missing!")
        else:
            print("✅ Blur score present.")
            
        # Grouping might not happen with 1 photo, but it shouldn't crash.
        # Check Stack ID
        print(f"   Stack ID: {event.stack_id}")
        
        # Check Vector Store
        from services.rag import memory_vector_store
        embeddings = memory_vector_store.get_embeddings([str(event.id)])
        if not embeddings or str(event.id) not in embeddings:
             print("❌ Embedding missing in Vector Store!")
        else:
             print(f"✅ Embedding found (Length: {len(embeddings[str(event.id)])})")

        print("\n🎉 Verification Success! No crashes detected.")
        
    except Exception as e:
        print(f"\n❌ Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        db.query(models.TimelineEvent).filter(models.TimelineEvent.image_url == "/static/uploads/test_dummy.jpg").delete()
        db.commit()
        db.close()
        if os.path.exists(upload_path):
            os.remove(upload_path)

if __name__ == "__main__":
    verify()

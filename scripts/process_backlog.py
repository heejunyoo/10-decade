
import os
import sys
import time
import threading

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force AI Environment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

from database import get_db
import models
from services import tasks
from services import logger

# Setup logging
logger.setup_logging()
log = logger.get_logger("backlog")

def process_backlog():
    print("🚀 Starting AI Backlog Processor...")
    
    # 1. Start Worker inside this script process
    # This ensures we have a consumer for the queue
    tasks.start_worker()
    print("⚙️  Worker thread started.")

    db = next(get_db())
    try:
        # 2. Find Incomplete Events
        # Criteria: Photo, Missing Summary OR Missing Tags
        from sqlalchemy import or_
        
        events = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            or_(
                models.TimelineEvent.summary == None, 
                models.TimelineEvent.summary == "",
                models.TimelineEvent.tags == None
            ),
            models.TimelineEvent.image_url != None
        ).all()
        
        if not events:
            print("✅ No pending AI tasks found. Everything is up to date!")
            return

        print(f"📋 Found {len(events)} events waiting for AI Code analysis.")
        
        for event in events:
            file_path = event.image_url.lstrip("/")
            full_path = os.path.join(os.getcwd(), "static/uploads", os.path.basename(file_path))
            
            if os.path.exists(full_path):
                print(f"   -> Queuing Event {event.id} ({os.path.basename(file_path)})")
                tasks.enqueue_event(event.id)
            else:
                print(f"   ⚠️ File missing for Event {event.id}: {full_path}")
        
        print("\n⏳  Processing... (This may take a while depending on model speed)")
        print("    Please wait until this script finishes.")
        
        # 3. Wait for Queue to Empty
        # tasks.analysis_queue matches the one in the imported module
        tasks.analysis_queue.join()
        
        print("✅ All tasks completed successfully!")

    except Exception as e:
        print(f"❌ Error processing backlog: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    process_backlog()


import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models
from services.rag import memory_vector_store
from services.config import config

def reindex_safely():
    print("🧠 Starting Safe Dual-Indexing (Local + Gemini)...")
    
    # Ensure Gemini Key is present
    if not config.get("gemini_api_key"):
        print("❌ Gemini API Key not found! Only Local indexing will work effectively.")
        print("   If you want Cloud Brain, set GEMINI_API_KEY in .env")
        # We continue anyway, as add_events handles missing keys gracefully (skips gemini)
    
    db = SessionLocal()
    try:
        # Fetch all events
        events = db.query(models.TimelineEvent).all()
        total = len(events)
        print(f"📚 Found {total} memories to index.")
        
        chunk_size = 5
        processed = 0
        
        for i in range(0, total, chunk_size):
            chunk = events[i : i + chunk_size]
            
            print(f"🔄 Processing batch {i+1}-{min(i+chunk_size, total)} of {total}...")
            memory_vector_store.add_events(chunk)
            
            processed += len(chunk)
            
            # Rate Limiting Sleep
            # Free Tier (Flash) is 15 RPM for some endpoints.
            # Processing 5 items per batch. 
            # 5s sleep ensures we don't exceed ~60 requests/min even with overhead.
            sleep_time = 5
            print(f"⏳ Sleeping {sleep_time}s to respect API Rate Limits...")
            time.sleep(sleep_time)

        print("\n✅ Re-indexing Complete!")
        print(f"   Total Processed: {processed}")
        print("   Dual Brain is now active.")

    except Exception as e:
        print(f"❌ Error during re-indexing: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reindex_safely()

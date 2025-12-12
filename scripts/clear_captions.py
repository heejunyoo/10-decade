import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models
from database import SessionLocal
from sqlalchemy import text

def clear_ai_captions():
    db = SessionLocal()
    try:
        print("🧹 Cleaning up AI-generated captions...")
        
        # We want to clear 'summary' (AI Caption) and 'description' (User Note)? 
        # User said "Delete AI Generated Captions... use metadata based weather/location".
        # 'summary' is definitely AI.
        # 'description' might be User Input OR AI (if labeled as such).
        # In early implementation, 'description' was user input. 
        # But wait, `analyzer.py` usage?
        # Let's check `services/media.py`.
        # Step 327 viewed `services/media.py`.
        # It calls `analyzer.generate_caption`.
        # `event.summary` = caption.
        # `event.description` = None (usually user input).
        # But let's be safe.
        # I will enforce that `summary` (AI) is NULL.
        # I will leave `description` alone unless verify it is AI.
        # User said "AI Generated Caption". That maps to `summary` field in `models.py` (usually).
        # Let's check `models.py` definition if possible or assume `summary` is the AI one.
        # `timeline_item.html` hid `event.description` AND `event.summary` in Step 384.
        
        # Only clearing `summary` is safer. 
        # The user said "AI generated captions".
        
        rows = db.query(models.TimelineEvent).filter(models.TimelineEvent.summary.isnot(None)).update({models.TimelineEvent.summary: None}, synchronize_session=False)
        db.commit()
        
        print(f"✅ Cleared 'summary' (AI Caption) field for {rows} events.")
        
        # Also ensure Weather/Location is populated (already done by previous script).
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clear_ai_captions()

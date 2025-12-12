
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from sqlalchemy import or_
import sys

def check_progress():
    db = SessionLocal()
    try:
        # Count total photos
        total_photos = db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type == "photo").count()
        
        # Count unprocessed (missing summary)
        unprocessed = db.query(models.TimelineEvent).filter(
            models.TimelineEvent.media_type == "photo",
            or_(models.TimelineEvent.summary == None, models.TimelineEvent.summary == "")
        ).count()
        
        processed = total_photos - unprocessed
        print(f"Status Report:")
        print(f"Total Photos: {total_photos}")
        print(f"Processed (Completed): {processed}")
        print(f"Remaining (Queued/Stuck): {unprocessed}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_progress()

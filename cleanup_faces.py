
from sqlalchemy.orm import Session
from database import SessionLocal
import models
from sqlalchemy import func

def cleanup_faces():
    db = SessionLocal()
    try:
        print("🧹 Starting Face Cleanup...")
        
        # 1. Find faces that are exact duplicates (same event, same location)
        # However, location is stored as JSON string, so exact match works.
        
        # We can't easily do GROUP BY on JSON in SQLite efficiently in all cases, 
        # so let's just iterate events that have many faces.
        
        events = db.query(models.TimelineEvent).filter(models.TimelineEvent.media_type == "photo").all()
        
        total_deleted = 0
        
        for event in events:
            faces = db.query(models.Face).filter(models.Face.event_id == event.id).all()
            if not faces:
                continue
                
            seen_locations = set()
            faces_to_delete = []
            
            for face in faces:
                # Use location string as unique key
                # (Or strict encoding check, but location is better proxy for "same detection result")
                key = face.location
                if key in seen_locations:
                    faces_to_delete.append(face)
                else:
                    seen_locations.add(key)
            
            if faces_to_delete:
                print(f"  Event {event.id}: Deleting {len(faces_to_delete)} duplicates... (Original count: {len(faces)})")
                for f in faces_to_delete:
                    db.delete(f)
                total_deleted += len(faces_to_delete)
        
        db.commit()
        print(f"✅ Cleanup Complete. Removed {total_deleted} duplicate face records.")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_faces()

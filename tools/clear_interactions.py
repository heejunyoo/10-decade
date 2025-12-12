import sys
import os
sys.path.append(os.getcwd())
from database import SessionLocal
import models

def clear_pending():
    db = SessionLocal()
    try:
        deleted = db.query(models.MemoryInteraction).filter(models.MemoryInteraction.is_answered == 0).delete()
        db.commit()
        print(f"Deleted {deleted} pending interactions.")
    except Exception as e:
        print(e)
    finally:
        db.close()

if __name__ == "__main__":
    clear_pending()

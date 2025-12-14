import sys
import os
from sqlalchemy import text

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
import models

def check_integrity():
    print("🕵️ Starting Data Integrity Check...")
    db = SessionLocal()
    try:
        # 1. Database Connection Check
        try:
            db.execute(text("SELECT 1"))
            print("✅ Database connection successful.")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

        # 2. Check Timeline Events
        events = db.query(models.TimelineEvent).all()
        print(f"📊 Found {len(events)} total events.")
        
        valid_count = 0
        missing_files = []
        corrupt_data = []

        for event in events:
            is_valid = True
            
            # Check Image/Video File Existence
            if event.image_url:
                # Remove /static/ prefix if present to check local path
                rel_path = event.image_url.lstrip("/")
                # Handle double static or strict paths
                # Usually: static/uploads/filename
                
                # Check root relative
                if not os.path.exists(rel_path):
                     # Try absolute if needed, or assume CWD is project root
                     if not os.path.exists(os.path.join(os.getcwd(), rel_path)):
                         # Try removing partial static?
                         if rel_path.startswith("static/"):
                             pass # already tried
                         
                         missing_files.append(f"Event {event.id}: Missing file {event.image_url}")
                         is_valid = False
            
            # Check Critical Fields for Embedding
            # We need text to embed. If date is missing, it's weird but not fatal for embedding.
            # But let's log it.
            if not event.date:
                 corrupt_data.append(f"Event {event.id}: Missing Date")
            
            if is_valid:
                valid_count += 1

        # 3. Report
        print("\n--- 📋 Integrity Report ---")
        print(f"✅ Valid Events: {valid_count}/{len(events)}")
        
        if missing_files:
            print(f"❌ Missing Files ({len(missing_files)}):")
            for msg in missing_files[:10]:
                print(f"  - {msg}")
            if len(missing_files) > 10:
                print(f"  ... and {len(missing_files) - 10} more.")
        else:
            print("✅ All media files present.")

        if corrupt_data:
            print(f"⚠️ Data Warnings ({len(corrupt_data)}):")
            for msg in corrupt_data[:10]:
                print(f"  - {msg}")
        else:
            print("✅ Data constraints satisfied.")
            
        print("---------------------------")
        
        if missing_files:
            print("❌ Verification FAILED. Please resolve missing files before indexing.")
            return False
            
        print("✅ Verification PASSED. Ready for LanceDB Migration.")
        return True

    except Exception as e:
        print(f"❌ Unexpected Error during verification: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if not check_integrity():
        sys.exit(1)

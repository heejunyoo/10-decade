
import sys
import os
from sqlalchemy import text
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine

def migrate():
    with engine.connect() as conn:
        print("🔧 Migrating Database Schema...")
        try:
            conn.execute(text("ALTER TABLE timeline_events ADD COLUMN mood VARCHAR"))
            print("   ✅ Added 'mood' to timeline_events")
        except Exception as e:
            print(f"   ⚠️  timeline_events.mood might already exist: {e}")

        try:
            conn.execute(text("ALTER TABLE faces ADD COLUMN emotion VARCHAR"))
            print("   ✅ Added 'emotion' to faces")
        except Exception as e:
            print(f"   ⚠️  faces.emotion might already exist: {e}")
            
        print("✅ Migration Complete.")

if __name__ == "__main__":
    migrate()

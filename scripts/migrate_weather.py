
import sqlite3
import os

DB_PATH = "decade_journey.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(timeline_events)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "weather_info" not in columns:
            print("Creating 'weather_info' column...")
            cursor.execute("ALTER TABLE timeline_events ADD COLUMN weather_info TEXT")
            print("✅ 'weather_info' column added.")
        else:
            print("ℹ️ 'weather_info' column already exists.")

        conn.commit()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

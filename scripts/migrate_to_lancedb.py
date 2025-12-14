import sys
import os

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rag import Indexer, LANCEDB_PATH, TABLE_NAME
import lancedb

def main():
    print("🚀 Starting Migration to LanceDB...")
    try:
        # 1. Clean old table
        if os.path.exists(LANCEDB_PATH):
             print("🧹 Cleaning old LanceDB table...")
             db = lancedb.connect(LANCEDB_PATH)
             try:
                 db.drop_table(TABLE_NAME)
                 print("✅ Old table dropped.")
             except Exception:
                 pass # Table might not exist
        
        # 2. Index
        Indexer.index_all()
        print("✅ Migration Complete!")
    except Exception as e:
        print(f"❌ Migration Failed: {e}")

if __name__ == "__main__":
    main()

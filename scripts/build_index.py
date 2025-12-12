
import sys
import os
sys.path.append(os.getcwd())

from services.rag import Indexer

if __name__ == "__main__":
    print("🚀 Starting Deep Memory Indexing...")
    Indexer.index_all()
    print("✅ Indexing Complete.")

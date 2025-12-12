
import sys
import os

# Add parent dir to path to allow importing services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.faces import reindex_faces

if __name__ == "__main__":
    print("🚀 Launching Face Re-indexing (Dlib Optimized)...")
    reindex_faces()

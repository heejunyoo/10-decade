
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.rag import memory_vector_store, Embedder
from database import SessionLocal
import models

def debug_search(query_text):
    print(f"🔎 Debugging Query: '{query_text}'")
    
    # Check Model Name
    model = Embedder.get_model()
    print(f"🤖 Model: {model}")
    
    # 1. Run Search
    results = memory_vector_store.search(query_text, k=5)
    
    print(f"\n📊 Found {len(results)} results:")
    for i, hit in enumerate(results):
        print(f"\n--- [Result {i+1}] ---")
        print(f"🆔 ID: {hit['id']}")
        print(f"📉 Distance/Score: {hit['score']} (Lower is better for Cosine Distance)")
        print(f"📝 Stored Text: {hit['text']}")
        print(f"🏷 Metadata: {hit['metadata']}")
        
        # Heuristic: Good match usually < 0.5?
        quality = "⭐⭐⭐" if hit['score'] < 0.4 else ("⭐⭐" if hit['score'] < 0.6 else "❌ Irrelevant?")
        print(f"🧐 Quality Assessment: {quality}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = sys.argv[1]
    else:
        q = "맛있는 음식" # Default Korean query
        
    debug_search(q)

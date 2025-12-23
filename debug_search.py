
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.rag import memory_vector_store

def debug_search(query):
    print(f"\n🔎 Testing Query: '{query}'")
    hits = memory_vector_store.search(query, k=5)
    
    print(f"   Found {len(hits)} hits:")
    for i, hit in enumerate(hits):
        # snippet = hit['text'][:30].replace('\n', ' ')
        # print(f"   [{i+1}] Score: {hit.get('score', 0):.4f} | ID: {hit['id']} | {snippet}...")
        print(f"   [{i+1}] ID: {hit['id']} | Img: {hit['metadata'].get('image_url')}")

if __name__ == "__main__":
    # Test with the queries user mentioned
    debug_search("중국에서 행복한 시간은 언제야?")
    # debug_search("제주도에서 강아지와 행복한 한때를 알려줘")
    # debug_search("Random Query 12345") 

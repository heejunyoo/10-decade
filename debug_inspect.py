
import sys
import os
import lancedb

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.rag import memory_vector_store

def inspect_ids(ids):
    print(f"\n🕵️ Inspecting IDs: {ids}")
    
    try:
        # Construct filter string
        id_str = ", ".join([f"'{i}'" for i in ids])
        results = memory_vector_store.table_local.search().where(f"id IN ({id_str})").limit(10).to_list()
        
        for r in results:
            print(f"\n🆔 ID: {r['id']}")
            print(f"📅 Date: {r['date']}")
            print(f"📍 Location: {r['location']}")
            print(f"📝 Text: {r['text']}")
            print(f"🖼 Image: {r['image_url']}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_ids(['133', '133']) # Just 133

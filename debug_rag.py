from services.rag import memory_vector_store, Embedder

# 1. Check Count
try:
    count = memory_vector_store.table.count_rows()
    print(f"📉 Total Memories in DB: {count}")
except Exception as e:
    print(f"❌ Error counting rows: {e}")

# 2. Check Raw Search (No Interface Filter)
query = "제주도"
print(f"\n🔍 Raw Search for: {query}")
emb = Embedder.embed_text([query])[0]
try:
    results = memory_vector_store.table.search(emb).limit(5).to_list()
    for r in results:
        dist = r.get('_distance', -1)
        text = r.get('text', '')[:50]
        print(f" - Dist: {dist:.4f} | Text: {text}...")
except Exception as e:
    print(f"❌ Search Error: {e}")

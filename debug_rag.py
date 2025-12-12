from services.rag import memory_vector_store
from database import SessionLocal
import models

def debug_rag():
    # 1. Check Collection Count
    count = memory_vector_store.collection.count()
    print(f"📊 ChromaDB Total Documents: {count}")
    
    # 2. Check DB Count
    db = SessionLocal()
    db_count = db.query(models.TimelineEvent).count()
    captioned_count = db.query(models.TimelineEvent).filter(models.TimelineEvent.summary != None).count()
    print(f"🗄️  SQLite Total Events: {db_count}")
    print(f"📝 Events with Captions: {captioned_count}")
    
    # 3. Peek at first 5 items
    if count > 0:
        print("\n🔍  Peeking at first 3 indexed items:")
        peek = memory_vector_store.collection.peek(limit=3)
        for i, doc in enumerate(peek['documents']):
            print(f"   [{i}] {doc[:100]}...")
            print(f"       Meta: {peek['metadatas'][i]}")
            
    # 4. Run a test search
    test_query = "beach"
    print(f"\n🧪 Test Search: '{test_query}'")
    hits = memory_vector_store.search(test_query)
    for hit in hits:
        print(f"   Score: {hit['score']:.4f} | Text: {hit['text'][:100]}...")

if __name__ == "__main__":
    debug_rag()

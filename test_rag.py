
import sys
import os
sys.path.append(os.getcwd())

from services.rag import memory_vector_store
from services.gemini import gemini_service
from services.config import config
import models
from database import SessionLocal

def test_rag_flow():
    print(f"🧪 Testing RAG Flow with AI Provider: {config.get('ai_provider')}")
    print(f"🧠 Gemini Model: {config.get('gemini_model')}")
    
    query = "Halloween"
    print(f"\n🔍 Searching for: '{query}'")
    
    # 1. Search VectorDB
    results = memory_vector_store.search(query, k=3)
    
    if not results:
        print("❌ No results found. Index might be empty.")
        print("   If you just added photos, run './manage.py backfill-rag' or wait for background task.")
        return

    print(f"✅ Found {len(results)} relevant memories:")
    context_text = ""
    for r in results:
        # r structure: {'id': '...', 'score': 0.123, 'text': '...', 'metadata': {...}}
        meta = r.get('metadata', {})
        date_str = meta.get('date', 'Unknown Date')
        print(f"   - [{date_str}] Score: {r['score']:.4f} | {r['text'][:50]}...")
        context_text += f"- [{date_str}] {r['text']}\n"

    # 2. Test Chat Generation
    print("\n💬 Testing Chat Generation...")
    
    system_prompt = f"""
    You are a helpful assistant for a personal memory archive. 
    Use the following context to answer the user's question.
    
    Context:
    {context_text}
    """
    
    user_question = "What was the vibe of our Halloween party?"
    print(f"❓ User Question: {user_question}")
    
    response = gemini_service.chat_query(system_prompt, user_question)
    
    print("\n🤖 AI Response:")
    print("-" * 40)
    print(response)
    print("-" * 40)

if __name__ == "__main__":
    test_rag_flow()

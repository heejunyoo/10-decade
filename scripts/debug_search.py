
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force AI Environment
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"

from services.rag import memory_vector_store
from services.ollama_manager import ollama_manager
import ollama

def debug_search(query_text="바다에서 행복한 시간"):
    print(f"🔎 Testing Search Query: '{query_text}'")
    
    # 1. Retrieval
    print("🧠 Searching Vector DB...")
    hits = memory_vector_store.search(query_text, k=3)
    
    if not hits:
        print("❌ No hits found. RAG is empty or query matches nothing.")
        return

    print(f"✅ Found {len(hits)} hits:")
    for i, hit in enumerate(hits):
        print(f"   [{i+1}] Score: {hit['score']:.4f} | Text: {hit['text'][:50]}...")

    # 2. Generation
    print("\n🤖 Testing Ollama Generation (llama3.1)...")
    
    if not ollama_manager.ensure_running():
        print("❌ Ollama is not running!")
        return

    context_block = "\n".join([f"- [Memory {i+1}] {hit['text']}" for i, hit in enumerate(hits)])
    
    system_prompt = (
        "You are 'Deep Memory'. Answer in Korean. Use the context to answer."
    )
    user_prompt = f"Question: {query_text}\n\nContext:\n{context_block}"
    
    try:
        response = ollama.generate(
            model='llama3.1', 
            prompt=f"{system_prompt}\n\n{user_prompt}", 
            stream=False
        )
        print("\n✅ Ollama Response:")
        print("--------------------------------------------------")
        print(response.get('response'))
        print("--------------------------------------------------")
    except Exception as e:
        print(f"❌ Generation failed: {e}")

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "바다에서 행복한 시간"
    debug_search(query)

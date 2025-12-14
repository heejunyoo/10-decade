
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.rag import memory_vector_store
from typing import List, Optional

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatQuery(BaseModel):
    text: str

class ChatResponse(BaseModel):
    answer: str
    context_items: List[dict]

@router.post("/query", response_model=ChatResponse)
async def query_memories(query: ChatQuery):
    print(f"DEBUG: Received Chat Query: {query.text}")

    # 0. MEMORY OPTIMIZATION: Unload Vision Model to free RAM for LLM
    try:
        from services.analyzer import analyzer
        # Force unload if it's lingering (Smart Batching might keep it alive)
        # We need the RAM for Llama 3.1 (5GB) + BGE-M3
        print("DEBUG: Force unloading Vision Model for Chat...")
        analyzer.unload_model() 
    except Exception as e:
        print(f"DEBUG: Warning - Could not unload vision model: {e}")

    # 1. Retrieval
    hits = memory_vector_store.search(query.text, k=5) or [] # Increased k to 5
    
    print(f"DEBUG: Search returned {len(hits)} hits.")
    
    # 2. Context Construction
    context_items = []
    
    for hit in hits:
        context_items.append({
            "text": hit['text'],
            "score": hit['score'],
            "metadata": hit['metadata']
        })
        
    # 3. Generation
    if not hits:
        print("DEBUG: No hits found.")
        answer = "관련된 추억을 찾지 못했어요. 😢 다른 검색어로 시도해보시겠어요?"
    else:
        # Construct Prompt
        system_prompt = (
            "You are 'Decade', a warm and nostalgic personal memory assistant. "
            "Your goal is to help the user relive their past moments using the provided context. "
            "Guidelines:\n"
            "1. Language: Always answer in polite Korean (존댓말/Honorifics), using a gentle and warm tone.\n"
            "2. Tone: Sentimental, empathetic, and appreciative of family memories.\n"
            "3. Content: Use specific details (Date, Location, People, Weather) from the context to tell a mini-story.\n"
            "4. Honesty: If the context doesn't have the answer, say so. Do not make up facts."
        )
        
        # Format context for the LLM
        context_block = "\n".join([f"- [Memory {i+1}] {hit['text']}" for i, hit in enumerate(hits)])
        
        user_prompt = f"User Question: {query.text}\n\nRetrieved Memories:\n{context_block}\n\nPlease answer the question based on these memories."
        
        try:
            from services.config import config
            provider = config.get("ai_provider")
            print(f"DEBUG: Using AI Provider: {provider}")
            
            if provider == "gemini":
                from services.gemini import gemini_service
                answer = gemini_service.chat_query(system_prompt, user_prompt)
            else:
                # LOCAL (OLLAMA)
                from services.ollama_manager import ollama_manager
                if not ollama_manager.ensure_running():
                    print("DEBUG: Ollama ensure_running failed.")
                    raise Exception("Ollama server failed to start.")

                import ollama
                
                # Use installed model (Optimized for Speed/Memory)
                MODEL_NAME = 'llama3.2:3b' 
                
                print(f"DEBUG: Generating with Ollama ({MODEL_NAME})...")
                response = ollama.generate(
                    model=MODEL_NAME, 
                    prompt=f"{system_prompt}\n\n{user_prompt}",
                    keep_alive='5m', # Keep in RAM for 5 mins
                    options={
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_ctx": 4096 # Limit context to save memory
                    }
                )
                answer = response.get('response', "")
                
                if not answer.strip():
                     print("DEBUG: Ollama returned empty string.")
                     answer = "음... 생각이 잘 나지 않네요. (AI 응답이 비어있습니다)"

        except Exception as e:
            provider = config.get("ai_provider", "Unknown")
            print(f"❌ AI Error ({provider}): {e}")
            
            error_source = "Gemini" if provider == "gemini" else "Ollama (Local)"
            answer = (
                f"죄송합니다. AI 두뇌({error_source})에 연결할 수 없습니다. "
                f"오류: {str(e)}"
            )
            
    print(f"DEBUG: Final Answer: {answer[:50]}...")
    return ChatResponse(answer=answer, context_items=context_items)

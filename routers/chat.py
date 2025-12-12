
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
    # 1. Retrieval
    hits = memory_vector_store.search(query.text, k=3) or []
    
    # 2. Context Construction
    context_str = ""
    context_items = []
    
    for hit in hits:
        context_str += f"- {hit['text']}\n"
        context_items.append({
            "text": hit['text'],
            "score": hit['score'],
            "metadata": hit['metadata']
        })
        
    # 3. Generation (Ollama)
    import requests
    
    if not hits:
        answer = "I couldn't find any specific memories matching that query."
    else:
        # Construct Prompt
        # Construct Prompt
        # Prompt Engineering: Persona, Tone, and Language (Korean default)
        system_prompt = (
            "You are 'Deep Memory', a warm and nostalgic personal memory assistant. "
            "Your goal is to help the user relive their past moments using the provided context. "
            "Guidelines:\n"
            "1. Language: Answer in Korean (unless the user specifically asks in English).\n"
            "2. Tone: Warm, sentimental, and appreciative of family/friends.\n"
            "3. Content: Use specific details (Date, Location, People, Weather) from the context to tell a mini-story.\n"
            "4. Honesty: If the context doesn't have the answer, admit it politely. Do not make up facts."
        )
        
        # Format context for the LLM
        context_block = "\n".join([f"- [Memory {i+1}] {hit['text']}" for i, hit in enumerate(hits)])
        
        user_prompt = f"User Question: {query.text}\n\nRetrieved Memories:\n{context_block}\n\nPlease answer the question based on these memories."
        
        user_prompt = f"User Question: {query.text}\n\nRetrieved Memories:\n{context_block}\n\nPlease answer the question based on these memories."
        
        try:
            # OPTION: Gemini API
            from services.config import config
            if config.get("ai_provider") == "gemini":
                from services.gemini import gemini_service
                answer = gemini_service.chat_query(system_prompt, user_prompt)
            else:
                # OPTION: Local Ollama (Native Client)
                # Auto-start if needed
                from services.ollama_manager import ollama_manager
                if not ollama_manager.ensure_running():
                    raise Exception("Ollama server failed to start automatically.")

                import ollama
                
                response = ollama.generate(
                    model='llama3.1', 
                    prompt=f"{system_prompt}\n\n{user_prompt}",
                    options={
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                )
                answer = response.get('response', "잠시 생각이 떠오르지 않네요.")
                
        except Exception as e:
            provider = config.get("ai_provider")
            print(f"AI Error ({provider}): {e}")
            
            error_source = "Gemini" if provider == "gemini" else "Ollama (Local)"
            
            # Fallback for when AI is offline or crashes
            answer = (
                f"죄송합니다. AI 두뇌({error_source})에 연결할 수 없습니다. "
                f"하지만 {len(hits)}개의 관련 추억을 찾았습니다. 아래 사진들을 확인해보세요! "
            )

    return ChatResponse(answer=answer, context_items=context_items)

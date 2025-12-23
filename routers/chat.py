
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
    
    # Debug: Log the image URLs being returned
    print(f"DEBUG: Returning {len(context_items)} context items:")
    for i, item in enumerate(context_items):
        print(f"   [{i+1}] {item['metadata'].get('image_url', 'No Image')} (Score: {item['score']:.4f})")
        
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
        
        user_prompt_final = f"User Question: {query.text}\n\nRetrieved Memories:\n{context_block}\n\nPlease answer the question based on these memories."
        
        from services.ai_service import ai_service
        
        # Delegate generation to the unified service
        # This automatically handles Provider Switching (Local/Gemini) and Model Selection (Best Local)
        answer = ai_service.generate_response(system_prompt, user_prompt_final, temperature=0.7)
            
    print(f"DEBUG: Final Answer: {answer[:50]}...")
    return ChatResponse(answer=answer, context_items=context_items)

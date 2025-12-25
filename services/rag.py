import os
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry
from lancedb.embeddings import get_registry
# Lazy Import: sentence_transformers
import models
from database import SessionLocal
from typing import List, Dict, Any, Optional
import pydantic

# Path for local vector DB (LanceDB)
LANCEDB_PATH = "./lancedb_data"
TABLE_NAME = "decade_memories"

from services.logger import get_logger
logger = get_logger("rag")

# Embedding Model Config
# We stick to the existing one for Phase 1, or prepare for BGE-M3
MODEL_NAME = 'BAAI/bge-m3'
DIMENSIONS = 1024 # BGE-M3 output dimension

class Embedder:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            print(f"🧠 Loading Embedding Model ({MODEL_NAME})...")
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer(MODEL_NAME)
        return cls._model

    @classmethod
    def embed_text(cls, texts: List[str]) -> List[List[float]]:
        model = cls.get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()

# Define LanceDB Schema using Pydantic
# Define Schema (Same for both, but Dimensions differ)
class MemoryItemLocal(LanceModel):
    id: str
    vector: Vector(1024) # BGE-M3
    text: str 
    date: str
    location: str
    media_type: str
    image_url: str
    payload_json: str 

class MemoryItemGemini(LanceModel):
    id: str
    vector: Vector(768) # text-embedding-004
    text: str 
    date: str
    location: str
    media_type: str
    image_url: str
    payload_json: str 

class MemoryVectorStore:
    def __init__(self):
        if not os.path.exists(LANCEDB_PATH):
            os.makedirs(LANCEDB_PATH)
            
        self.db = lancedb.connect(LANCEDB_PATH)
        
        # Table 1: Local Brain (BGE-M3)
        try:
            self.table_local = self.db.create_table("decade_memories_local", schema=MemoryItemLocal, exist_ok=True)
            # Legacy Migration: If "decade_memories" exists, rename or just assume new starts here.
            # Ideally user should re-index.
        except Exception as e:
            logger.error(f"Failed to init Local Table: {e}")

        # Table 2: Cloud Brain (Gemini)
        try:
            self.table_gemini = self.db.create_table("decade_memories_gemini", schema=MemoryItemGemini, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to init Gemini Table: {e}")

    def add_events(self, events: List[models.TimelineEvent]):
        """
        Dual Indexing: Adds to BOTH tables if possible.
        """
        if not events: return

        documents = []
        # ... (Context construction logic is identical, omitting for brevity in diff but MUST be included in actual file) ...
        # I will COPY the context construction logic exactly from previous file.
        
        # --- RE-IMPLEMENT CONTEXT CONSTRUCTION START ---
        items_payload = [] # List of dicts without vector
        
        for event in events:
            parts = [f"Date: {event.date}"]
            if event.location_name: parts.append(f"Location: {event.location_name}")
            if event.weather_info: parts.append(f"Weather: {event.weather_info}")
            if event.title: parts.append(f"Title: {event.title}")
            
            content = []
            if event.summary and not event.summary.startswith("[Low Confidence]"):
                content.append(f"AI Description: {event.summary}")
            if event.description:
                content.append(f"User Note: {event.description}")
            if content: parts.append(" ".join(content))
                
            if event.faces:
                names = [f.person.name for f in event.faces if f.person and f.person.name != "Unknown"]
                if names: parts.append(f"People: {', '.join(set(names))}")
                emotions = [f"{f.person.name} looks {f.emotion}" for f in event.faces if f.person and f.emotion]
                if emotions: parts.append(f"Emotions: {', '.join(emotions)}")
            if event.mood: parts.append(f"Mood: {event.mood}")
            
            text = ". ".join(parts)
            documents.append(text)
            
            import json
            items_payload.append({
                "id": str(event.id),
                "date": event.date or "",
                "location": event.location_name or "",
                "media_type": event.media_type,
                "image_url": event.image_url or "",
                "text": text,
                "payload_json": json.dumps({
                     "title": event.title,
                     "summary": event.summary
                 })
            })
        # --- RE-IMPLEMENT CONTEXT CONSTRUCTION END ---

        if not documents: return

        # 1. Index to Local Brain (Always)
        try:
            logger.info(f"🧮 Embedding {len(documents)} memories (Local BGE-M3)...")
            embeddings_local = Embedder.embed_text(documents)
            
            final_items_local = []
            for item, emb in zip(items_payload, embeddings_local):
                i = item.copy()
                i["vector"] = emb
                final_items_local.append(MemoryItemLocal(**i))
            
            # Upsert Local
            try:
                self.table_local.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(final_items_local)
            except:
                ids = [x.id for x in final_items_local]
                self.table_local.delete(f"id IN ({','.join(['\'' + i + '\'' for i in ids])})")
                self.table_local.add(final_items_local)
                
            logger.info(f"✅ Indexed {len(documents)} to Local Brain.")
        except Exception as e:
            logger.error(f"❌ Local Indexing Failed: {e}")

        # 2. Index to Gemini Brain (If Key Available)
        from services.config import config
        if config.get("gemini_api_key"):
            try:
                logger.info(f"☁️ Embedding {len(documents)} memories (Gemini Cloud)...")
                from services.gemini import gemini_service
                
                final_items_gemini = []
                for item in items_payload:
                    emb = gemini_service.get_embedding(item["text"])
                    if emb:
                        i = item.copy()
                        i["vector"] = emb
                        final_items_gemini.append(MemoryItemGemini(**i))
                
                if final_items_gemini:
                    # Upsert Gemini
                    try:
                        self.table_gemini.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(final_items_gemini)
                    except:
                        ids = [x.id for x in final_items_gemini]
                        self.table_gemini.delete(f"id IN ({','.join(['\'' + i + '\'' for i in ids])})")
                        self.table_gemini.add(final_items_gemini)
                    logger.info(f"✅ Indexed {len(final_items_gemini)} to Gemini Brain.")
                    
            except Exception as e:
                logger.warning(f"⚠️ Gemini Indexing Skipped (API Error): {e}")

    def update_photo_index(self, event_id: int):
        db = SessionLocal()
        try:
            event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
            if event: self.add_events([event])
        finally:
            db.close()

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        from datetime import datetime
        from services.config import config
        
        # Determine Mode: check explicit overrides, otherwise default to "ensemble" if key exists
        search_provider = config.get("search_provider") # 'local', 'gemini', or None
        has_gemini = bool(config.get("gemini_api_key"))
        
        # 1. Force Local
        if search_provider == "local" or (not has_gemini and not search_provider):
             logger.info(f"🔍 Searching Local Brain (BGE-M3) for: {query}")
             return self._search_local(query, k)
             
        # 2. Force Gemini
        if search_provider == "gemini":
             logger.info(f"🔍 Searching Gemini Brain for: {query}")
             return self._search_gemini(query, k)
             
        # 3. Default: Ensemble (Dual) - Best of Both Worlds
        logger.info(f"🧠 Dual-Search (Ensemble): Local + Gemini for '{query}'")
        return self._search_ensemble(query, k)

    def _search_ensemble(self, query: str, k: int) -> List[Dict[str, Any]]:
        """
        Combines results from Local (BGE-M3) and Gemini using Reciprocal Rank Fusion (RRF).
        Then assumes RERANKING via Gemini Flash to filter out 'sticky' irrelevant results.
        """
        # 1. Retrieval (High Recall)
        # Fetch more candidates to allow reranking (3x k) to cast a wide net
        candidates_k = k * 3
        results_local = self._search_local(query, candidates_k) 
        results_gemini = self._search_gemini(query, candidates_k)
        
        # 2. RRF Fusion
        k_rrf = 60 
        scores = {}
        metadata_map = {}
        
        for rank, item in enumerate(results_local):
            doc_id = item['id']
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rank + k_rrf))
            metadata_map[doc_id] = item
            
        for rank, item in enumerate(results_gemini):
            doc_id = item['id']
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (rank + k_rrf))
            if doc_id not in metadata_map: 
                metadata_map[doc_id] = item
            
        # Top Candidates from RRF
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        top_candidates = [metadata_map[doc_id] for doc_id in sorted_ids[:candidates_k]] # Keep pool large for LLM
        
        # 3. LLM Reranking (Precision)
        # Use Gemini Flash to filter out noise (like the persistent 'sticky' images)
        logger.info(f"🧠 Reranking {len(top_candidates)} candidates via Gemini...")
        return self._rerank_with_llm(query, top_candidates, k)

    def _rerank_with_llm(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        from services.gemini import gemini_service
        try:
            # Construct Prompt
            candidates_text = ""
            for i, c in enumerate(candidates):
                # Optimize text for token usage
                meta_str = f"Date: {c['metadata'].get('date')}, Location: {c['metadata'].get('location')}"
                snippet = c['text'][:200].replace('\n', ' ')
                candidates_text += f"[{i}] ID: {c['id']} | {meta_str} | Content: {snippet}\n"

            prompt = (
                f"User Query: {query}\n\n"
                f"Candidate Memories:\n{candidates_text}\n\n"
                "Task: Select the most relevant memories for the query. \n"
                "Rules:\n"
                "1. STRICTLY ignore memories that conflict with the query (e.g. wrong location, wrong year).\n"
                "2. If the query specifies a place (e.g. 'China'), reject items from other places (e.g. 'Korea').\n"
                "3. Rank them by relevance (Most relevant first).\n"
                "4. Return ONLY a JSON list of indices, e.g. [0, 4, 2]. Return at most 5 indices.\n"
                "5. If no relevant memories found, return []."
            )

            # Call Gemini (Flash is preferred for speed and rate limits)
            # Explicitly request dynamically found Flash model to avoid consuming Pro quota (2 RPM)
            flash_model = gemini_service.get_flash_model_name()
            
            response_text = gemini_service.chat_query(
                "You are a search ranking assistant. Output JSON only.", 
                prompt, 
                temperature=0.0,
                model_name=flash_model
            )
            
            import json
            import re
            
            # Extract JSON
            match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if match:
                selected_indices = json.loads(match.group(0))
                reranked_results = []
                for idx in selected_indices:
                    if 0 <= idx < len(candidates):
                        reranked_results.append(candidates[idx])
                
                logger.info(f"   ↳ LLM Selected {len(reranked_results)} relevant memories.")
                return reranked_results[:top_k]
            else:
                logger.warning("   ⚠️ LLM Reranking failed to parse JSON. Falling back to RRF.")
                return candidates[:top_k]

        except Exception as e:
            logger.error(f"   ⚠️ LLM Reranking Error: {e}. Falling back to RRF.")
            return candidates[:top_k]

    def _search_local(self, query: str, k: int):
        # ... logic from previous search() using self.table_local and Embedder ...
        query_embedding = Embedder.embed_text([query])[0]
        return self._execute_search(self.table_local, query_embedding, query, k, 1024)

    def _search_gemini(self, query: str, k: int):
        from services.gemini import gemini_service
        query_embedding = gemini_service.get_embedding(query)
        if not query_embedding: return []
        return self._execute_search(self.table_gemini, query_embedding, query, k, 768)

    def _execute_search(self, table, vector, query_text, k, dim):
        # Shared Hybrid Logic
        try:
            import re
            
            # Dynamic Weighting Logic
            alpha_vector = 0.7 
            if re.search(r"\b(19|20)\d{2}\b", query_text): alpha_vector = 0.1
            if any(w in query_text for w in ["행복", "happy", "summer", "winter"]): alpha_vector = 0.9 # Add seasons
            
            results = table.search(vector).limit(k * 2).to_list()
            hits = []
            
            keywords = [w.lower() for w in query_text.split() if len(w) > 1]
            
            for r in results:
                dist = r.get('_distance', 0.0)
                vector_score = 1.0 - (dist / 2.0)
                
                # Relaxed threshold for candidate generation
                # if vector_score < 0.3 and alpha_vector > 0.5: continue 
                
                keyword_matches = sum(1 for kw in keywords if kw in r["text"].lower())
                keyword_score = min(keyword_matches * 0.3, 1.0)
                
                # Hybrid Score
                hybrid_score = (vector_score * alpha_vector) + (keyword_score * (1.0 - alpha_vector))
                
                meta = { "date": r["date"], "location": r["location"], "media_type": r["media_type"], "image_url": r["image_url"] }
                hits.append({
                    "id": r["id"], 
                    "score": hybrid_score, 
                    "text": r["text"], 
                    "metadata": meta
                })
            
            hits.sort(key=lambda x: x["score"], reverse=True)
            return hits
        except Exception as e:
            logger.error(f"Search Error: {e}")
            return []

    def get_embeddings(self, ids: List[str]):
        return {} # Deprecated/Unused
    
class Indexer:
    @staticmethod
    def index_all():
        db = SessionLocal()
        vector_store = MemoryVectorStore()
        try:
            events = db.query(models.TimelineEvent).all()
            logger.info(f"📚 Full Indexing: {len(events)} events (Dual Mode)")
            chunk_size = 20 # Smaller chunk for dual API calls
            for i in range(0, len(events), chunk_size):
                chunk = events[i : i + chunk_size]
                vector_store.add_events(chunk)
        finally:
            db.close()

# Singleton
memory_vector_store = MemoryVectorStore()

import os
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry
from sentence_transformers import SentenceTransformer
import models
from database import SessionLocal
from typing import List, Dict, Any, Optional
import pydantic

# Path for local vector DB (LanceDB)
LANCEDB_PATH = "./lancedb_data"
TABLE_NAME = "decade_memories"

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
            cls._model = SentenceTransformer(MODEL_NAME)
        return cls._model

    @classmethod
    def embed_text(cls, texts: List[str]) -> List[List[float]]:
        model = cls.get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()

# Define LanceDB Schema using Pydantic
class MemoryItem(LanceModel):
    id: str
    vector: Vector(DIMENSIONS)
    text: str # The searchable context blob
    
    # Metadata Fields
    date: str
    location: str
    media_type: str
    image_url: str
    
    # Full original payload for display/reference
    payload_json: str 

class MemoryVectorStore:
    def __init__(self):
        # Ensure directory exists (LanceDB handles this but good to be explicit)
        if not os.path.exists(LANCEDB_PATH):
            os.makedirs(LANCEDB_PATH)
            
        self.db = lancedb.connect(LANCEDB_PATH)
        
        # Open or Create Table
        try:
            self.table = self.db.create_table(TABLE_NAME, schema=MemoryItem, exist_ok=True)
        except Exception as e:
            print(f"Failed to open/create table: {e}")
            # Fallback or re-raise
            raise e

    def add_events(self, events: List[models.TimelineEvent]):
        """
        Embeds and upserts events.
        """
        if not events:
            return

        documents = []
        ids = []
        
        items_to_add = []
        
        for event in events:
            # Construct rich context string
            parts = [f"Date: {event.date}"]
            
            if event.location_name:
                parts.append(f"Location: {event.location_name}")
            
            if event.weather_info:
                parts.append(f"Weather: {event.weather_info}")
                
            if event.title:
                parts.append(f"Title: {event.title}")
                
            content = []
            if event.summary:
                if event.summary.startswith("[Low Confidence]"):
                    print(f"🛡️ RAG Exclusion: Skipping hallucinated summary for Event {event.id}")
                else:
                    content.append(f"AI Description: {event.summary}")
            if event.description:
                content.append(f"User Note: {event.description}")
            
            if content:
                parts.append(" ".join(content))
                
            if event.faces and len(event.faces) > 0:
                names = []
                emotion_context = []
                for f in event.faces:
                    if f.person and f.person.name != "Unknown":
                        names.append(f.person.name)
                        if f.emotion:
                            emotion_context.append(f"{f.person.name} looks {f.emotion}")
                
                if names:
                    parts.append(f"People: {', '.join(set(names))}")
                
                if emotion_context:
                    parts.append(f"Emotions: {', '.join(emotion_context)}")

            if event.mood:
                parts.append(f"Mood: {event.mood}")
            
            text = ". ".join(parts)
            documents.append(text)
            ids.append(str(event.id))
            
            # Prepare Item data (minus vector)
             # We will compute vectors in batch
            import json
            payload = {
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
            }
            items_to_add.append(payload)
        
        if not documents:
            return

        # Generate Embeddings (Batch)
        print(f"🧮 Embedding {len(documents)} memories...")
        embeddings = Embedder.embed_text(documents)
        
        # Merge vector into payload
        final_items = []
        for item, emb in zip(items_to_add, embeddings):
            item["vector"] = emb
            # Convert to Pydantic Model to ensure Schema/Order enforcement
            try:
                model_item = MemoryItem(**item)
                final_items.append(model_item)
            except Exception as e:
                print(f"⚠️ Skipping invalid item {item['id']}: {e}")
            
        # Upsert (Delete old by ID then Add)
        try:
             # Standardize: List of IDs to delete
             # ids_to_del = [x.id for x in final_items] # Access via attribute now
             
             # Correct Upsert pattern in LanceDB:
             # self.table.merge_insert("id") in newer versions.
             try:
                 self.table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(final_items)
             except AttributeError:
                 # Fallback for older versions
                 print("⚠️ merge_insert not found, using delete-insert fallback")
                 ids_to_del = [x.id for x in final_items]
                 for id_val in ids_to_del:
                     self.table.delete(f"id = '{id_val}'")
                 self.table.add(final_items)

             print(f"✅ Indexed {len(final_items)} memories to LanceDB.")

        except Exception as e:
            print(f"Error during LanceDB Upsert: {e}")

    def update_photo_index(self, event_id: int):
        """
        Live Re-Indexing for a single photo.
        """
        db = SessionLocal()
        try:
            event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
            if not event:
                return
            
            self.add_events([event])
            print(f"🔄 Memory {event_id} re-indexed successfully.")
            
        finally:
            db.close()

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        print(f"🔍 Hybrid Search for: {query}")
        query_embedding = Embedder.embed_text([query])[0]
        
        # 1. Fetch Candidates (Fetch 3x k to allow for reranking)
        FETCH_K = k * 3
        
        try:
            import re
            
            # 2. Dynamic Weighting Logic (CTO Directive)
            # Default: Vector Heavy (0.7)
            # If Year/Date detected -> Keyword Heavy (Vector 0.1)
            # If Emotion detected -> Vector Heavy (Vector 0.9)
            
            alpha_vector = 0.7 
            
            # Regex Patterns
            year_pattern = r"\b(19|20)\d{2}\b" # 19xx or 20xx
            date_pattern = r"\b(19|20)\d{2}[-./]\d{1,2}\b"
            
            if re.search(year_pattern, query) or re.search(date_pattern, query):
                print(f"DEBUG: 📅 Date pattern detected. Switching to Keyword Focus.")
                alpha_vector = 0.1 # 10% Vector, 90% Keyword
                
            # Emotion Keywords (Simple list for now)
            emotion_keywords = ["행복", "우울", "슬픈", "기쁜", "화난", "즐거운", "happy", "sad"]
            if any(k in query for k in emotion_keywords):
                print(f"DEBUG: 😊 Emotion pattern detected. Switching to Vector Focus.")
                alpha_vector = 0.9 # 90% Vector
            
            print(f"DEBUG: Using Dynamic Weighting - Vector: {alpha_vector}, Keyword: {1.0 - alpha_vector}")

            results = self.table.search(query_embedding)\
                .limit(k * 4)\
                .to_list()
                
            hits = []
            
            # 2. Hybrid Scoring Logic
            # Identify "Explicit Intent" (e.g., Year)
            
            year_match = re.search(r'\b(19|20)\d{2}\b', query)
            target_year = year_match.group(0) if year_match else None
            
            keywords = [w.lower() for w in query.split() if len(w) > 1]
            
            for r in results:
                # Base Vector Score (1.0 - Distance)
                dist = r.get('_distance', 0.0)
                
                # FIX: LanceDB Cosine Distance ranges from 0 (Same) to 2 (Opposite).
                # Unrelated items hover around 1.0.
                # We map [0, 2] -> [1, 0]
                vector_score = 1.0 - (dist / 2.0)
                
                # print(f"DEBUG: Candidate {r['id']} - Dist: {dist:.4f}, VecScore: {vector_score:.4f}")

                # Filter meaningless matches
                # With dynamic weighting, we might want to be lenient if keyword matches strongly
                # But kept 0.4 safety
                if vector_score < 0.4 and alpha_vector > 0.5: 
                    # Only filter strict vector score if we are relying on vector
                    # If we depend on keyword (alpha=0.1), let it pass if vector low
                    pass
                    # continue 

                # Keyword Score
                keyword_matches = 0
                text_lower = r["text"].lower()
                for kw in keywords:
                    if kw in text_lower:
                        keyword_matches += 1
                
                # Normalize Keyword Score (0.0 to 1.0) - Cap at 1.0
                keyword_score = min(keyword_matches * 0.3, 1.0)
                
                # Year Boost (Hard Constraint Simulation)
                year_boost = 0.0
                if target_year and target_year in r.get("date", ""):
                    year_boost = 0.5 # Massive boost for correct year
                
                # Final Hybrid Score (Dynamic)
                hybrid_score = (vector_score * alpha_vector) + (keyword_score * (1.0 - alpha_vector)) + year_boost
                
                # Flatten metadata
                meta = {
                    "date": r["date"],
                    "location": r["location"],
                    "media_type": r["media_type"],
                    "image_url": r["image_url"]
                }
                
                hits.append({
                    "id": r["id"],
                    "score": hybrid_score,
                    "text": r["text"],
                    "metadata": meta,
                    "_debug_vec": vector_score,
                    "_debug_kw": keyword_score
                })
                
            # 3. Re-Rank and Slice
            hits.sort(key=lambda x: x["score"], reverse=True)
            return hits[:k]
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
            
    def get_embeddings(self, ids: List[str]) -> Dict[str, List[float]]:
        # Not easily efficient in LanceDB without scanning or filtering
        # But we can query.
        if not ids: return {}
        try:
            # Filter query
            # id in ...
            # safe string construction
            id_str = ", ".join([f"'{x}'" for x in ids])
            results = self.table.search().where(f"id IN ({id_str})").to_list()
            
            embed_map = {}
            for r in results:
                embed_map[str(r["id"])] = r["vector"]
            return embed_map
        except Exception as e:
            return {}

class Indexer:
    @staticmethod
    def index_all():
        db = SessionLocal()
        vector_store = MemoryVectorStore()
        try:
            events = db.query(models.TimelineEvent).all()
            print(f"📚 Found {len(events)} total events in DB.")
            
            chunk_size = 50
            for i in range(0, len(events), chunk_size):
                chunk = events[i : i + chunk_size]
                vector_store.add_events(chunk)
        finally:
            db.close()

# Singleton
memory_vector_store = MemoryVectorStore()

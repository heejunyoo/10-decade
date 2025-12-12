
import os
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import models
from database import SessionLocal
from typing import List, Dict, Any

# Path for local vector DB
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "decade_memories"

class Embedder:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            print("🧠 Loading Embedding Model (paraphrase-multilingual-MiniLM-L12-v2)...")
            # Use Multilingual model for better Korean support
            cls._model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        return cls._model

    @classmethod
    def embed_text(cls, texts: List[str]) -> List[List[float]]:
        model = cls.get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()

class MemoryVectorStore:
    def __init__(self):
        # Ensure directory exists
        if not os.path.exists(CHROMA_DB_PATH):
            os.makedirs(CHROMA_DB_PATH)
            
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        # We use manual embedding via 'Embedder' class to control the model and avoid redundant loading.
        
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"} # Cosine similarity
        )

    def add_events(self, events: List[models.TimelineEvent]):
        """
        Embeds and upserts events.
        """
        ids = []
        documents = []
        metadatas = []
        
        for event in events:
            # Construct rich context string
            # Format: "Date: YYYY-MM-DD. Location: Seoul. Weather: Sunny. Content: ..."
            parts = [f"Date: {event.date}"]
            
            if event.location_name:
                parts.append(f"Location: {event.location_name}")
            
            if event.weather_info:
                parts.append(f"Weather: {event.weather_info}")
                
            if event.title:
                parts.append(f"Title: {event.title}")
                
            # Content priority: Caption (Summary) > Description
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
            
            ids.append(str(event.id))
            documents.append(text)
            
            # Metadata for filtering/retrieval
            meta = {
                "date": event.date or "",
                "location": event.location_name or "",
                "media_type": event.media_type,
                "image_url": event.image_url or ""
            }
            metadatas.append(meta)
        
        if not ids:
            return

        # Generate Embeddings
        print(f"🧮 Embedding {len(documents)} memories...")
        embeddings = Embedder.embed_text(documents)
        
        # Upsert
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        print(f"✅ Indexed {len(ids)} memories.")

    def update_photo_index(self, event_id: int):
        """
        Live Re-Indexing for a single photo.
        Used when user edits caption/tags manually.
        """
        db = SessionLocal()
        try:
            event = db.query(models.TimelineEvent).filter(models.TimelineEvent.id == event_id).first()
            if not event:
                return
            
            # Reuse logic
            self.add_events([event])
            print(f"🔄 Memory {event_id} re-indexed successfully.")
            
        finally:
            db.close()

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        print(f"🔍 Searching for: {query}")
        query_embedding = Embedder.embed_text([query])
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=k
        )
        
        # Default empty structure if no results
        if not results['ids']:
            return []

        # Refine structure & Filter by Threshold
        hits = []
        THRESHOLD = 0.75  # Stricter filter (Lower is better for Cosine Distance)
        
        for i in range(len(results['ids'][0])):
            score = results['distances'][0][i] if 'distances' in results else 1.0
            
            # Filter out weak matches
            if score > THRESHOLD:
                continue
                
            hits.append({
                "id": results['ids'][0][i],
                "score": score,
                "text": results['documents'][0][i],
                "metadata": results['metadatas'][0][i]
            })
            
        return hits
            
    def get_embeddings(self, ids: List[str]) -> Dict[str, List[float]]:
        """
        Retrieves embeddings for specific IDs.
        Returns a dict mapping ID -> Embedding.
        """
        if not ids:
            return {}
            
        try:
            results = self.collection.get(
                ids=ids,
                include=["embeddings"]
            )
            
            embedding_map = {}
            if results and results.get('ids'):
                ids_list = results['ids']
                embeddings_list = results.get('embeddings')
                
                for i, id_val in enumerate(ids_list):
                    if embeddings_list is not None:
                        # Ensure we don't index out of bounds (though IDs and Embeddings should match)
                        if i < len(embeddings_list):
                             embedding_map[id_val] = embeddings_list[i]
            
            return embedding_map
        except Exception as e:
            print(f"⚠️ Failed to fetch embeddings: {e}")
            return {}

class Indexer:
    @staticmethod
    def index_all():
        db = SessionLocal()
        vector_store = MemoryVectorStore()
        try:
            # Fetch all events with some text/data worth indexing
            # Basically everything except completely empty ones?
            # Or just all.
            events = db.query(models.TimelineEvent).all()
            print(f"📚 Found {len(events)} total events in DB.")
            
            # Batch process? For 200 items, one batch is fine.
            # Use chunks if large.
            chunk_size = 50
            for i in range(0, len(events), chunk_size):
                chunk = events[i : i + chunk_size]
                vector_store.add_events(chunk)
                
        finally:
            db.close()

# Singleton
memory_vector_store = MemoryVectorStore()

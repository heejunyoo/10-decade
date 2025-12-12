# Technical Manual: The Decade Journey

## 1. System Architecture

The system follows a typical **Service-Repository** pattern implemented in FastAPI. Controllers (`routers/`) delegate business logic to (`services/`), which interact with `models.py` (SQLAlchemy) and `chromadb` (Vector Store).

### 🏛️ High-Level Diagram
```mermaid
graph TD
    Client[Web Client (PWA)] --> API[FastAPI Entrypoint]
    
    subgraph Core Services
        API --> Timeline[Timeline Service]
        API --> Faces[Face Service]
        API --> Search[RAG Search Service]
        API --> Map[Map Service]
    end
    
    subgraph Data Layer
        Timeline --> SQLite[SQLite (Metadata)]
        Search --> Chroma[ChromaDB (Vectors)]
        Faces --> InsightFace[InsightFace Engine]
    end
    
    subgraph AI Pipeline
        Timeline --> Analyzer[Image Analyzer]
        Analyzer --> Florence[Florence-2 (Local Vision)]
        Analyzer --> Gemini[Gemini (Cloud Vision)]
        Analyzer --> Translator[Google Translate API]
        Faces --> DeepFace[DeepFace (Emotion)]
    end
```

---

## 2. AI Pipelines & Logic

### 👁️ Image Analysis Pipeline (`services/analyzer.py`)
This pipeline triggers automatically on file upload (via background worker).

1.  **Ingestion:** Image is loaded and converted to RGB.
2.  **Face Context:** `Face Service` injects detected names (e.g., "Dad", "Mom") into the prompt context.
3.  **Vision Inference:**
    *   **Mode A (Local):** `Florence-2-base` generates a dense caption and tagging.
    *   **Mode B (Gemini):** If configured, `Gemini Pro` generates a warm, narrative caption including "Mood" and "Atmosphere".
4.  **Translation:** The English caption is translated to Korean using `deep-translator`.
5.  **Metadata Save:** Tags, Caption, and Translation are stored in `TimelineEvent`.

### 👤 Face Recognition & Emotion (`services/faces.py`)
A hybrid approach is used for maximum accuracy and depth.

1.  **Detection:** `InsightFace` (`buffalo_l`) locates faces and generates 512D embeddings.
2.  **Identification:**
    *   Embeddings are compared against `models.Face` using Cosine Similarity.
    *   **Threshold:** `0.5` (Configurable).
3.  **Emotion Extraction:**
    *   Detected face crops are passed to `DeepFace`.
    *   `DeepFace.analyze(actions=['emotion'])` determines the dominant expression (Happy, Sad, etc.).
4.  **Clustering:** `get_grouped_unknown_faces` uses greedy clustering to group "Unknown" faces for bulk labeling.

### 🔍 RAG Search (`services/rag.py`)
Search is not keyword-based but concept-based.

1.  **Context Building:**
    *   Text blob = `Date` + `Location` + `Weather` + `Caption` + `People Names` + `Emotions` + `Mood`.
2.  **Embedding:** `Sentence-Transformers (MiniLM-L12)` converts the blob to a vector.
3.  **Indexing:** Vectors are stored in `ChromaDB`.
4.  **Query:** User query is embedding -> Cosine Search in ChromaDB -> Top K Results returned.

---

## 3. Data Flow & Schema

### Database Schema (`models.py`)
*   **TimelineEvent:** The central entity.
    *   `media_type`: 'photo' or 'video'.
    *   `file_hash` / `phash`: Perceptual hash for duplicate detection.
    *   `stack_id`: For grouping burst shots (Stacking logic).
*   **Face:** A specific instance of a face in a photo.
    *   `encoding`: Binary blob (pickle).
    *   `emotion`: String (e.g., "happy").
*   **MemoryInteraction:** Stores the "Daily Interview" Q&A linked to an event.

### Initialization & Safety
*   **Startup:** `main.py` -> `lifespan` -> `preload_models.preload()`.
*   **Mutex Safety:** On macOS, global environment variables (`OMP_NUM_THREADS=1`, `TOKENIZERS_PARALLELISM=false`) are forced to prevent `libc++abi` crashes.
*   **Fallbacks:** `GeminiService` automatically degrades from Pro to Flash if Rate Limits (429) are hit. `Analyzer` falls back to `deep-translator` logic if local models fail.

---

## 4. Troubleshooting

### Common Issues
1.  **"Mutex Lock Failed" Crash (macOS)**
    *   *Cause:* Conflict between `sentencepiece` (C++) and Python's `fork` mechanism in `uvicorn --reload`.
    *   *Fix:* The project strictly disables tokenizer parallelism and forces `deep-translator` for translation to avoid the crashing library entirely.

2.  **Face Indexing Stuck**
    *   *Cause:* Corrupt `status.json` or process termination.
    *   *Fix:* Delete `indexing_status.json` manually if the UI is stuck in "Indexing...".

3.  **Gemini API Errors**
    *   *Check:* Ensure `GEMINI_API_KEY` is valid in `.env`.
    *   *Logs:* Check `system_logs` table via Admin UI for specific API error codes.

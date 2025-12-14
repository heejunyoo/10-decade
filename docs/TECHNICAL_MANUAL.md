# ⚙️ Technical Manual

This document details the internal architecture, data flows, and subsystem implementations of **The Decade Journey**.

---

## 1. System Architecture

The application follows a **Modular Monolith** architecture powered by **FastAPI**.

### Core Layers
1.  **Presentation Layer**: Jinja2 Templates + HTMX/Vanilla JS.
2.  **API Layer (`routers/`)**: RESTful endpoints separated by domain (Timeline, Memories, Chat, etc.).
3.  **Service Layer (`services/`)**:
    *   **AI Service**: Orchestrates LLM generation (Local vs Cloud).
    *   **Task Queue**: Asynchronous background processing via `huey`.
    *   **RAG Engine**: Vector embedding and retrieval logic.
4.  **Data Layer**:
    *   **SQLite (`decade.db`)**: Relational data (Events, People, Settings).
    *   **LanceDB (`lancedb_data`)**: Vector embeddings for search.
    *   **Filesystem (`static/uploads`)**: Raw media storage.

---

## 2. Asynchronous Processing (Huey)

To prevent blocking the main thread during heavy AI operations, the system uses **Huey** with a simple SQLite backend.

### The Pipeline (`services/tasks.py`)
When a user uploads a photo/video:
1.  **Synchronous**: File is saved, `TimelineEvent` created (orphaned state), basic EXIF data extracted.
2.  **Enqueue**: `process_ai_for_event` task is pushed to Huey.
3.  **Asynchronous Worker**:
    *   **Step 1: Face Analysis**: InsightFace detects faces, encodes them (128d), and matches against known clusters (`services/faces.py`).
    *   **Step 2: Vision Analysis**: Image is analyzed for visual description (Captioning).
    *   **Step 3: Embedding**: Text metadata is embedded (Sentence-Transformers) and stored in LanceDB (`services/rag.py`).
    *   **Step 4: Completion**: Event is marked as fully processed.

### Self-Healing
*   **Orphan Rescue**: On app startup (`main.py`), `services.tasks.reprocess_orphans()` scans for events stuck in "processing" state (e.g., due to crash) and re-queues them.

---

## 3. AI Subsystems

### A. Local LLM Manager (`services/ollama_manager.py`)
*   **Dynamic Model Selection**: Automatically detects available Ollama models.
*   **Priority Logic**: Prefers `llama3.1:8b` > `gemma2:9b` > `llama3.2:3b`.
*   **Lifecycle Management**: Can auto-start the Ollama service process if down.

### B. Face Recognition Pipeline
1.  **Detection**: Returns bounding boxes for all faces.
2.  **Encoding**: Generates 128-dimensional encodings.
3.  **Clustering**: Uses a distance threshold (`FACE_SIMILARITY_THRESHOLD` in `config.py`) to group similar faces.
4.  **Entity Resolution**: "Unknown" clusters can be merged into named "Person" entities.

### C. RAG (Retrieval Augmented Generation)
*   **Vector DB**: LanceDB (Serverless, local file-based).
*   **Embedding Model**: `BAAI/bge-m3` or similar high-performance multilingual model.
*   **Hybrid Search**:
    *   Combines **Vector Similarity** (Semantic) + **Keyword Matching** (Exact).
    *   Used in "Memory Assistant" chat to provide context-aware answers.

---

## 4. Stability & Safety

### AI Hallucination Guard (`services/ai_service.py`)
*   **Problem**: Small local models (3B) sometimes hallucinate in foreign languages (Thai, Russian, etc.) when prompted in Korean.
*   **Solution**: `_is_contaminated()` validator.
    *   Regex blocklist for non-Korean/English scripts.
    *   **Retry Loop**: Automatically retries generation up to 3 times if contamination is detected.
    *   **Fallback**: Returns a safe, pre-defined template if all attempts fail.

### Configuration (`services/config.py`)
*   **Hierarchy**: Database Settings > Environment Variables > Defaults.
*   **Hot-Swapping**: Changing settings in the UI immediately updates the in-memory config cache.

---

## 5. Database Schema (Key Models)

*   **TimelineEvent**: The core unit. Contains `date`, `file_hash`, `summary` (AI caption), `stack_id` (burst mode grouping).
*   **Person**: A named identity.
*   **Face**: A detected face instance linking `Person` -> `TimelineEvent`.
*   **MemoryInteraction**: User Q&A data (Daily Interview responses).
*   **TimeCapsule**: Messages stored for future delivery.

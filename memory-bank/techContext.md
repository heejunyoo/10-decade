# Technology Context

## Core Stack
*   **Language**: Python 3.10+
*   **Web Framework**: `FastAPI` (ASGI)
*   **Server**: `Uvicorn`
*   **Database**: `SQLAlchemy` (ORM) + `SQLite` (File-based)

## AI & Machine Learning
### 1. Vision (Local)
*   **Model**: Microsoft `Florence-2-large`
*   **Library**: `transformers` (HuggingFace)
*   **Hardware Compatibility**: Optimized for CPU (AVX2) / Mac MPS.

### 2. Face Recognition
*   **Library**: `InsightFace` (Python)
*   **Model Pack**: `buffalo_l` (RetinaFace Detection + ArcFace Embedding)
*   **Runtime**: `ONNXRuntime` (Configured for CPU Execution stability).

### 3. Generative Chat
*   **Local Backend**: `Ollama` (External Process) running `Llama 3.1`.
*   **Cloud Backend**: `Google Generative AI SDK` connected to `Gemini 1.5 Flash/Pro`.

### 4. Search & Retrieval
*   **Vector DB**: `ChromaDB` (Local persistence).
*   **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2`.

## Frontend Architecture
*   **Styling**: `Tailwind CSS` (CDN Integration).
*   **Interactivity**: `Alpine.js` (Client-side state), `HTMX` (Server-side interaction).
*   **Maps**: `Leaflet.js` + `OpenStreetMap` + `MarkerCluster`.
*   **Templates**: `Jinja2` (Server-side rendering).

## Development Environment
*   **Configuration**: `.env` file (managed via `python-dotenv`).
*   **Logging**: Database-backed `SystemLog` table + Standard Console Output.

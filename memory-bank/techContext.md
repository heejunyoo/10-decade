# Technical Context

## Technology Stack

### Core
*   **Language**: Python 3.13
*   **Web Framework**: FastAPI
*   **Template Engine**: Jinja2 (Serverside Rendering)
*   **Database**: 
    *   `SQLite` (Metadata, User Profiles, Settings)
    *   `LanceDB` (Vector Storage - Local & Cloud Embeddings)
    *   `ChromaDB` (Data Persistence - Legacy/Backup)
*   **Task Queue**: Huey (SQLite backend) - Handles async AI processing.

### AI & Machine Learning
*   **Face Recognition**: `InsightFace` (ONNX Runtime)
*   **Vision**: 
    *   Primary: Google Gemini 1.5 Flash/Pro
    *   Secondary: Groq (Llama 3.2 Vision)
    *   Local (Optional): Qwen2-VL-2B-Instruct (via `transformers`)
*   **Chat/Text**: 
    *   Primary: Gemini 1.5 Pro
    *   Secondary: Groq (Llama 3.3 / Mixtral)
    *   Local (Optional): Ollama (Llama 3, Gemma 2)
*   **Embedding**:
    *   Cloud: `models/text-embedding-004` (Gemini)
    *   Local: `BAAI/bge-m3` (SentenceTransformers)

### Frontend
*   **Style**: Vanilla CSS (Variables for theming) + FontAwesome
*   **JS**: Vanilla JS (Masonry Layout, Modals)
*   **PWA**: Manifest support for mobile install

## Development Environment
*   **OS**: macOS (Metal MPS support enabled for Torch)
*   **Virtual Env**: `venv` (Standard)
*   **Dependencies**: 
    *   `requirements.txt`: Core + Cloud AI libs.
    *   `requirements-local.txt`: Heavy local ML libs (`torch`, `transformers`).

## Key Directories
*   `routers/`: API endpoints separated by feature (timeline, chat, faces...)
*   `services/`: Business logic and Singleton services.
*   `templates/`: HTML Jinja2 templates.
*   `static/`: Assets and User Uploads.
*   `lancedb_data/`: Vector database storage.

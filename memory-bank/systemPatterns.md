# System Patterns

## Architecture Overview

The system follows a **Modular Monolith** architecture built on FastAPI. It emphasizes separation of concerns via distinct Services and Routers.

### 1. Service Layer Pattern (Singleton)
Core business logic is encapsulated in singleton services in `services/`.
*   **`ConfigService`**: Centralized configuration management. Loads from DB > Env > Defaults. Thread-safe.
*   **`AIService`**: High-level orchestrator for user-facing AI tasks (Interview, Summary). Facade over specific provider implementations.
*   **`VisionService`**: Handles image analysis. Routes to Gemini, Groq, or Local Analyzer.
*   **`OllamaManager`**: Manages local Ollama process lifecycle (start/stop/check).

### 2. Dual-Brain Search (Hybrid RAG)
Storage and retrieval of memories use a hybrid approach ("Dual Brain").
*   **Indexing**: Every photo is embedded twice:
    1.  **Local Brain**: `BAAI/bge-m3` (Dense, High Precision).
    2.  **Cloud Brain**: Gemini Embedding (Semantic, Broad).
*   **Retrieval**: Uses Reciprocal Rank Fusion (RRF) to combine results from both indices.
*   **Reranking**: Top candidates are optionally reranked by an LLM (Gemini Flash) for context verification.

### 3. Asynchronous Processing (Task Queue)
Heavy AI operations are offloaded to a background worker using **Huey**.
*   **Event Pipeline**: Upload -> Enqueue -> `process_ai_for_event` -> (Face Rec -> Vision -> Context -> RAG).
*   **Isolation**: Worker runs in a separate process, bypassing GIL issues and preventing web server blocking.
*   **Resiliency**: Tasks persist in `decade_ops.db` and retry on failure.

### 4. Switchable AI Provider Strategy
The system supports hot-swapping AI backends without code changes.
*   **Provider Independent**: High-level code calls generic methods (`analyze_image`, `chat_query`).
*   **Fallback Chain**:
    *   **Vision**: Gemini -> Groq -> Local (Qwen).
    *   **Chat**: Gemini -> Groq -> Local (Ollama).
*   **Lazy Loading**: Heavy local libraries (`torch`, `transformers`) are only imported inside the methods that need them, preventing memory bloat when using Cloud modes.

### 5. Frontend-Backend Coupling
*   **Server-Side Rendering (SSR)**: Primary UI is rendered via Jinja2 for SEO and performance on low-end devices.
*   **Hydration**: Vanilla JS attaches to DOM elements for interactivity (Modals, Infinite Scroll).
*   **API-First**: All actions are exposed as REST APIs, used by both SSR forms and JS fetch calls.

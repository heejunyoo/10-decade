
# 🕵️ Decade Journey - Project Analysis & Architecture

## Overview
Decade Journey is a premium personal memory assistant designed to help users relive their past effectively. It moves beyond a simple photo gallery by integrating sophisticated AI for search, storytelling, and "Time Capsule" features.

## 🧠 Hybrid Search Architecture (The "Dual Brain")

To solve the problem of precise retrieval vs. intelligent generation, the system uses a **Dual Brain** architecture enhanced by **Ensemble** and **Reranking**.

### 1. Dual Indexing
Every memory (photo/video) is indexed into two vector spaces:
*   **Local Brain (BGE-M3)**: 
    *   **Model**: `BAAI/bge-m3` (1024 dim)
    *   **Role**: High-precision semantic search. Excellent at understanding specific keywords and Korean context.
    *   **Storage**: LanceDB (`decade_memories_local` table).
*   **Cloud Brain (Gemini)**:
    *   **Model**: `models/text-embedding-004` (768 dim)
    *   **Role**: Broad, conceptual understanding. Good for vague queries like "happy moments".
    *   **Storage**: LanceDB (`decade_memories_gemini` table).

### 2. Ensemble Search (RRF)
When a user searches (e.g., "China Trip"), we do NOT rely on a single brain.
*   **Parallel Query**: The system queries *both* Local and Gemini indices simultaneously.
*   **Fusion**: Results are merged using **Reciprocal Rank Fusion (RRF)**.
    *   Items found by both engines get a massive score boost.
    *   This stabilizes "messy" Gemini results with "precise" Local results.

### 3. Smart Filtering (LLM Reranking) [NEW]
To eliminate "Generic/Sticky" memories (e.g., a photo that matches "happy" but is from the wrong year), we apply a final intelligence layer.
*   **Candidate Generation**: RRF generates a wide pool of ~15 candidates.
*   **LLM Inspection**: We send these candidates + the user's query to **Gemini Flash**.
*   **Reasoning**: The LLM acts as a judge:
    *   *"User asked for 'China'. Candidate #3 is in 'Jeju'. REJECT."*
    *   *"User asked for 'Food'. Candidate #5 is a landscape. REJECT."*
*   **Result**: Only truly relevant memories are returned to the user.

---

## Key Components

### Backend (`services/`)
*   `rag.py`: Implements the `MemoryVectorStore`. now uses **Lazy Loading** for `sentence_transformers` to allow lightweight startup without heavy dependencies.
*   `gemini.py`: Handles interactions with Google Gemini API. Now creates a "Gemini-Native" experience by default.
*   `analyzer.py`: Manages the Qwen2-VL Vision Model. Refactored to **load Torch/Transformers on-demand**. This prevents server crashes in environments where these libraries are missing.
*   `ai_service.py`: Orchestrates high-level AI tasks.

### Frontend
*   `templates/chat_search.html`: The interface for the Memory Assistant.
*   `static/script.js`: Handles Masonry layouts and modals.

## Future Roadmap
*   **Pre-emptive Caching**: To reduce the latency of LLM Reranking (currently ~1-2s).
*   **Emotion Mapping**: Visualizing memories by emotion in the Archive.

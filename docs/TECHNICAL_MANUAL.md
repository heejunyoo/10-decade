# ⚙️ Technical Manual
**The Decade Journey System Architecture & Internals**

---

## 1. System Architecture
The application follows a **Producer-Consumer** pattern to handle heavy AI workloads without blocking the web interface.

### Components
*   **Web Server (`main.py`)**: A FastAPI instance handling HTTP requests, serving HTML templates, and API endpoints.
*   **Task Queue (`Huey`)**: A lightweight persistent task queue (using SQLite) that handles background jobs.
*   **AI Worker (`services/tasks.py`)**: Consumes tasks from Huey to run CPU/GPU-intensive AI operations.
*   **Vector Database (`LanceDB`)**: Embedded vector store for high-performance similarity search.

### Data Flow (Upload -> Analysis)
1.  **Upload**: User uploads file -> Saved to `static/uploads`.
2.  **Queue**: `TimelineEvent` created in DB (Pending state) -> `analyze_image_task` pushed to Huey.
3.  **Process (Worker)**:
    *   **Vision**: `ImageAnalyzer` generates tags, caption, mood.
    *   **Face**: `FaceDetector` extracts encodings and crops faces.
    *   **Embedding**: `MemoryVectorStore` embeds text + metadata into LanceDB.
4.  **Result**: DB updated with AI insights.

---

## 2. Database Schema (`models.py`)

### Core Tables
| Table | Description | Key Fields |
| :--- | :--- | :--- |
| **`timeline_events`** | Main photo/video entry | `image_url`, `date`, `summary`, `tags`, `mood`, `stack_id` |
| **`people`** | Identified individuals | `name`, `cover_photo` |
| **`faces`** | Detected faces in events | `encoding`, `emotion`, `location` |
| **`time_capsules`** | Locked messages | `open_date`, `message`, `is_read` |
| **`memory_interactions`** | Chat Q&A history | `question`, `answer`, `event_id` |

---

## 3. AI Service Implementation

### 👁️ Vision Analysis (`services/vision.py` & `analyzer.py`)
*   **Model**: `Qwen2-VL-2B-Instruct` (Lazy Loaded).
*   **Optimization**:
    *   **Smart Batching**: The model remains loaded for 30 seconds after use. If a new task arrives, the timer resets. This prevents thrashing during bulk uploads.
    *   **Saliency Crop**: Used for generating thumbnails if no faces are found.

### 🔍 Retrieval Augmented Generation (RAG) (`services/rag.py`)
*   **Store**: LanceDB (`./lancedb_data`).
*   **Embedding**: `BAAI/bge-m3` (1024 dimensions).
*   **Hybrid Search Algorithm**:
    1.  Fetch Top-15 candidates via Vector Search.
    2.  Calculate **Hybrid Score**: `(VectorScore * 0.7) + (KeywordMatch * 0.3)`.
    3.  **Boosts**: Strong boost if Query Year matches Metadata Year.
    4.  Return Top-5 re-ranked results.

### 👤 Face Recognition (`services/faces.py`)
*   **Library**: `insightface` (ArcFace model).
*   **Logic**: Detects faces -> Computes encoding -> Updates `Face` table.
*   *(Note: Clustering is handled via `grouping.py` logic combining name assignment).*

---

## 4. Stability & Reliability Features

### 🏥 Self-Healing ("Orphan Rescue")
*   **Location**: `main.py` -> `lifespan`.
*   **Function**: On server startup, scans for events that exist in DB but have no `summary`.
*   **Action**: Automatically re-queues them for analysis. This handles server crashes/power loss during processing.

### 🛡️ Error Handling
*   **Chat Fallback**: If Ollama/Gemini fails, the system returns a polite error message but *still displays the retrieved photos*, ensuring the user gets some value.
*   **Safe Unload**: `analyzer.unload_model()` includes garbage collection and CUDA cache clearing to aggressively reclaim RAM.

---

## 5. Troubleshooting Guide

### 🔴 "Chat is Empty" / Silent Failure
*   **Cause**: OOM (Out of Memory). Running Vision + Chat + Embedding models simultaneously on <16GB RAM.
*   **Fix**: The system now strictly **Unloads Vision** before starting Chat.
*   **Manual Fix**: Running `ollama ps` and killing stuck models.

### 🟡 Slow Upload Processing
*   **Cause**: Cold Start of AI models.
*   **Mitigation**: Smart Batching keeps models warm. The first image takes ~5s, subsequent ones ~0.5s.

### 🟣 Search Returns Zero Results
*   **Cause**: LanceDB cosine distance often exceeds 1.0, causing strict similarity filters to fail.
*   **Fix**: Adjusted formula to `1.0 - (Distance / 2.0)` to normalize [0, 2] range.

# 🌌 The Decade Journey

> **"Your Personal Time Machine."**
> A self-hosted, AI-powered digital legacy system that organizes, analyzes, and preserves your life's memories for the next decade.

**The Decade Journey** is a privacy-first web application designed to archive photos and videos, map them to your life's timeline, and use local AI to rediscover forgotten moments.

---

## 🚀 Key Features (Implemented)

### 📸 Timeline & Archive
*   **visual Timeline**: A scrolling feed of your life, grouped by year and month.
*   **Media Support**: Handles Photos (JPG, PNG, **HEIC**) and Videos (MP4).
*   **Smart Metadata**: Automatically extracts EXIF date, GPS, and device info.
*   **Cinema Mode**: A slideshow experience with ambient background music.

### 🧠 On-Device AI Intelligence
*   **Face Recognition**: Automatically detects and groups faces using **InsightFace**.
    *   *Manage People*: Merge unknown faces, name family members.
*   **Vision Analysis**: AI analyzes every photo to generate:
    *   **Captions**: "A group of friends laughing at a birthday party."
    *   **Searchable Tags**: "sunset, beach, happy, dog".
*   **Local LLM Integration**: Uses **Ollama** (Llama 3, Gemma 2) to run a private AI assistant.
    *   *Dynamic Model Switching*: Supports generic 3B models or powerful 8B+ models.
    *   *Hybrid AI*: Option to switch to **Google Gemini (Cloud)** for higher reasoning content.

### 💬 Memory Assistant
*   **RAG Chatbot**: Chat with your memories. "What did we eat in Jeju Island in 2022?"
    *   Uses **LanceDB** for vector semantic search.
*   **Daily Interview**: The AI acts as a biographer, asking you one question a day about a specific past photo to enrich its story.
*   **Time Capsule**: Write messages to your future self (or family) to be unlocked on a specific date.

### 🗺️ Geospatial Memories
*   **Interactive Map**: View your photos pinned on a global map based on GPS usage.

### 🛡️ Privacy & Stability
*   **100% Self-Hosted**: Your data never leaves your machine (unless you opt-in to Gemini).
*   **Background Processing**: Uses **Huey** task queue for non-blocking uploads and AI analysis.
*   **Self-Healing**: Automatic remediation of "orphaned" (incomplete) database records.

---

## 🛠️ Technology Stack

**Backend**
*   **FastAPI**: High-performance Async Web Framework.
*   **SQLAlchemy**: SQLite ORM for structured metadata.
*   **LanceDB**: Embedded Vector Database for semantic search (RAG).
*   **Huey**: Lightweight task queue (Redis-free, SQLite backend).

**AI & ML**
*   **Ollama**: Local LLM Runner (Interface for Llama 3, Phi, Gemma).
*   **InsightFace**: State-of-the-art Face Analysis.
*   **Sentence-Transformers**: Text Embeddings for RAG.
*   **Pillow / Pillow-HEIF**: Image processing and Apple HEIC conversion.

**Frontend**
*   **Jinja2**: Server-side templating.
*   **Vanilla JS / HTMX**: Dynamic interactions without heavy frameworks.
*   **Tailwind CSS (via CDN)**: Utility-first styling.

---

## 📦 Installation

**Prerequisites**
*   Python 3.10+
*   **Ollama** (Running locally on port 11434)
*   **FFmpeg** (For video processing)

**Setup**
1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Initialize AI Models (Optional, for Local 8B upgrade):
    ```bash
    ./scripts/setup_models.sh
    ```
4.  Run the server:
    ```bash
    uvicorn main:app --reload
    ```
5.  Access at `http://localhost:8000`.

---

## 📂 Project Structure

*   `main.py`: Application entry point and middleware.
*   `services/`: Business logic (AI, Config, Tasks, RAG).
*   `routers/`: API endpoints organized by domain.
*   `templates/`: HTML frontend components.
*   `static/`: Assets (JS, CSS, Uploads).
*   `models.py`: Database schema definitions.

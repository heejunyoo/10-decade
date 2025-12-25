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

### 🧠 Hybrid Intelligence (Local + Cloud)
*   **Face Recognition**: Automatically detects and groups faces using **InsightFace** (Local).
    *   *Manage People*: Merge unknown faces, name family members.
*   **Vision Analysis**: AI analyzes every photo to generate captions and tags.
    *   **Auto-Switching**: Uses **Gemini Flash** for high-speed captioning, automatically falling back to other models on rate limits.
*   **Dual-Search (Ensemble)**: Combines **Local Vector Search (BGE-M3)** with **Gemini Cloud Search** to find memories like "My daughter playing in the snow".
    *   *Results are re-ranked by LLM for maximum relevance.*

### 💬 Memory Assistant
*   **RAG Chatbot**: Chat with your memories. "What did we eat in Jeju Island in 2022?"
*   **Daily Interview**: The AI acts as a biographer, asking you one question a day.
*   **Time Capsule**: Write messages to your future self.

### 🗺️ Geospatial Memories
*   **Interactive Map**: View your photos pinned on a global map.

### 🛡️ Privacy & Stability
*   **100% Self-Hosted Core**: Your source files never leave your machine. Metadata is local.
*   **Resilient AI**: System automatically rotates through available Gemini models (Flash -> Pro) if quotas are hit.
*   **Self-Healing**: Automatic remediation of "orphaned" tasks on restart.

---

## 🛠️ Technology Stack

**Backend**
*   **FastAPI**: High-performance Async Web Framework.
*   **SQLAlchemy**: SQLite ORM.
*   **LanceDB**: Hybrid Vector Database (Local + Cloud Embeddings).
*   **Huey**: Lightweight task queue.

**AI & ML (Hybrid Architecture)**
*   **Google Gemini (Default)**: Handles Chat, Vision, and Reasoning via Cloud API. Lightweight & Fast.
*   **Local Models (On-Demand)**:
    *   **InsightFace**: Always-on, lightweight CPU face recognition.
    *   **Ollama / Qwen2-VL / BGE-M3**: Heavy local models are **Lazy Loaded**. They consume 0 RAM until you explicitly enable "Local Mode" in Settings.

---

## ☁️ Cloud-Native Deployment Ready
This project is designed with a **"Gemini First"** philosophy to enable easy deployment on low-cost cloud servers (VPS).

*   **Lightweight Startup**: The server starts in "Gemini Mode" by default, requiring minimal RAM (<500MB).
*   **No GPU Required**: Heavy libraries like `Torch`, `Transformers`, and `DeepFace` are only loaded if you toggle "Local Mode". If they are missing, the system gracefully stays in Cloud Mode.
*   **Privacy**: Even in Cloud Mode, Face Recognition (`InsightFace`) runs locally on the CPU to ensure biometric data privacy.

---

## 📦 Installation
There are two ways to run The Decade Journey: **Docker** or **Local Python**.

### Configuration (Crucial)
Before running, create a `.env` file in the root directory:
```bash
cp .env.example .env
```
Edit `.env` to add your keys:
*   `GEMINI_API_KEY`: Required for Cloud Search & Advanced Vision.
*   `OLLAMA_BASE_URL`: (Optional) Defaults to http://localhost:11434.

### Option 1: Docker (Recommended)
No dependency hell. Just run it.

1.  **Prerequisites**:
    *   Docker & Docker Compose installed.

    *   **Ollama** (Optional): Only required if you plan to use "Local Mode". Not needed for Gemini.

2.  **Run**:
    ```bash
    docker-compose up -d --build
    ```
    *   Access at: `http://localhost:8000`

### Option 2: Local Python
For developers.

1.  **Setup**:
    ```bash
    # Create Virtual Env
    python -m venv venv
    source venv/bin/activate

    # Install Deps
    # Install Core Dependencies (Gemini Mode - Lightweight)
    pip install -r requirements.txt

    # (Optional) Install Local AI Dependencies (For Local Mode)
    # Required for: Qwen2-VL, BGE-M3, DeepFace
    pip install -r requirements-local.txt
    ```
3.  **Run**:
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

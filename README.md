# The Decade Journey (2015-2025)

> **"A digital time capsule for 10 years of cherished memories."**

**The Decade Journey** is a self-hosted, AI-powered memory vault designed to organize, analyze, and celebrate family photos and videos. It combines local AI models for privacy and speed with cloud AI for rich narratives, offering a premium "Google Photos" alternative running entirely on your own hardware (optimized for Apple Silicon).

---

## 🏗️ Dynamic Tech Stack

This project is built on a **Hybrid AI Architecture**, leveraging the best of local performant models and powerful cloud APIs.

### **Core Backend**
*   **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (High-performance Async Python)
*   **Database:** SQLite (Metadata) + SQLAlchemy (ORM)
*   **Vector Search:** [ChromaDB](https://www.trychroma.com/) (Semantic Search & RAG)
*   **Task Queue:** Custom threaded worker for background processing

### **AI & Machine Learning**
| Component | Technology / Model | Role |
| :--- | :--- | :--- |
| **Face Recognition** | **InsightFace** (`buffalo_l`) | State-of-the-art face detection & identification. |
| **Emotion Analysis** | **DeepFace** | Analyzing facial expressions (Happy, Sad, Surprise, etc.) from cropped faces. |
| **Vision (Local)** | **Florence-2** (`microsoft/Florence-2-base`) | On-device image tagging & captioning (MPS Accelerated). |
| **Vision (Cloud)** | **Google Gemini** (Pro/Flash) | Generating warm, narrative-style captions and "Mood" analysis. |
| **Translation** | **Deep Translator** (Google API) | Real-time English-to-Korean translation of AI captions. |
| **Embeddings** | **Sentence-Transformers** (`MiniLM-L12`) | Multilingual vector embeddings for semantic search. |

### **Frontend & UI**
*   **Templating:** Jinja2 (Server-Side Rendering)
*   **Styling:** Vanilla CSS (Premium "Glassmorphism" Design, Responsive Grid)
*   **Interactivity:** Vanilla JS + [Leaflet.js](https://leafletjs.com/) (Maps)
*   **PWA:** Support for "Add to Home Screen" on iOS/Android.

---

## ✨ Key Features

### 1. 🧠 Intelligent Memory Analysis
*   **Hybrid Captioning:** Automatically generates detailed descriptions using Florence-2 (Local) or upgrades to Gemini (Cloud) for storytelling.
*   **Semantic Search:** Search memories by concept ("Playing in the snow with Dad") rather than just keywords, powered by RAG (Retrieval-Augmented Generation).
*   **Emotion & Mood:** Detects dominant emotions (e.g., "Dad 😄") and atmospheric mood (e.g., "Nostalgic") for every photo.

### 2. 👥 Advanced People Management
*   **Face Clustering:** Automatically groups "Unknown" faces.
*   **Interactive Merging:** Review and merge face clusters with a single click.
*   **Profile Integration:** Link faces to family profiles (e.g., "Mom", "Dad") to auto-tag standard roles.

### 3. 🗺️ Spatio-Temporal Journey
*   **Interactive Map:** View all photos on a global map (Exif GPS extraction). Includes specific cluster views.
*   **Timeline View:** A fluid, infinite-scroll masonry grid of all memories.
*   **"On This Day":** Rediscover what happened on today's date in previous years.

### 4. 💌 Time Capsules & Essays
*   **Digital Time Capsules:** Write messages to the future (e.g., "Open in 2030"). Messages remain locked and encrypted until the target date.
*   **Daily Interview:** The system asks a daily retrospective question (e.g., "What made you smile today?"). Answers are recorded in the timeline.

### 5. 🛡️ Privacy & Performance
*   **Safe Playground:** Validated strictly for **macOS (Apple Silicon)** environments.
*   **Crash Prevention:** Custom mutex handling and thread isolation to prevent common macOS Python layout crashes.
*   **Local-First:** Heaviest tasks (Face, Vector) run locally; Cloud is optional.

---

## 🚀 Getting Started

### Prerequisites
*   macOS (Apple Silicon M1/M2/M3/M4 recommended)
*   Python 3.10+
*   `ffmpeg` (for video thumbnail generation)

### Installation

1.  **Clone & Install Dependencies**
    ```bash
    git clone https://github.com/heejunyoo/decade_journey.git
    cd decade_journey
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configuration (.env)**
    Create a `.env` file based on `.env.example`:
    ```ini
    # AI Configuration
    GEMINI_API_KEY=your_key_here
    
    # App Secrets
    SECRET_KEY=your_secret_key
    ```

3.  **Run the Server**
    ```bash
    python3 main.py
    # Access at http://localhost:8000
    ```

---

## 📂 Project Structure

*   `models.py`: Database schema definitions.
*   `routers/`: API endpoints grouped by feature (timeline, map, people, etc.).
*   `services/`: Core logic engines.
    *   `analyzer.py`: Vision AI & Translation pipeline.
    *   `faces.py`: InsightFace detection & clustering.
    *   `rag.py`: ChromaDB indexing & search.
    *   `gemini.py`: Google AI integration & retry logic.
*   `templates/`: HTML frontend templates.
*   `static/`: CSS, JS, and uploaded media assets.

---
*Generated by Antigravity Agent (Bottom-Up Discovery Mode)*

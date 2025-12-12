# Product Context

## Problem Statement
Modern families generate terabytes of photos, but they become "digital graveyards."
1.  **Context Loss**: We forget *why* a photo was taken or *what* we felt.
2.  **Fragmentation**: Photos are scattered across phones, clouds, and drives.
3.  **Privacy Concerns**: deeply personal moments are stored on Big Tech servers used for ad targeting.
4.  **Passive Storage**: We rarely look back at old photos unless reminded.

## Solution Strategy
**The Decade Journey** transforms passive storage into an **Active Memory System**.

### 1. The "Active" Element
*   **Daily Interview**: The system acts as a journalist, asking questions like "What was making you laugh here?" while the memory is fresh or via "On This Day" triggers.
*   **Time Capsule**: Encourages writing to the future, creating a dialogue across time.

### 2. The "Intelligence" Element
*   **Face Recognition**: Uses `InsightFace` (Industry standard) -> "Show me all photos of Dad."
*   **Scene Understanding**: Uses `Florence-2` / `Gemini` -> "Show me photos of 'Beach' or 'Cake'."

### 3. The "Privacy" Element
*   **Local First**: Primary storage is local disk. Database is SQLite.
*   **Hybrid AI**: Heavy lifting can be done locally (Ollama/Florence) or optionally via Cloud (Gemini) for better reasoning, but strictly opt-in.

## User Experience Goals
*   **Nostalgic & Warm**: UI uses serif fonts and warm seasonal colors (`classic`, `retro` themes).
*   **Zero Friction**: Upload -> Auto-Process. No manual tagging required.
*   **Surprise & Delight**: "Found this memory from 5 years ago" notifications.

# 🧪 QA Manual

This document outlines the test plans to verify the integrity and functionality of **The Decade Journey**.

---

## 1. Core Workflow Testing

### 📸 Media Upload
*   **SCENARIO**: Upload mixed content (JPG, HEIC, MP4).
*   **EXPECTED**:
    1.  UI shows upload progress.
    2.  Files appear effectively immediately in `Timeline` (placeholder data).
    3.  **Background**: Huey logs show "Processing task...".
    4.  **Final**: After ~5-10s, photos update with AI Captions, Tags, and Faces.
    5.  **HEIC**: Must be converted to viewing-compatible JPG automatically.

### 👤 Face Management
*   **SCENARIO**: Merging "Unknown" faces.
*   **STEPS**:
    1.  Go to `Manage > Faces`.
    2.  Find an "Unknown" cluster.
    3.  Rename to "Test Person".
    4.  Find another cluster of the same person. Select "Merge into Existing".
*   **EXPECTED**: Both clusters merge into one "Test Person". All associated timeline events are effectively tagged.

---

## 2. AI Intelligence Testing

### 💬 Memory Assistant (Chat)
*   **SCENARIO**: RAG Retrieval validation.
*   **INPUT**: "What did we eat last Christmas?"
*   **EXPECTED**:
    1.  System searches Vector DB.
    2.  Displays relevant photos alongside the answer.
    3.  Answer acts as a "Biographer" using the retrieved context.

### 📝 Daily Interview
*   **SCENARIO**: Question Generation & Refresh.
*   **STEPS**:
    1.  Check the "Daily Memory" card on Dashboard.
    2.  **Verify**: Question is in polite Korean (no hallucinations).
    3.  **Action**: Click "Refresh" (🔄) button.
    4.  **Expected**: New question generates within specific context (e.g., "Why were you laughing in this photo?") without page reload (HTMX).

### 🚨 Hallucination Guard (Stress Test)
*   **SCENARIO**: Force unstable conditions (if using 3B model).
*   **TEST**: Repeatedly generate questions.
*   **EXPECTED**:
    *   No Chinese/Japanese/Thai characters should appear.
    *   Logs (`system_logs`) should show "Hallucination Detected. Retrying..." if it catches bad output.

---

## 3. Resilience & Stability

### 🔌 Service Interruption
*   **SCENARIO**: Kill server during upload processing.
*   **STEPS**:
    1.  Upload 50 photos.
    2.  Immediately `Ctrl+C` stop the server.
    3.  Restart server.
*   **EXPECTED**:
    *   Server startup logs: "Checking for orphaned events..."
    *   Orphans identified and re-queued.
    *   Processing resumes and completes for all 50 photos.

### 💾 Backup & Restore
*   **SCENARIO**: Run `scripts/backup.sh`.
*   **EXPECTED**:
    *   Creates a `zip` of `uploads/`.
    *   Creates a `sqlite3` backup of `decade.db`.
    *   Creates a copy of `lancedb_data`.
    *   Files saved to `backups/YYYY-MM-DD_...`.

---

## 4. Mobile Responsiveness (PWA)

*   **Viewport**: Test on iPhone (Safari) and Android (Chrome).
*   **Checks**:
    *   "Add to Home Screen" enabled (Manifest.json present).
    *   Status bar color matches theme (`theme-color` meta tag).
    *   Upload button accessible on small screens.
    *   Timeline scrolling is smooth.

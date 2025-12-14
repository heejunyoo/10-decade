# 🧪 QA Manual
**Quality Assurance & Testing Protocols**

---

## 1. Core Functionality Tests

### 📤 Media Upload
| Test Case | Steps | Expected Result |
| :--- | :--- | :--- |
| **Single Photo** | Upload 1 JPG via "Add Memory". | File appears in Timeline. AI tags/summary appear within 10s. |
| **Bulk Upload** | Upload 20 photos at once. | Analysis should process sequentially. **Log should show only 1 "Loading Model" event** (Smart Batching). |
| **Video Upload** | Upload MP4 video. | Video should play. AI should (currently) only analyze the thumbnail or basic metadata. |
| **Camera Capture** | Use "Take Photo" button on Mobile. | Camera opens directly. Captured photo uploads successfully. |

### 📅 Timeline Interaction
| Test Case | Steps | Expected Result |
| :--- | :--- | :--- |
| **Scroll** | Scroll down 100+ items. | Infinite scroll should load smoothly without browser lag. |
| **Cinema Mode** | Click "Cinema Mode". | Fullscreen slideshow starts. Music plays (if enabled). |
| **Detail View** | Click a photo. | Modal opens with Date, Location, AI Summary, and User Description. |

---

## 2. AI Intelligence Tests

### 🔍 Search Quality
| Query Type | Example Query | Expected Behavior |
| :--- | :--- | :--- |
| **Exact Keyword** | "Jeju" | Returns photos with "Jeju" in location or tags. |
| **Semantic** | "People eating happy food" | Returns photos of dining, food, smiling faces (even if "happy" word isn't present). |
| **Hybrid** | "2023 Christmas" | Should strictly prioritize photos from December 2023 over general Christmas photos. |
| **Negative Score** | "asdfqwer" | Should return "No results found" (Zero hits). |

### 💬 Chat Assistant
| Scenario | Action | Expected Result |
| :--- | :--- | :--- |
| **General Query** | "Explain this photo." | AI narrates the photo context using metadata. |
| **Memory Recall** | "When did we go to Paris?" | AI finds "Paris" photos and answers "You went in [Date]...". |
| **Empty Context** | "What is the capital of Mars?" | AI apologizes politely: "I can only answer about your memories." |
| **Politeness** | Any question. | Response uses Honorifics (존댓말) and warm tone. |

---

## 3. Reliability & PWA Tests

### 📱 PWA Experience (Mobile)
*   **Install**: "Add to Home Screen" creates an icon with the gold 'D' logo.
*   **Launch**: Splash screen (`Decade Journey`) appears, then fades to Timeline.
*   **Touch**: Tapping buttons gives visual feedback (scale down) but no gray highlight box.

### 🔄 Self-Healing (Disaster Recovery)
*   **Simulation**:
    1.  Upload 5 photos.
    2.  Check Logs: "Processing 1/5...".
    3.  **Kill Server** (`Ctrl+C`) immediately.
    4.  Restart Server.
*   **Verify**: Logs should say "Found X orphans... Re-queueing". The remaining photos should eventually get summaries.

---

## 4. Performance Benchmarks
*   **Cold Start Search**: < 5 seconds (Model Load).
*   **Warm Search**: < 1 second.
*   **Analysis Speed**: ~3-5 seconds per image (on M1/M2/M3 Mac).

# Active Context

## Current Operational State
**System Status: Stable / Production-Ready**

The system is currently operating with a stabilized architecture. All core modules are verified against the codebase.

### 1. Configuration System
*   **State**: Active.
*   **Behavior**: Enforces a strict hierarchy (`Database` > `.env` > `System Defaults`).
*   **Safety**: "Implicit Local Fallback" is **Disabled**. The system remains **Idle** (no AI load) until a provider is explicitly selected in the `Manage` interface.

### 2. AI & Vision Subsystem
*   **State**: Hybrid (Optimized).
*   **Routing**:
    *   **Gemini (Cloud)**:
        *   **Smart Probe**: Zero-cost setup probe to auto-downgrade (Pro->Flash) if rate-limited.
        *   **Resilience**: `tenacity` based exponential backoff (retry on 429).
    *   **Local (On-Device)**:
        *   **Single-Pass Inference**: Combines Tagging & Captioning into one `Florence-2` call (~50% speedup).
        *   **RAG**: Threshold lowered to 0.6 prevents valid data loss.
*   **Face Recognition**: Powered by `InsightFace` (CPU-optimized).

### 3. Documentation
*   **State**: Synchronized.
*   **Coverage**: `README.md` and `docs/TECHNICAL_MANUAL.md` serve as the sole source of truth, reflecting the actual v3.0.0 codebase.

## Current Focus
*   **Performance Verification**: Validating the speedup from Single-Pass Local Inference.
*   **Integration Testing**: Confirming Gemini Retry logic handles rate limits gracefully.
*   **System Stability**: Ensuring no regression after Data Reset.

## Active Roadmap
*   [ ] User Acceptance Testing (UAT) for "Memory Box" daily question flow.
*   [ ] Verification of "Time Capsule" date locking mechanism.
*   [ ] Potential Future Feature: Video Analysis pipeline integration.

## 🛑 Antigravity Protocol (Strict Compliance)
All tasks must follow this 4-Phase Process:
1.  **Context & Fact Check**: Analyze ANY file before editing. No assumptions.
2.  **Implementation**: Defensive coding (validation, try-except, logging) required.
3.  **Proof of Work (CRITICAL)**: MUST create `tests/verify_{feature}.py` and execute it.
4.  **Sync Documentation**: Update `TECHNICAL_MANUAL.md` immediately after code changes.

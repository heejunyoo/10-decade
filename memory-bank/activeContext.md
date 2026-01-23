# Active Context

## Current Operational State
**System Status: Stable / Production-Ready**

The system is currently operating with a stabilized architecture. All core modules are verified against the codebase.

### 1. Configuration System
*   **State**: Active.
*   **Behavior**: Enforces a strict hierarchy (`Database` > `.env` > `System Defaults`).
*   **Safety**: "Implicit Local Fallback" is **Disabled**. The system remains **Idle** (no AI load) until a provider is explicitly selected in the `Manage` interface.

### 2. AI & Vision Subsystem
*   **State**: Cloud-First (Optimized for Storage).
*   **Routing**:
    *   **Gemini (Primary)**: Default provider. Used for Vision, Chat, and Embedding.
        *   **Smart Probe**: Auto-downgrade (Pro->Flash) if rate-limited.
        *   **Resilience**: `tenacity` based exponential backoff.
    *   **Groq (Secondary)**: Fallback provider. Free tier alternative (Llama 3.2 Vision).
    *   **Local (Optional)**:
        *   **On-Demand**: Models (Qwen, Ollama) are NOT downloaded by default.
        *   **Auto-Fetch**: Triggered only if user explicitly selects 'Local' mode.
        *   **Storage**: Requires ~20GB+ disk space if enabled.
*   **Face Recognition**: Powered by `InsightFace` (CPU-optimized, always local).

### 3. Documentation
*   **State**: Synchronized.
*   **Coverage**: `README.md` and `docs/TECHNICAL_MANUAL.md` serve as the sole source of truth, reflecting the actual v3.0.0 codebase.

## Current Focus
*   **Optimization**: Reducing disk footprint by removing unused local models.
*   **Reliability**: Ensuring consistent AI experience via Gemini/Groq.
*   **Verification**: Validating on-demand download logic for local fallback.

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

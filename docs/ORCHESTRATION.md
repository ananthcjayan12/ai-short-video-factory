# Agent orchestration

The orchestration layer is a capability map, not a vendor map.

```text
structured    narration, Director, QA
audio         master voice
code          prototype builder and bounded prototype repair
browser       Playwright screen recorder
talking_head  real camera / InfiniteTalk adapter
render        HyperFrames / FFmpeg
```

Each route includes:

- primary provider/model;
- timeout;
- retry count;
- compatible fallback provider/model.

Structured agent prompts are written to `_requests/` together with the JSON Schema. Responses must validate through Pydantic before stage code accepts them.

This is important for the Director: an LLM cannot return a scene with a nonexistent renderer or arbitrary timing fields and still advance the pipeline.

## Default strategy

- Narration: Claude Code → Codex fallback.
- Director: Claude Code → Codex fallback.
- Prototype: Codex → Claude Code fallback.
- Prototype repair: independently selectable Codex route; deterministic QA remains the acceptance gate.
- Screen recording: Playwright.
- Talking head: real camera by default; InfiniteTalk optional.
- Graphics: deterministic HyperFrames first.
- Render: HyperFrames → FFmpeg fallback/assembly.
- QA: Codex → Claude fallback.

## Available AI integrations

All provider choices appear in the Factory Desk model map, filtered by the capability of the task.

| Provider | Connection | Capabilities | Authentication |
|---|---|---|---|
| Codex | ChatGPT-authenticated CLI | structured, code | `codex login` |
| Claude Code | CLI | structured, code | Claude CLI login |
| Claude | Anthropic API | structured | `ANTHROPIC_API_KEY` |
| Gemini | Google GenAI API | structured, audio | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| Grok | SuperGrok-authenticated CLI | structured | `grok login` |
| Antigravity | Google-authenticated `agy` CLI | structured | run `agy` and sign in |
| GitHub Copilot | CLI | structured | run `copilot` and sign in |
| Moonshot / Kimi | API | structured | `MOONSHOT_API_KEY` |
| Z.AI | API | structured | `ZAI_API_KEY` |
| ElevenLabs | API | audio | `ELEVENLABS_API_KEY`; `ELEVENLABS_VOICE_ID` is only a fallback |

Copy `.env.example` to `.env`, add only the credentials you need, and install the optional Gemini SDK with `pip install -e ".[ai,dev]"`. API keys are read locally and never written to project artifacts or invocation logs.

Codex and Grok expose reasoning-effort controls in the per-episode model map. A provider is never offered for a task unless its declared capability matches that task. Gemini's text and TTS model catalogs are separated, so an audio model cannot accidentally be assigned to a story task.

`prototype_builder` and `prototype_repair` are separate model routes. After a build, the Factory validates the static entrypoint, DemoJob contracts, and every cue frame at reel and phone viewports. If a check fails, the repair route receives only the validated findings plus a source inventory, edits inside `04_prototype/`, and is rechecked deterministically. Two repair attempts are allowed by default (`SVF_PROTOTYPE_REPAIR_ATTEMPTS`, clamped to 0–3). Every attempt retains its prompt, provider log, Pydantic-validated issue report, before-source copy, and before/after hashes under `_requests/prototype_repairs/`. A model cannot advance a prototype by weakening or bypassing QA.

`graphics_builder` uses the highest-quality structured route by default. Its output must pass both the Pydantic contract and a deterministic storytelling gate covering free-form staging, visual-world evolution, shell variety, action cadence, final-third payoff, review checkpoints, and narration anchors. Every semantic action resolves from an exact Whisper phrase and occurrence, then snaps forward to an integer output frame. The browser renderer runs a deterministic choreography pass at every seek to keep visible actors inside the safe stage and move lower-priority actors out of collisions. A validated browser report checks review frames, action liveness, containment, and unresolved overlap before composition advances. Preview playback samples the master audio clock on every animation frame rather than relying on low-frequency media events. A schema-valid but generic plan receives one bounded re-plan with the measured defect. If the selected AI provider reaches its usage limit, generation stops with a clear error before any new graphics package or preview is compiled. Deterministic graphics are available only when an operator explicitly selects the mock/offline agent.

The `voice_generator` route defaults to manual audio. Route it to `elevenlabs` or `gemini` in the Factory Desk, choose the voice beside the TTS model, then use **Generate voice**. Voice choice is stored per episode. The desk lists all 30 Gemini prebuilt voices and loads every voice available to the configured ElevenLabs account through its paginated voice API.

Native TTS runs in small narration batches. Each paragraph (or deterministic sub-part capped by `SVF_TTS_CHUNK_MAX_CHARS`, 900 by default) is synthesized, normalized to 24 kHz mono PCM WAV, checked for duration, loudness, clipping and audio format, and cached by provider/model/voice/text/settings. Approved chunks live under `02_voice/audio_chunks/<chunk-id>/`; `manifest.json` is the validated assembly contract. Retries reuse valid chunks, while changing the text, model or voice invalidates only the affected cache entries. The lossless WAV assembly inserts `SVF_TTS_CHUNK_PAUSE_SECONDS` between chunks (0.35 seconds by default) and becomes `02_voice/voice_master.wav`.

## Offline profile

The deterministic MockAgent lets CI validate the complete state/contract flow without provider usage. PAIN-001 uses this path by default.

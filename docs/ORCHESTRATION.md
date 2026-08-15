# Agent orchestration

The orchestration layer is a capability map, not a vendor map.

```text
structured    narration, Director, QA
audio         master voice
code          prototype builder
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
| ElevenLabs | API | audio | `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` |

Copy `.env.example` to `.env`, add only the credentials you need, and install the optional Gemini SDK with `pip install -e ".[ai,dev]"`. API keys are read locally and never written to project artifacts or invocation logs.

Codex and Grok expose reasoning-effort controls in the per-episode model map. A provider is never offered for a task unless its declared capability matches that task. Gemini's text and TTS model catalogs are separated, so an audio model cannot accidentally be assigned to a story task.

The `voice_generator` route defaults to manual audio. Route it to `elevenlabs` or `gemini` in the Factory Desk, then use **Generate voice**. The generated file becomes `02_voice/voice_master.wav`; ElevenLabs character timing is retained as `02_voice/voice_alignment.json`.

## Offline profile

The deterministic MockAgent lets CI validate the complete state/contract flow without provider usage. PAIN-001 uses this path by default.

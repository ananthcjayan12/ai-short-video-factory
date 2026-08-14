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

## Offline profile

The deterministic MockAgent lets CI validate the complete state/contract flow without provider usage. PAIN-001 uses this path by default.

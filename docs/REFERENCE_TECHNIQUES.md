# Techniques carried over from the reference production engine

This repo intentionally reuses the *architecture*, not the documentary-specific stages.

| Reference technique | Shorts adaptation |
|---|---|
| Task declares capability | Narration/director/code/browser/talking-head/render tasks declare capabilities |
| Provider/model selected per task | Codex, Claude, Gemini, Grok, Antigravity, Copilot, Kimi, Z.AI, ElevenLabs and local tool routes |
| Primary retry + compatible fallback | Structured routes keep primary/fallback metadata |
| Pydantic JSON contracts | Narration, DirectorPlan, Scene, DemoJob, VoiceMetadata, state |
| Persisted production stages | `00_input` through `10_final` |
| Human review gates | Director approval and final approval remain explicit |
| Asset-scoped retry | Every Playwright demo scene is an independent job/file |
| Deterministic renderer | HyperFrames HTML is generated from approved scene data |
| `hf-seek` recomputation | Composition listens to the same render clock for preview/frames |
| Render lint | HyperFrames lint runs before rendering |
| Resumable render chunks | Shorts are split only at scene boundaries; valid chunks are reused |
| FFprobe/FFmpeg assembly | Chunk validation, concatenation and master-voice mux |
| Fail-soft behavior | Missing presenter/media scenes render explicit placeholders instead of hallucinated assets |
| Offline mock provider | PAIN-001/CI can run without model credits |

The biggest short-form addition is the **Director budget normalizer**. A creative model may propose scenes, but local code controls visual density and presenter cadence before any paid generation/recording starts.

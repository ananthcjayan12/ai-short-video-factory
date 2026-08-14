# AI Short Video Factory

A narration-first, agent-orchestrated production system for 45–60 second AI/business case-study videos.

The project intentionally separates **creative reasoning**, **media/prototype generation**, and **deterministic rendering**:

```text
Pain point / case
      ↓
Narration Writer → Narration QA
      ↓
Voice track = MASTER CLOCK
      ↓
Director Agent → hard budget normalizer → human approval
      ↓
┌───────────────┬────────────────┬──────────────────┐
│ Playwright    │ HyperFrames    │ Talking head     │
│ screen demos  │ diagrams/mgfx  │ real / adapter   │
└───────────────┴────────────────┴──────────────────┘
      ↓
HyperFrames deterministic composition
      ↓
FFmpeg chunk concat + master voice mux
      ↓
QA → human approval → publish
```

This design is adapted from the same production ideas used in the Failure Documentary Engine: capability-routed providers, schema-validated agent outputs, retries/fallbacks, persisted project state, inspectable HyperFrames HTML, `hf-seek` frame state, and resumable render chunks.

## Why this architecture

Do **not** ask one model to “make the whole video.” The model should make bounded decisions and return contracts. Ordinary code should own timing, files, retries, validation, rendering, and approval gates.

The result is easier to repair:

- bad narration → regenerate narration only;
- weak direction → regenerate Director plan only;
- broken prototype → rerun code builder only;
- failed demo clip → rerun one Playwright job;
- missing presenter clip → keep placeholder or import that scene only;
- interrupted render → resume validated chunks.

## Current MVP

The repo includes a complete reference episode for **PAIN-001 — Context-aware receipt-to-job matcher**:

- synthetic receipt/job prototype;
- three scene-specific Playwright recording jobs;
- 10-scene vertical Director plan;
- presenter placeholders that can be replaced scene-by-scene;
- deterministic HyperFrames diagrams for the “three jobs,” context reasoning, and DIY stack;
- narration-first 58-second master timeline;
- technical QA and production budgets.

## Requirements

- Python 3.10+
- Node.js 22+
- FFmpeg + FFprobe
- HyperFrames runtime (pinned in `package.json`)
- Playwright Chromium for automatic screen recording
- optional: authenticated `codex` and/or `claude` CLIs for real agent stages

## Install

```bash
git clone <this-repo>
cd ai-short-video-factory
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm install
npx playwright install chromium
npm run doctor
svf doctor
```

## Fastest working demo

```bash
svf demo pain-001
svf status pain-001
svf qa pain-001
```

This creates:

```text
projects/pain-001/
├── 00_input/
├── 01_narration/
├── 02_voice/
├── 03_director/
├── 04_prototype/
├── 05_asset_jobs/
├── 06_recordings/
├── 07_talking_head/
├── 08_graphics/
├── 09_composition/
├── 10_final/
└── _requests/
```

### Record the prototype automatically

```bash
svf record-demos pain-001
```

The command starts the local prototype server, runs all Playwright scene jobs, saves the `.webm` clips, and attaches them to the approved Director plan.

### Add your real talking-head clips

The reference Director asks for presenter clips in S01, S04, S07 and S10.

```bash
svf import-head pain-001 S01 ~/Videos/pain001-hook.mp4
svf import-head pain-001 S04 ~/Videos/pain001-insight.mp4
svf import-head pain-001 S07 ~/Videos/pain001-trust.mp4
svf import-head pain-001 S10 ~/Videos/pain001-cta.mp4
```

If you do not import them, HyperFrames renders deliberate presenter placeholders so the edit can still be reviewed.

### Render

```bash
svf render-preview pain-001
svf render-final pain-001
```

HyperFrames renders scene-aligned chunks. Existing valid chunks are reused after interruption. FFmpeg concatenates them and muxes the voice track.

## Real agent mode

By default, `svf demo` uses an offline deterministic agent so the architecture can be tested without credits.

For a new episode:

```bash
svf init pain-101 \
  --title "AI freight quote normalizer" \
  --pain "Quotes arrive as PDF, Excel, email and WhatsApp" \
  --industry "Logistics" \
  --role "Freight coordinator"

svf narrate pain-101
# Generate/import your final voice track here
svf import-voice pain-101 ~/voice/pain-101.wav
svf direct pain-101
svf approve-director pain-101
svf prototype-prompt pain-101
svf build-prototype pain-101
```

The real route is configured in `projects/.svf-orchestrator.json`. Copy the example and change provider/model mappings without changing pipeline code.

## Provider / task separation

Capabilities in this repo:

```text
structured · code · audio · browser · talking_head · render
```

Main tasks:

```text
narration_writer
narration_qa
voice_generator
director
director_qa
prototype_builder
screen_recorder
talking_head_generator
graphics_builder
composition_renderer
final_qc
```

A task can only be assigned to a provider advertising the required capability.

## Director safety budgets

The Director is creative, but the pipeline is strict. The deterministic normalizer enforces limits such as:

- presenter-led hook;
- presenter-led close;
- maximum meaningful visual moments;
- maximum generated assets;
- maximum scene duration;
- maximum uninterrupted time without the presenter.

If a plan exceeds the budget, the system fails soft to a talking-head beat rather than automatically generating an expensive or incoherent asset batch.

## Screen recordings

Each screen-recording scene gets an independent JSON job:

```json
{
  "job_id": "demo-match",
  "scene_id": "S06",
  "url": "http://127.0.0.1:4173/index.html",
  "output_path": "06_recordings/S06-match.webm",
  "actions": [
    {"action": "click", "selector": "[data-testid='receive-receipt']"},
    {"action": "click", "selector": "[data-testid='find-job']"},
    {"action": "assert_text", "selector": "[data-testid='match-result']", "value": "94% confidence"}
  ]
}
```

This is intentionally deterministic: the same demo can be recorded again without a human moving a mouse.

## HyperFrames contract

The Python composition compiler writes ordinary HTML. Every scene is a `.clip` with `data-start` and `data-duration`. The page listens to `hf-seek` and recomputes scene state from the render clock. That means browser preview and frame rendering use the same timeline semantics.

## Talking head / InfiniteTalk

Real-camera talking head is the safest default because your face is part of the channel brand. An `infinite_talk` provider slot is included, but intentionally unconfigured. Add its command template in `.svf-orchestrator.json` if you want an avatar/talking-head generator for selected scenes.

Recommended editorial policy:

- hook: real face;
- one insight/trust beat: real face;
- CTA: real face;
- optional middle presenter beat: InfiniteTalk only if the result is convincingly natural.

## Next implementation layers

This MVP intentionally leaves these as adapters instead of hard-coding vendors:

1. TTS provider implementation (ElevenLabs/HeyGen/other).
2. InfiniteTalk command adapter details.
3. auto-generated Playwright plans for arbitrary prototypes.
4. final visual QA using a vision-capable model.
5. YouTube/Instagram publishing after explicit approval.

The pipeline contracts already have slots for these, so adding them does not require redesigning the project.

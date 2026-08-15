# AI Short Video Factory

A narration-first, agent-orchestrated production system for 45–60 second AI/business case-study videos.

The project intentionally separates **creative reasoning**, **media/prototype generation**, and **deterministic rendering**:

```text
Pain point / verified claims
      ↓
Story Structure → Narration Writer → Narration QA
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

- weak narration → inspect its story spine and quality report, then regenerate narration only;
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
- optional: authenticated Codex, Claude, Grok, Antigravity or Copilot CLIs
- optional: Anthropic, Gemini, Moonshot/Kimi or Z.AI API keys for structured stages
- optional: ElevenLabs or Gemini credentials for generated master voice

## Install

```bash
git clone <this-repo>
cd ai-short-video-factory
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[ai,dev]"
npm install
npx playwright install chromium
npm run doctor
svf doctor
```

## Factory Desk UI

The local Factory Desk puts the production workflow behind a visual interface while keeping the same schema validation, capability routing and approval gates as the CLI.

```bash
nvm use
source .venv/bin/activate
svf ui
```

Then open [http://127.0.0.1:8787](http://127.0.0.1:8787). From the desk you can:

- create and switch between episode workspaces;
- generate narration and voice timing tracks;
- review and explicitly approve Director plans;
- build portrait-first prototypes whose visual reveals follow Whisper word timestamps, run cue-by-cue reel/phone QA, record deterministic demos and attach presenter clips;
- build and scrub the complete browser timeline before rendering, then run QA, render previews/finals and explicitly approve the final video;
- inspect provider readiness and queued production work;
- route every task to a compatible provider/model per episode;
- inspect retained prompts, schemas, responses and invocation records;
- stop durable jobs safely and recover after a UI restart;
- archive a stage and rebuild it without destroying the prior version.

For the complete workflow, see [Creating a New Video](docs/CREATING_A_VIDEO.md).

The UI binds to localhost by default because it controls local files and production tools. Publishing still requires a separate operator-approved step.

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
├── _requests/
└── _control/
```

### Record the prototype automatically

```bash
svf record-demos pain-001
```

The command starts the local prototype server, drives each prototype scene from its validated Whisper-anchored cue timeline, trims loading preroll, saves the `.webm` clips, and attaches them to the approved Director plan.

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
svf prepare-preview pain-001
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
svf align-voice pain-101
svf direct pain-101
svf approve-director pain-101
svf prototype-prompt pain-101
svf build-prototype pain-101
```

The real route is configured in `projects/.svf-orchestrator.json`, or per episode in the Factory Desk. Copy `.env.example` for API/TTS credentials, then change provider/model mappings without changing pipeline code. See [Agent orchestration](docs/ORCHESTRATION.md) for the complete provider catalog.

## Provider / task separation

Capabilities in this repo:

```text
structured · code · audio · browser · talking_head · render
```

Main tasks:

```text
story_structure
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

Before rendering, the graphics builder creates a validated editorial scene/object/action plan plus individual inspectable scene HTML files and a master graphics preview under `08_graphics/`. The composition compiler then creates a complete, voice-timed interactive preview under `09_composition/preview/`; run `svf prepare-preview <episode-id>` to refresh it without rendering an MP4. Every scene is a `.clip` with `data-start` and `data-duration`. The page listens to `hf-seek` and recomputes scene state from the render clock, so browser preview and frame rendering use the same timeline semantics.

## Talking head / InfiniteTalk

Real-camera talking head is the safest default because your face is part of the channel brand. An `infinite_talk` provider slot is included, but intentionally unconfigured. Add its command template in `.svf-orchestrator.json` if you want an avatar/talking-head generator for selected scenes.

Recommended editorial policy:

- hook: real face;
- one insight/trust beat: real face;
- CTA: real face;
- optional middle presenter beat: InfiniteTalk only if the result is convincingly natural.

## Next implementation layers

This MVP intentionally leaves these as adapters instead of hard-coding vendors:

1. InfiniteTalk command adapter details.
2. auto-generated Playwright plans for arbitrary prototypes.
3. final visual QA using a vision-capable model.
4. YouTube/Instagram publishing after explicit approval.

The pipeline contracts already have slots for these, so adding them does not require redesigning the project.

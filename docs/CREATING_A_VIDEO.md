# Creating a New Video with Factory Desk

This guide covers the complete production path: brief, AI story planning, narration, master voice, direction, synthetic demo assets, recording, rendering, QA, and final operator approval.

The key production rule is simple: **the final narration audio is the master timeline**. AI proposes bounded creative decisions as validated data. Deterministic code owns files, timing, production budgets, recording, rendering, and approval gates.

## 1. Start the local desk

From the repository:

```bash
cd /Users/ananthu/Downloads/ai-short-video-factory
source .venv/bin/activate
nvm use
svf doctor
npm run doctor
svf ui
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787).

This project currently reuses the Python environment already available at `.venv`. The Node dependencies and Chromium installation can also be reused when `npm run doctor` reports them ready. Install only a missing component reported by either doctor command.

If port 8787 is already occupied, the earlier Factory Desk process may still be running. Either open the URL directly or select another port:

```bash
svf ui --port 8788
```

The desk intentionally binds to localhost. It can execute local AI CLIs, browser capture, FFmpeg, and renderers, so it should not be exposed as a public website.

## 2. Create a production brief

Click **New episode** and provide:

- **Episode ID:** a stable lowercase identifier such as `pain-102`.
- **Working title:** the specific transformation or system being demonstrated.
- **Pain point:** the concrete operational problem. Avoid a broad topic such as “AI for logistics.”
- **Industry and viewer role:** enough context for examples and language.
- **Target length:** normally 45–60 seconds.
- **Backend facts:** one verified implementation fact per line.
- **DIY stack:** honest steps a viewer could use for a smaller version.

Example:

```text
Episode ID: pain-102
Title: AI freight quote normalizer
Pain point: Quotes arrive as PDF, Excel, email, and WhatsApp, so coordinators retype every line.
Industry: Logistics
Viewer role: Freight coordinator

Backend facts:
- OCR extracts lanes, weights, currencies, and accessorial charges.
- A reasoning step maps differently named charges to a common vocabulary.
- Deterministic rules convert units, calculate totals, and reject incomplete quotes.

DIY stack:
- Shared email inbox
- n8n workflow
- OCR or vision model
- Normalized Google Sheet
- Manual review queue for uncertain fields
```

Every supplied fact receives a stable claim handle such as `pain-01`, `backend-01`, or `diy-01`. AI outputs may reference only those handles. This prevents an attractive script from silently inventing production claims.

Equivalent CLI command:

```bash
svf init pain-102 \
  --title "AI freight quote normalizer" \
  --pain "Quotes arrive in incompatible formats, so coordinators retype every line" \
  --industry "Logistics" \
  --role "Freight coordinator"
```

For the richer backend and DIY lists, use the UI or edit `projects/pain-102/00_input/episode_brief.json` while it still validates as an `EpisodeBrief`.

## 3. Choose task-specific models

Open **Model orchestration** in the episode workspace. Every row is an independent task and declares a required capability:

| Group | Typical task | Capability | Default role |
|---|---|---|---|
| Story | Story structure | structured | Creates the factual story beats |
| Story | Narration writer | structured | Writes the spoken script from those beats |
| Audio | Voice generator | audio | Creates or imports the master voice |
| Direction | Director | structured | Maps the voice to visual scenes |
| Assets | Prototype builder | code | Builds a small synthetic working demo |
| Assets | Screen recorder | browser | Captures deterministic demo actions |
| Assembly | Composition renderer | render | Runs HyperFrames and FFmpeg |
| Assembly | Final QC | structured | Reviews the production contract |

The desk shows only providers compatible with a task's capability. Click **Save routing** to write episode-specific overrides to:

```text
projects/<episode-id>/_control/model-map.json
```

Those overrides take precedence over the global `projects/.svf-orchestrator.json`. They do not alter any other episode.

For a zero-cost workflow, use the **Offline Mock** provider for structured tasks. For real production, choose among Codex, Claude CLI/API, Gemini, Grok, Antigravity, Copilot, Moonshot/Kimi, or Z.AI. Codex and Grok rows also expose reasoning effort. Run `svf doctor` to see which local integrations are ready.

## 4. Generate the story and narration

Click **Generate** in Narration. One action performs two required validated AI passes and, when needed, one corrective edit pass:

1. **Story structure** first extracts a grounded `story_spine`: protagonist, recurring moment, operational pain, stakes, initial assumption when actually supplied, turning point, changed workday when supported, and explicit source gaps. It normally creates five substantial beats rather than one beat per feature.
2. **Narration writer** converts that spine and plan into connected spoken paragraphs. It reserves roughly 30–40% for the client pain and turning point, uses episode-specific nouns, and keeps the DIY section and CTA compact.
3. **Story-quality gate** deterministically checks protagonist placement, pain allocation, real-client narrative voice, CTA size, and paragraph integrity. A weak first draft is retained and sent through `narration_qa` for one complete rewrite. A second weak result stops the stage instead of silently advancing to voice generation.

The pipeline writes:

```text
01_narration/story_plan.json
01_narration/narration_draft.json
01_narration/narration_quality.json
01_narration/narration.json
01_narration/narration.txt
_requests/story_structure_prompt.md
_requests/story_structure_schema.json
_requests/story_structure_response.json
_requests/story_structure_invocation.json
_requests/narration_prompt.md
_requests/narration_schema.json
_requests/narration_response.json
_requests/narration_invocation.json
_requests/narration_rewrite_prompt.md        # only when the first draft fails
_requests/narration_rewrite_response.json    # only when the first draft fails
_requests/narration_rewrite_invocation.json  # only when the first draft fails
```

Open **Prompt inspector** to review the exact prompt, JSON Schema, provider/model, status, and validated response for each pass.

To exercise the complete contract without calling an external model, click **Offline draft** or run:

```bash
svf narrate pain-102 --agent mock
```

To generate only the structure:

```bash
svf story pain-102
```

Do not continue if the narration asserts results, customer details, or implementation facts that were not supplied in the brief. Missing story facts are recorded in `story_spine.source_gaps`; correct the brief rather than filling those gaps with plausible fiction.

## 5. Set the master voice timeline

The final spoken audio owns the production duration. There are three paths:

### Import the real voice

Click **Import audio** and choose WAV, MP3, M4A, AAC, or FLAC. From the CLI:

```bash
svf import-voice pain-102 /absolute/path/to/pain-102.wav
```

### Use a configured voice provider

Route `voice_generator` to **ElevenLabs TTS** or **Gemini API + TTS**, choose a voice in the same per-episode routing row, then click **Generate voice** or use:

```bash
svf generate-voice pain-102
```

The native adapter generates narration in paragraph-sized batches, validates each WAV for duration, loudness, clipping and format, and losslessly assembles them into `02_voice/voice_master.wav`. Valid batches are cached under `02_voice/audio_chunks/`, so a failed or interrupted run resumes without paying for already-approved speech. The validated `02_voice/audio_chunks/manifest.json` records the provider, model, voice, source text, cache key, quality result and exact master-timeline position for every batch.

The voice selector exposes all 30 Gemini prebuilt voices. For ElevenLabs it loads every voice available to the configured account using API pagination. The chosen voice is saved with the episode instead of changing a project-wide default. Set credentials in `.env` (copied from `.env.example`); environment voice IDs remain CLI fallbacks. A custom audio CLI is still supported when its media command template creates the same WAV contract. Manual voice remains the safe default.

### Create a development timing track

Click **Timing track** or run:

```bash
svf mock-voice pain-102 --seconds 58
```

This produces silence of the requested length. It is useful for layout and pipeline testing, but it is not final narration.

### Create the word-level master clock

After generating or importing the final spoken voice, run:

```bash
svf align-voice pain-102
```

This always uses local OpenAI Whisper, whichever TTS provider created the audio. It writes validated `02_voice/audio_word_timestamps.json` and `02_voice/audio_timing.json` artifacts. ElevenLabs is used only when selected as the voice generator; its character-alignment response is not used as the production edit clock.

Install the alignment dependency if needed with `pip install -e '.[alignment]'`. Configure the local model with `SVF_WHISPER_MODEL` (default `base.en`) and language with `SVF_WHISPER_LANGUAGE` (default `en`). A silent development timing track cannot be word-aligned.

Changing the final voice after direction invalidates scene timing. Use **Recovery & versions → Voice onward** to archive the old downstream work before rebuilding.

## 6. Direct and approve the visual plan

Click **Direct** after the final voice has been aligned. The production Director refuses missing or stale alignment. It receives:

- the verified brief;
- the validated story structure;
- the narration paragraphs and claim handles;
- the exact voice duration;
- paragraph/beat timing derived from the audio;
- every validated Whisper word start and end.

Scene cuts are deterministically snapped to real word boundaries after the creative plan is budget-normalized. This keeps screen recordings and visual changes synchronized to the phrase being spoken.

### Project-wide talking-head policy

In **Project visual policy**, choose whether talking head is allowed for the entire project. The setting is stored once in `projects/.svf-project.json` and applies to every episode:

- **Allowed** lets the Director use presenter hooks, insight beats, and closes.
- **Disabled** removes presenter scene types and renderers from the Director's choices. Plans use screen recordings, diagrams, UI mockups, B-roll, static designs, and HyperFrames graphics only.

This is enforced after AI generation as well: deterministic code replaces any disallowed presenter scene, presenter upload/generation is blocked, and conflicting plans cannot be approved or rendered. Regenerate an existing Director plan after changing the policy.

The same setting is available from the CLI:

```bash
svf talking-head-policy allowed
svf talking-head-policy disabled
```

Production budgets are also owned by deterministic code. Values returned by an AI cannot relax or accidentally zero those budgets.

The raw plan is validated as `DirectorPlan`, normalized by hard production budgets, and saved as:

```text
03_director/director_plan.raw.json
03_director/director_plan.json
```

The normalizer protects the edit with rules such as a presenter-led hook and close, bounded visual moments, maximum scene duration, and maximum uninterrupted time away from the presenter.

Review the timeline in Factory Desk. When it is acceptable, click **Approve plan**:

```bash
svf approve-director pain-102
```

Approval creates `03_director/director_plan.approved.json`. Asset production should consume only this approved file.

## 7. Build a small synthetic prototype

For screen-recording scenes:

1. Click **Prepare build brief**.
2. Inspect `_requests/prototype_builder_prompt.md`.
3. Click **Build prototype**.

CLI equivalent:

```bash
svf prototype-prompt pain-102
svf build-prototype pain-102
```

The builder treats the prototype as a camera-ready visual asset, not a general application. It designs each approved screen scene around the narration's visual proof and payoff. Director `on_screen_text` is editorial guidance—not a requirement to paste every phrase into the UI. The default composition is a mobile-style 1080×1920 portrait frame that uses the vertical canvas intentionally, while also remaining responsive at 390×844.

Each prototype scene receives the overlapping Whisper words with both absolute and scene-relative times. The builder maps a short exact spoken anchor to every meaningful reveal, highlight, comparison, transformation, or status change. It exposes those mappings as validated `timeline_cues` and implements a seekable `window.__svfSetTime(localSeconds, timelineCues)` clock. This is the same timing model used by the stock-reel scenes: the narration is the master and the visual payoff appears when its corresponding phrase is spoken.

A build is accepted only after deterministic checks confirm that:

- every approved screen-recording scene has exactly one portrait capture contract;
- every capture contract has a scene-duration timeline with cues anchored to exact Whisper phrases;
- each cue time matches its first anchor word and targets a real `data-testid` element;
- the source contains a seekable narration-time animation function and scene-specific state;
- the capture uses the episode's 1080×1920 canvas;
- the prototype has no horizontal overflow or clipped content at reel and phone sizes;
- proof scenes occupy enough of the vertical frame and use legible text and touch targets.

The browser QA seeks to scene start, every spoken cue, and scene end at both viewports. Its validated report is retained at `_requests/prototype_visual_qa.json` with the raw process log beside it. If static, DemoJob, or browser QA fails, the separately routed `prototype_repair` model receives only the measured evidence and current source inventory. It edits the existing prototype at the smallest useful scope, then the Factory reruns every deterministic check. Two attempts are allowed by default; unsuccessful repairs remain blocked.

Each attempt archives the pre-repair source and records its prompt, provider log, validated findings, and before/after hashes under `_requests/prototype_repairs/`. To validate or repair an already-generated prototype without rebuilding it, click **Validate & repair** or run:

```bash
svf repair-prototype pain-102
```

The prototype is evidence for the video, not a fake production system. Never insert private customer data, invented outcomes, or unverified savings figures.

The sandboxed builder writes scene-specific `DemoJob` contracts under `04_prototype/asset_jobs/`. After the builder exits, Factory Desk validates and promotes them into the canonical `05_asset_jobs/` directory. Once Whisper timing exists, screen scenes must include word-anchored `timeline_cues`; a static-state fallback is intentionally rejected because it cannot prove narration synchronization.

## 8. Record screen demos and add presenter clips

Click **Record demos** or run:

```bash
svf record-demos pain-102
```

The worker starts a reusable temporary local prototype server, waits until the port is actually ready, executes each validated browser job in Chromium, and drives the prototype's seekable clock from zero through the Director scene duration. Setup actions run before the clock; explicitly timed assertions run at their requested time; assertions left at zero validate the final cue-dependent state. Text assertions ignore CSS capitalization and normalize whitespace. The recorder trims page-load preroll, saves the narration-length recording in `06_recordings/`, and attaches it to the approved scene plan. Progress is reported job by job.

When the project talking-head policy is enabled, use **Attach clip** for scenes marked `talking_head` or `cta`:

```bash
svf import-head pain-102 S01 /absolute/path/to/hook.mp4
svf import-head pain-102 S04 /absolute/path/to/insight.mp4
svf import-head pain-102 S10 /absolute/path/to/cta.mp4
```

Missing presenter footage fails soft to a deliberate deterministic placeholder so a preview remains possible. It should normally be replaced before final approval.

## 9. Generate and review graphics

After screen recordings are attached, click **Generate graphics** or run:

```bash
svf generate-graphics pain-102
```

The graphics model outputs a validated data contract rather than HTML or edit code. Its editorial grammar uses semantic object types, free-form portrait frames, causal connections, spatial reveals, maps, evidence collage, kinetic type, object transformation, and continuity instead of reducing each scene to a generic card grid. Important actions quote an exact narration anchor and are snapped back to the master word timeline before rendering. Factory Desk then deterministically compiles:

```text
08_graphics/graphics_plan.json
08_graphics/graphics_manifest.json
08_graphics/scenes/<scene-id>.html
08_graphics/master.html
```

This follows the stock-Reel evidence workflow: each graphics scene declares one evolving visual world, opening and payoff states, an optional camera move, free-form object frames, narration-timed actions, a continuity object, and two or three stable review checkpoints. Every non-hold action is verified against an exact consecutive Whisper phrase and starts on the first output frame at or after that word. Scene boundaries are stored as contiguous integer frame windows so fractional-time rounding cannot accumulate. New episodes use 60 fps by default; 24, 30, and 60 fps remain valid per-episode formats.

A hard storytelling gate rejects repeated shells, dashboard/card layouts, static reveal-only scenes, missing final-third payoffs, long unchanged sections, ungrounded narration anchors, and permanently overlapping visual states. After compilation, browser QA seeks every review checkpoint and action window to verify safe-stage containment, resolved object overlap, and observable motion before the timeline preview is accepted. One bounded AI re-plan is allowed. If the selected AI provider's usage limit is exhausted, the job stops before compiling any new graphics or preview and tells the operator to change the provider/model or replenish quota. Deterministic output runs only when the operator explicitly selects mock/offline generation. Open the graphics master to inspect only the designed scenes. The renderer applies the current project's visual theme; reference themes and assets are not copied.

## 10. QA, preview, and final render

Click **Run QA** or use:

```bash
svf qa pain-102
```

First click **Build timeline preview**, or run:

```bash
svf prepare-preview pain-102
```

This is a fast, browser-playable composition under `09_composition/preview/`. It combines the master voice, every screen/presenter recording, deterministic graphics, captions, and exact scene timings. Play it, scrub it, and jump between scenes before spending time rendering frames. Refresh it whenever attached media or graphics change.

Resolve blocking issues, approve the browser timeline, then render an MP4 preview:

```bash
svf render-preview pain-102
```

HyperFrames validates the same composition, renders resumable chunks, and FFmpeg concatenates them and muxes the master voice. Progress reports validation, each chunk, concatenation, and voice muxing. Inspect `10_final/preview.mp4` in the desk.

Every queued or running production job displays a prominent **Terminate job** button. After confirmation, the desk terminates the complete worker process group—including renderer, FFmpeg, browser, and child processes—while preserving completed chunks and artifacts. Resumable render jobs can reuse valid completed chunks when started again.

When the preview is accepted:

```bash
svf render-final pain-102
```

The final file is `10_final/final.mp4`. Rendering it does **not** approve or publish it.

## 10. Explicit final approval

Watch the entire final file with sound. Check:

- spoken claims against the original brief;
- subtitle/readability and safe margins;
- voice/image synchronization;
- demo states and exception handling;
- presenter clip quality;
- the CTA and final frame;
- absence of private or misleading data.

Then click **Approve final video** or run:

```bash
svf approve-final pain-102
```

This changes the episode state to `approved`. Publishing remains a separate operator-controlled action and is intentionally not automatic.

## Job progress, logs, stopping, and restart recovery

Factory Desk runs production actions as subprocesses through a serialized local worker. Every job is written before it starts:

```text
_control/jobs/<job-id>.json
_control/production.log
_control/progress.jsonl
```

The bottom-right job tray displays current status, percent, recent log lines, and a **Stop safely** control. Stopping preserves artifacts already written. HyperFrames also preserves valid render chunks, so a later render can resume them.

If Factory Desk is closed during a task, its job record remains. On the next inspection, a vanished worker process is marked `interrupted`; files are not deleted. Check the artifact folders and rerun the bounded action.

To deliberately rebuild from an earlier stage, use **Recovery & versions**. The desk moves populated downstream folders into:

```text
_control/archive/<UTC-timestamp>/
```

It then recreates empty stage folders and rewinds the episode state. This is recoverable and avoids overwriting the old production.

## Episode folder contract

```text
projects/<episode-id>/
├── 00_input/          verified episode brief
├── 01_narration/      story structure and spoken script
├── 02_voice/          immutable master voice and metadata
├── 03_director/       raw, normalized, and approved scene plans
├── 04_prototype/      synthetic working demo
├── 05_asset_jobs/     validated capture contracts
├── 06_recordings/     deterministic browser recordings
├── 07_talking_head/   imported/generated presenter clips
├── 08_graphics/       graphics assets
├── 09_composition/    generated HyperFrames composition
├── 10_final/          preview, final, chunks, and render reports
├── _requests/         prompts, schemas, responses, invocations, agent logs
├── _control/          durable jobs, progress, model routing, archives
└── episode-state.json approval flags and current stage
```

Every JSON handoff is loaded through its Pydantic model before the next pipeline stage advances.

## Troubleshooting

### `address already in use` on port 8787

The desk is already running or another process owns the port. Open the existing URL, or use `svf ui --port 8788`.

### A real AI task waits for a manual response

The selected provider is in manual mode. Open the generated prompt and schema in `_requests/`, save a matching JSON response at the indicated response path, then run the stage with its response-consumption workflow or choose a command provider in Model orchestration.

### An AI provider is unavailable

Run `svf doctor`. Authenticate/install the missing CLI or add the required API key from `.env.example`, select another compatible provider, or use Offline Mock to test the flow.

### Playwright or Chromium is missing

Run:

```bash
npm install
npx playwright install chromium
npm run doctor
```

If doctor already reports Chromium ready, do not reinstall it.

### Render fails

Run `npm run doctor`, confirm FFmpeg/FFprobe and HyperFrames are available, and inspect:

```text
_control/production.log
10_final/hyperframes-lint.log
10_final/*.render.log
10_final/hyperframes-concat.log
10_final/hyperframes-mux.log
```

Fix the bounded failure and rerun the render. Valid chunks are reused.

### The UI reports an interrupted job after restart

This is intentional recovery behavior. Inspect the last production log and expected artifact, then rerun the same action. Do not delete `_control/jobs`; it is the production audit history.

## Compact CLI checklist

```bash
svf init pain-102 --title "..." --pain "..." --industry "..." --role "..."
svf narrate pain-102
svf import-voice pain-102 /absolute/path/to/voice.wav
svf direct pain-102
svf approve-director pain-102
svf prototype-prompt pain-102
svf build-prototype pain-102
svf record-demos pain-102
svf import-head pain-102 S01 /absolute/path/to/hook.mp4
svf generate-graphics pain-102
svf prepare-preview pain-102
svf qa pain-102
svf render-preview pain-102
svf render-final pain-102
svf approve-final pain-102
```

At each boundary, inspect the validated contract and only advance when the current stage is correct.

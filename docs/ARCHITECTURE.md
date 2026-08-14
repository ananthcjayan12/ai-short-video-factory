# Architecture

## Core rule

**Narration is content. Voice is time. Director is intent. Render code is truth.**

The Director never writes the final video. It returns a validated `DirectorPlan`. Asset workers execute only the scenes assigned to them. The compositor renders the approved artifacts on the master audio clock.

## Stages

1. `00_input` — one validated case brief.
2. `01_narration` — approved case-study narration.
3. `02_voice` — master voice track and duration metadata.
4. `03_director` — raw, normalized and approved scene plans.
5. `04_prototype` — small working synthetic product demo.
6. `05_asset_jobs` — Playwright or other scene jobs.
7. `06_recordings` — deterministic demo clips.
8. `07_talking_head` — real or generated presenter clips.
9. `08_graphics` — optional generated/local graphic artifacts.
10. `09_composition` — inspectable HyperFrames HTML + manifests.
11. `10_final` — preview/final MP4, logs and render report.

## Why persisted folders instead of one agent memory

Every stage is debuggable and rerunnable. The pipeline can invalidate one downstream artifact without discarding upstream approvals. This is much safer than a long autonomous session whose internal state is hard to inspect.

## Parallel execution after Director approval

After scene approval these jobs can run concurrently:

- code agent builds/repairs the prototype;
- Playwright records deterministic screen scenes;
- real talking-head clips can be recorded in a batch;
- InfiniteTalk can render optional presenter replacements;
- local HyperFrames graphics need no paid generation.

Final composition waits only for required assets or uses explicit safe placeholders.

# Editorial sequence graphics

This branch changes the **creative planning unit** without replacing the existing media engines.

Previously, Custom Graphics filtered the approved Director plan down to only `hyperframes` / `static` scenes and generated each graphics scene independently. That made two graphics scenes appear adjacent to the graphics agent even when a Playwright screen recording or presenter scene existed between them in the final timeline.

The new path groups the **real Director timeline** into editorial sequences of two or three adjacent beats and directs that sequence in one structured-model call.

## Timeline model

```text
Narration + Whisper word clock
            |
        Director plan
            |
  Editorial sequence grouping
            |
   +--------+---------+
   |        |         |
 talking   screen    graphics
 head      proof     beat
   |        |         |
 existing  existing  CustomGraphicsLayoutPlan
 media     Playwright       |
 path      path              v
                       graphics_coder
                            |
                       HyperFrames
            \               /
             \             /
              existing compositor
                     |
                 final video
```

A sequence can therefore look like:

```text
Q01: talking head -> HyperFrames graphic
Q02: Playwright proof -> talking head -> HyperFrames diagram
```

The creative director sees every beat in the sequence and plans `transition_in`, `transition_out`, a continuity object, and an optional `overlay_intent`. It returns full `CustomGraphicsLayoutPlan` objects **only** for the graphics beats. Presenter and Playwright scenes remain authoritative base media.

## Why this is different

The old continuity context was built from a graphics-only filtered list. For a timeline such as:

```text
S02 graphics -> S03 Playwright -> S04 presenter -> S05 graphics
```

S02 could incorrectly treat S05 as its immediate visual neighbour. The editorial plan preserves S03 and S04, so S02 can hand off into the real screen proof and S05 can intentionally pick up after the presenter.

The layout calls run sequentially so the closing handoff from one editorial sequence can inform the next. After all layouts are locked, scene coding is parallelized because the deterministic scene contracts are already fixed.

## Model routing

Three independent model routes are now registered in Factory Desk:

- `graphics_layout` — multi-beat creative / editorial direction.
- `graphics_coder` — HTML/CSS/deterministic JavaScript implementation for one graphics scene.
- `graphics_code_repair` — bounded source repair from measured validation failures.

`graphics_builder` remains registered for backward compatibility and the old mock/offline path.

The defaults use the same Codex route as the previous graphics builder, so existing installations do not suddenly require new provider credentials. Operators can route the three stages independently in the existing model controls—for example a reasoning-focused model for `graphics_layout` and a code-focused model for `graphics_coder`.

## Call shape

By default:

- `SVF_EDITORIAL_BEATS_PER_SEQUENCE=2`
- `SVF_EDITORIAL_MAX_SEQUENCE_SECONDS=16`
- `SVF_CUSTOM_GRAPHICS_CONCURRENCY=3`

For roughly ten to twelve Director beats in a one-minute video, the first setting normally produces about five to six **creative layout calls**. Each graphics scene still receives a coder invocation after its layout is locked, plus repair only when validation measures a defect.

Set `SVF_EDITORIAL_BEATS_PER_SEQUENCE=3` to prefer three-beat sequences. The duration cap can still split long beats into smaller batches.

## Screen recordings

Playwright remains the source of truth for application footage. Editorial planning receives the screen scene's narration, purpose, visual brief, adjacent scenes, and Whisper timing, but it is explicitly forbidden from replacing the screen with a fake generated UI.

This release plans the visual handoff into and out of the screen recording. The compositor still uses the existing `generated_asset` / `source_asset` media path.

## Talking head

Real camera and InfiniteTalk clips also remain base media. The editorial sequence planner uses them as first-class timeline beats so a graphic can deliberately resolve into the presenter, or the presenter can introduce the object that becomes the next graphic.

## Overlay intent

`EditorialBeatDirection.overlay_intent` records restrained ideas such as a kinetic keyword, callout, arrow, stat, or screen annotation over real media. **This branch does not yet render those overlays on top of presenter or Playwright video.** The current compositor remains one base visual per Director scene.

That is intentional for this PR: it lands the multi-beat planning, real-timeline continuity, call batching, split model routing, and repair fix without changing the proven media/composition contract at the same time. A follow-up can turn `overlay_intent` into an actual overlay track/layer once the sequence planner is validated on real outputs.

## Persisted artifact

The planner writes:

```text
03_director/editorial_sequence_plan.json
```

This includes deterministic sequence boundaries, previous/next real timeline scenes, the global visual bible, each sequence's beat directions, and the generated graphics layouts. It is intended to make editorial decisions inspectable and debuggable before final rendering.

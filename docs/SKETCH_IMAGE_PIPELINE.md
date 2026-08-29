# Codex Whiteboard SVG Animation Pipeline

The graphics path uses Codex to create each scene's SVG drawing and its
word-cued CSS/JavaScript animation. It uses no image generator or video provider.

```text
final narration audio
  -> Whisper word timestamps
  -> approved Director scene order and visual brief
  -> Codex-generated Pydantic layout contract
  -> Codex-generated inline SVG + scoped CSS + JavaScript
  -> schema/source validation and word-cue alignment
  -> HyperFrames render
  -> FFmpeg concat/mux fallback
```

Each graphics scene is written to `08_graphics/scenes/<scene-id>.html`. The
ordered master animation is `08_graphics/master.html`. Both use the same scene
contract and the narration remains the master clock.

Codex creates a scene-specific but intentionally simple SVG composition from the
approved visual brief. It receives the scene-local, locked word timings and
must attach every meaningful action to an exact narration phrase.

Layout is bounded deterministically:

- every object frame must remain inside the 0–100% scene stage;
- the whiteboard stage clips anything outside its safe frame;
- scene labels are limited to two lines and wrap long tokens;
- support details are excluded from the visual surface;
- source is scoped to its scene and cannot access network, timers, page globals,
  or external assets;
- animation is recalculated from narration-relative time on every seek.

Use the Factory Desk **Build whiteboard animation** action or:

```bash
svf generate-graphics <episode-id>
```

Bulk creation runs up to four isolated Codex scene workers in parallel
(`SVF_CUSTOM_GRAPHICS_CONCURRENCY=4`). A worker makes the validated layout, then
the SVG/CSS/JavaScript source, while final scene order always follows the locked
Director timeline.

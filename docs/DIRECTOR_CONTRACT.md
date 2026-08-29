# Director contract

The Director gets:

- final narration text;
- final voice duration;
- validated Whisper word timestamps;
- case brief;
- available scene types/renderers;
- production budgets;
- the project-wide talking-head policy.

It returns `DirectorPlan`.

A scene must define:

```text
scene_id
start / end
type
renderer
narration_excerpt
purpose
visual_brief
demo_job_id (if screen recording)
on_screen_text
```

## Image-first sketch branch

In this branch the Director makes the visual-medium decision before any expensive asset generation begins.

### Sketch / whiteboard scene

Use a graphics scene type such as `motion_graphic`, `diagram`, `ui_mockup` or `broll` with `renderer=static`.

`visual_brief` must already specify the exact visible composition strongly enough for one 9:16 keyframe to be generated without a second creative agent inventing the story. It should identify:

- protagonist or main object;
- episode-specific props;
- visible relationship / cause-and-effect;
- focal hierarchy;
- minimal labels that are genuinely needed;
- the visual payoff.

Downstream production is:

```text
Director visual_brief
    -> Codex-validated whiteboard scene contract
    -> Codex-created inline SVG
    -> locked-word-timed CSS/JavaScript animation
```

Codex translates the approved brief into the scene SVG; it does not re-plan the scene.

### Screen-recording scene

Use `screen_recording` + `playwright` only for a claim a synthetic working prototype can visibly prove. The Director should state the exact software state / behavior the viewer needs to see so the prototype builder creates only the required camera-ready UI.

## Editorial principles

1. The voice track is immutable during direction.
2. Every scene cut must use the validated Whisper word clock.
3. When talking head is allowed at project level, the face is used for trust, insight and transitions—not merely because footage exists. When disabled, presenter scene types and renderers are forbidden.
4. Screen recording is reserved for observable prototype proof, not generic dashboards.
5. Whiteboard/sketch images explain the human moment, causality, stakes, comparisons, context and mental models.
6. Adjacent narration lines that share one strong visual idea should usually remain one image scene so progressive drawing animation can reveal it cleanly.
7. AI ambiguity should be visible. “REVIEW” or one useful clarification can be better proof than pretending the system is always certain.
8. The DIY scene should feel achievable; the advanced integration should feel deeper but not like an ad.
9. A hard normalizer constrains creative output before any expensive asset generation begins.
10. Production budgets are deterministic inputs. AI-returned budget values are never authoritative.

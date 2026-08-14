# Director contract

The Director gets:

- final narration text;
- final voice duration;
- case brief;
- available scene types/renderers;
- production budgets.

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

## Editorial principles

1. The voice track is immutable during direction.
2. The face is used for trust, insight and transitions—not merely because footage exists.
3. Screen recording is reserved for a claim a working prototype can prove.
4. Graphics explain relationships or causality; they should not decorate literal words.
5. AI ambiguity should be visible. “REVIEW” is often a better demo than pretending the system is always certain.
6. The DIY scene should feel achievable; the advanced integration should feel deeper but not like an ad.
7. A hard normalizer constrains creative output before any expensive asset generation begins.

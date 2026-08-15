# Director contract

The Director gets:

- final narration text;
- final voice duration;
- case brief;
- available scene types/renderers;
- production budgets.
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

## Editorial principles

1. The voice track is immutable during direction.
2. When talking head is allowed at project level, the face is used for trust, insight and transitions—not merely because footage exists. When disabled, presenter scene types and renderers are forbidden.
3. Screen recording is reserved for a claim a working prototype can prove.
4. Graphics explain relationships or causality; they should not decorate literal words.
5. AI ambiguity should be visible. “REVIEW” is often a better demo than pretending the system is always certain.
6. The DIY scene should feel achievable; the advanced integration should feel deeper but not like an ad.
7. A hard normalizer constrains creative output before any expensive asset generation begins.
8. Production budgets are deterministic inputs. AI-returned budget values are never authoritative.

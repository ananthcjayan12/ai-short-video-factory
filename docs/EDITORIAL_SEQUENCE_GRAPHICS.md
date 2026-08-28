# Editorial sequence graphics — V3 creative contract

This branch keeps the mixed-media editorial-sequence idea, but changes the AI contract to match the working V3 architecture in `stock-select/UI-revamp`.

The important boundary is now:

```text
Narration + Whisper numeric timing
            |
        Director plan
            |
  Mixed-media sequence grouping
            |
   2–3 adjacent real beats
            |
   lightweight V3 creative JSON
            |
 deterministic compatibility compiler
            |
   existing Custom Graphics coder
            |
 HTML / CSS / deterministic JavaScript
            |
 deterministic source validation
            |
 browser visual QA / repair
            |
       existing compositor
```

## Why the contract changed

The first version of this PR asked the creative model to emit the existing `CustomGraphicsLayoutPlan` directly. That plan contains renderer bookkeeping such as:

- `initially_visible`
- exact reveal cardinality
- `anchor_text` / `anchor_occurrence`
- `review_checkpoints`
- scene-local action timing
- strict stage-fill and semantic-state rules

Those fields are useful for deterministic rendering, but they are a poor creative-model boundary. Small, human-understandable differences such as an implicit reveal, an absolute timestamp, or a paraphrased narration anchor caused the whole generation call to fail before coding.

The V3 path now follows Stock-Select's separation of responsibilities:

```text
Creative model: WHAT should appear, WHERE, and WHEN?
Coder/compiler: HOW is that represented safely and deterministically?
```

The creative model no longer emits renderer-native `CustomGraphicsLayoutPlan` objects.

## V3 creative JSON

Each editorial sequence contains two or three adjacent Director beats. The creative model returns a small JSON object with:

```text
sequence_id
canvas_duration
visual_thesis
continuity_object
beats[]
```

Each beat contains:

```text
beat_id
scene_id
renderer
time_start
time_end
narration_text
transition_in
transition_out
overlay_intent
layout
gsap_choreography
```

For graphics beats, `layout` contains a small number of descriptive elements and `gsap_choreography` contains numeric animation intentions such as:

```text
slide_left
slide_right
fade_in
line_draw
count_up
paper_drop
stamp_hit
formation_build
bar_fill
scale_reveal
persist
```

For Playwright and presenter beats, `layout=null` and `gsap_choreography=[]`. Their existing video remains authoritative.

## Timing model

The creative model sees only **sequence-local numeric time**.

If a sequence starts at master time `6.10s`, an animation at master time `12.60s` is exposed to the creative layer as `6.50s`.

Whisper words are also converted to sequence-local numeric timestamps before entering the prompt. They are context for creative timing only.

There is no executable narration phrase contract in the V3 layer:

```text
no anchor_text
no anchor_occurrence
no exact phrase re-matching
```

This removes the failure mode where a sensible phrase such as `work out the shipment` differs slightly from the Whisper tokenization.

## Deterministic compatibility compiler

The existing Custom Graphics renderer and package writer are retained in this PR. After the V3 creative response is normalized, deterministic Python converts each graphics beat into the legacy `CustomGraphicsLayoutPlan` required by the current renderer.

That compiler owns the mechanical details that the AI should not have to get exactly right:

- approved absolute scene start/end
- scene-local action times
- element ID sanitization
- frame bounds
- one opening element
- future-element reveal cues
- action cue IDs
- renderer action kinds
- numeric timing marker metadata
- review checkpoints
- final payoff timing
- minimum portrait-stage coverage

So the strict renderer contract still exists, but **the AI no longer writes it**.

## Normalization instead of semantic repair loops

The V3 creative response is intentionally permissive. Ordinary model drift is normalized locally before compilation:

- wrong/missing beat IDs are replaced from the approved Director order
- renderer values are replaced from the Director
- graphics accidentally proposed for Playwright/presenter beats are discarded
- missing graphics layouts receive a deterministic minimal fallback
- element IDs are namespaced and sanitized
- unknown choreography targets are redirected to a known element
- obvious master-clock `at_offset` values are converted to sequence-local time
- out-of-range choreography is clamped to the approved beat window

This follows the same philosophy as Stock-Select V3: creative JSON is an intent specification, not executable binary metadata.

## Mixed-media continuity

The part from the earlier PR that remains important is grouping the **real Director timeline**, not a graphics-only filtered list.

For example:

```text
S02 graphics -> S03 Playwright -> S04 presenter -> S05 graphics
```

The planner sees all four beats in their real order. It can therefore plan the handoff into real screen proof and the return from the presenter instead of pretending S02 and S05 are adjacent.

`overlay_intent` remains planning metadata only in this PR. It does not yet physically composite generated overlays over Playwright or talking-head footage.

## Model routing

The existing independent routes remain:

- `graphics_layout` — V3-style creative director
- `graphics_coder` — renderer implementation
- `graphics_code_repair` — measured source repair

The branch keeps the repository's current provider defaults for compatibility. Operators can route them independently. To mirror Stock-Select's reference setup most closely, use a reasoning-focused model for `graphics_layout` and a code-focused model for `graphics_coder`.

## Call shape

Defaults remain:

- `SVF_EDITORIAL_BEATS_PER_SEQUENCE=2`
- `SVF_EDITORIAL_MAX_SEQUENCE_SECONDS=16`
- `SVF_CUSTOM_GRAPHICS_CONCURRENCY=3`

Creative sequence calls run in timeline order. After creative intent is locked and deterministically compiled, graphics coding can run in parallel.

## Persisted artifact

The planner writes:

```text
03_director/editorial_sequence_plan.json
```

It now contains the V3 creative contract rather than model-generated `CustomGraphicsLayoutPlan` objects. This makes it much easier to inspect whether the creative idea itself is correct before looking at renderer implementation details.

## Reliability boundary

The intended failure policy is now:

```text
Creative drift
    -> normalize deterministically

Unsafe or invalid generated source
    -> reject / repair

Measured browser visual defect
    -> source repair
```

In other words, generation should not crash because the creative model forgot a renderer bookkeeping field. Strictness is concentrated around the executable output and measured visual result, where it provides real value.

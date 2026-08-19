# Custom Graphics Engine Implementation Plan

## Outcome

Replace the current single-template graphics builder with a bounded, scene-specific HTML/CSS/JavaScript generation flow modeled on the Stock repository's MAV v3 custom-scene path.

The selected package theme remains an operator choice in the UI. The Director does not alternate themes. For every graphics scene, a creative-director model designs a narration-aligned layout contract and a code model translates that contract into isolated HTML, scoped CSS, and deterministic timeline JavaScript. The factory validates, previews, and repairs each scene independently before assembling the episode.

This affects future graphics generations only. Existing generated scene files are not manually rewritten.

## Why the current output repeats shapes

The current graphics model can describe a topic-specific `visual_form`, but the renderer only exposes it as a data attribute. Actual appearance is selected from a fixed CSS mapping keyed by `object_type`. A `decision` is therefore always the same diamond and a `process` is always the same arrow-like block. The whiteboard theme changes palette, typography, borders, and texture, but it still renders the same underlying semantic objects.

This architecture is reliable but cannot create sufficiently distinct compositions. Prompt changes alone cannot solve that limitation because the renderer has no implementation for the model's free-form visual description.

## MAV v3 behavior to adopt

The useful MAV v3 custom flow is:

1. Split narration into short, word-timed visual scenes.
2. Ask a creative-director model for strict Layout JSON.
3. Ask a code model to translate that JSON into scene HTML, scoped CSS, and GSAP choreography.
4. Inject each scene into a fixed composition shell.
5. Reject unsafe or structurally invalid output.
6. Normalize only mechanical issues deterministically.
7. Compile an inspectable master preview.
8. Seek to stable evidence frames and validate the visual result.
9. Repair only the failed scene using measured diagnostics and its current source.

The Short Factory should use the same separation of responsibilities, adapted to a 1080x1920 portrait canvas and the existing HyperFrames seek clock.

## Deliberate differences from MAV

- Keep `EpisodeBrief.graphics_theme` as the one package-wide UI selection.
- Keep narration and Whisper words as the master timeline.
- Generate JavaScript against a small approved scene API instead of permitting arbitrary browser code.
- Keep the existing composition and HyperFrames render pipeline; do not introduce Motion Canvas.
- Use portrait-safe coordinates and caption-safe regions.
- Ground all visible claims in the brief, narration, and approved Director plan.
- Keep deterministic recipes as a fail-soft option, but make custom generated scenes the primary route.
- Do not copy MAV's physics modules, landscape layouts, prompts, branding, or visual assets.

## Target pipeline

```text
Approved Director scene + narration + scene-local Whisper words + selected theme
    -> CustomGraphicsLayoutPlan (structured model)
    -> layout and timing validation
    -> CustomGraphicsSource (HTML + scoped CSS + timeline JS)
    -> source safety and shell-contract validation
    -> isolated scene preview
    -> deterministic checkpoint/action-frame QA
    -> scene-only measured repair when needed
    -> accepted scene source + hashes + QA evidence
    -> master graphics package
    -> existing composition preview and HyperFrames render
```

## Contracts

### `CustomGraphicsLayoutPlan`

One structured plan per graphics scene. It should contain:

- immutable `scene_id`, `start`, `end`, and selected `theme`;
- `visual_thesis`, `opening_state`, and observable `payoff_state`;
- two to five narration beats, each tied to an exact Whisper phrase and occurrence;
- free-form portrait regions with stable IDs and explicit rectangles;
- element descriptions, semantic roles, layering, and intended visual forms;
- choreography entries with approved action names, targets, entrances, exits, and cue anchors;
- two or three review checkpoints;
- a final-hold interval of at least 0.7 seconds.

The plan owns creative composition. It does not contain executable markup, CSS, JavaScript, SVG path data, or arbitrary colors.

### `CustomGraphicsSource`

One validated source bundle per scene:

- `scene_id`;
- `html` fragment;
- `css` containing only scene-scoped selectors;
- `javascript` exporting exactly one approved initializer;
- `layout_plan_sha256`;
- `generator` metadata and source version;
- repair history.

### Approved scene runtime API

Generated JavaScript should receive a factory-owned context rather than global browser access:

```javascript
export function initScene({root, timeline, cues, duration, theme, svg}) {}
```

The context exposes only:

- root-scoped element lookup;
- deterministic timeline operations (`fromTo`, `to`, `set`, `draw`, `countTo`);
- exact named narration cues;
- safe SVG helpers for lines, curves, arrows, and paths;
- scene duration and selected theme tokens.

The source must not use `window`, `document` outside the supplied root, network APIs, storage, timers, randomness, dynamic imports, `eval`, `Function`, external assets, event listeners, or dependency loading.

## Theme architecture

The creative Layout JSON is theme-aware, and the fixed shell supplies different token sets and motion guidance.

### Editorial documentary

- layered evidence, paper fragments, maps, cutaways, crops, route ribbons, bold kinetic type, irregular silhouettes, and controlled depth;
- solid or curved connectors chosen for the visual relationship;
- stronger scale changes, match moves, wipes, stamps, and object transformation;
- restrained texture and shadow supplied by the shell.

### Whiteboard explainer

- progressive marker drawing, simple figures, documents, axes, circles, underlines, annotated routes, and erased/replaced states;
- hand-drawn-looking SVG paths generated from a deterministic scene seed;
- marker-style connectors and arrowheads rather than editorial ribbons;
- fewer simultaneous elements, simpler spatial reading, and no collage shadows.

The theme is selected once for the graphics package. Every scene source must declare and validate the same theme.

## File-level implementation

### New files

- `shorts_factory/custom_graphics/models.py`: layout and generated-source Pydantic contracts.
- `shorts_factory/custom_graphics/prompts.py`: theme-aware layout, code-generation, and repair prompt assembly.
- `shorts_factory/custom_graphics/validation.py`: layout, source, cue, and shell validation.
- `shorts_factory/custom_graphics/compiler.py`: isolate accepted source in scene and master previews.
- `shorts_factory/custom_graphics/runtime.py`: approved runtime payload and source assembly.
- `shorts_factory/prompt_templates/graphics_layout.system.txt`
- `shorts_factory/prompt_templates/graphics_layout.user.txt`
- `shorts_factory/prompt_templates/graphics_coder.system.txt`
- `shorts_factory/prompt_templates/graphics_coder.user.txt`
- `shorts_factory/prompt_templates/graphics_code_repair.system.txt`
- `shorts_factory/prompt_templates/graphics_code_repair.user.txt`
- `shorts_factory/rendering/assets/graphics_runtime.js`
- `shorts_factory/rendering/assets/graphics_editorial.css`
- `shorts_factory/rendering/assets/graphics_whiteboard.css`
- `scripts/validate_custom_graphics.mjs`
- focused contract, security, compiler, QA, and integration tests.

### Existing files to change

- `shorts_factory/models.py`: add graphics engine/version metadata without breaking legacy plans.
- `shorts_factory/pipeline.py`: replace the single whole-plan graphics call with per-scene layout, code, validation, repair, and acceptance stages.
- `shorts_factory/prompts.py`: expose the new prompt builders.
- `shorts_factory/prompt_templates/prompt_model_mapping.json`: register layout, coder, and repair tasks.
- `shorts_factory/rendering/graphics.py`: retain the legacy contract renderer as fallback; delegate custom scenes to the new compiler.
- `shorts_factory/rendering/composition.py`: embed accepted custom scene bundles using the same seek clock.
- `shorts_factory/ui/server.py` and `shorts_factory/ui/static/app.js`: show engine status, failed scene diagnostics, and scene-only retry while preserving the existing theme selector.
- `scripts/validate_graphics.mjs`: either delegate to or share evidence helpers with the custom validator.
- `docs/CREATING_A_VIDEO.md` and `README.md`: document source artifacts and review flow.

## Implementation phases

### Phase 1 — Contracts and fixed shell

1. Add versioned layout and source contracts with `extra="forbid"`.
2. Define the 1080x1920 canvas, visual safe area, caption exclusion zone, token sets, font ownership, and z-index rules.
3. Define the allowed HTML tags, SVG tags/attributes, CSS properties/functions, JavaScript syntax, and timeline API.
4. Build a static hand-authored sample scene for each theme to prove the shell contract.

Exit criteria: the shell can seek deterministically, editorial and whiteboard are visibly distinct, and invalid contract/source fixtures fail before preview compilation.

### Phase 2 — Creative layout generation

1. Convert each approved graphics scene into a compact generation packet containing only its Director contract, narration excerpt, exact local words, adjacent continuity summary, theme, and canvas rules.
2. Generate `CustomGraphicsLayoutPlan` per scene with the structured provider.
3. Validate IDs, bounds, cumulative visibility, opening/payoff difference, cue existence, text budgets, action liveness, and final hold.
4. Cache valid layout plans by input hash so one scene can be regenerated without changing its neighbors.

Exit criteria: every generated layout has valid portrait geometry and word anchors before any code generation call occurs.

### Phase 3 — HTML/CSS/JavaScript generation

1. Feed only the validated layout, approved runtime API, selected theme contract, and exact scene identifiers to the coder.
2. Require exact output markers for HTML, CSS, and JavaScript.
3. Parse the three sections without executing them.
4. Reject unscoped CSS, base-shell overrides, global selectors, external URLs, forbidden DOM/browser APIs, inline handlers, unsupported SVG, hard-coded theme colors/fonts, duplicate IDs, missing planned IDs, and actions outside the scene window.
5. Permit deterministic mechanical normalization only for safe issues such as redundant wrappers or duplicated scene scope.

Exit criteria: accepted source can touch only its own scene root and the approved runtime.

### Phase 4 — Preview compiler and visual QA

1. Write each accepted bundle under `08_graphics/scenes/<scene-id>/` with its layout, source, metadata, and preview.
2. Build `08_graphics/master.html` from the accepted scene bundles and the existing integer-frame scene windows.
3. Seek the opening frame, every narration cue, every review checkpoint, the densest visible state, and the payoff hold.
4. Check overflow, clipping, collisions, unreadable text, empty stage, leaked future elements, unchanged actions, missing arrowheads, disconnected connector endpoints, unscoped mutations, and runtime exceptions.
5. Store screenshots and a machine-readable report per scene.

Exit criteria: compilation and every deterministic frame check pass before composition-ready state.

### Phase 5 — Bounded scene repair

1. Repair only the failed scene, never the full graphics plan.
2. Pass the repair model the validated layout, current source, exact diagnostics, and relevant checkpoint screenshots.
3. Preserve timing, narration anchors, theme, factual copy, and already-correct IDs.
4. Re-run source validation and all checkpoints for that scene after each attempt.
5. Allow two code-repair attempts. If the layout itself is proven impossible, allow one layout repair followed by fresh code generation.
6. Keep the last accepted source for every unaffected scene and archive every before/after hash.

Exit criteria: a failed S13 cannot alter S01-S12 or S14+, and unsuccessful repair leaves an inspectable failed scene rather than silently accepting it.

### Phase 6 — Pipeline and UI integration

1. Add `graphics_engine: "custom_html_v1"` to new graphics manifests while retaining legacy-plan loading.
2. Make custom generation the normal route for real providers; retain the current deterministic renderer for mock/offline mode and explicit fail-soft use.
3. Preserve the existing package-wide Editorial/Whiteboard UI control.
4. Display scene status: layout, source, compile, visual QA, repaired, or failed.
5. Add a scene-only regenerate/repair action and show the selected theme and source hash.

Exit criteria: users can choose one theme, generate the package, inspect every scene, and retry only a failed scene.

### Phase 7 — Rollout and hardening

1. Run the new engine behind an explicit engine-version setting on representative synthetic episodes.
2. Build regression fixtures for documents, decisions, handoffs, routes, queues, before/after transformations, evidence reveals, metrics, and CTA scenes in both themes.
3. Measure first-pass layout validity, first-pass code validity, visual-QA pass rate, repair rate, and repeated-silhouette rate.
4. Switch new projects to `custom_html_v1` only after the acceptance suite is stable.
5. Keep legacy rendering for existing manifests so old projects remain reproducible.

## Required validation gates

### Before code generation

- exact scene timing and theme;
- all cue anchors found in the scene-local Whisper words;
- unique, beat-prefixed IDs;
- all planned rectangles inside safe bounds;
- cumulative visible rectangles checked at every beat;
- only one to three opening actors;
- no payoff actor visible at the opening;
- at least one semantic state change;
- final payoff completed before the hold.

### Before browser execution

- HTML/SVG allowlist;
- CSS selector scoping and property allowlist;
- JavaScript AST allowlist;
- no network, storage, timers, randomness, global DOM access, dynamic code, external dependencies, or event listeners;
- no shell/base-class redefinition;
- all layout IDs present exactly once;
- every timeline target belongs to the scene;
- exact approved initializer signature.

### Before package acceptance

- no console/runtime errors;
- opening visibility contract passes;
- every semantic action changes a rendered frame;
- important content stays within portrait and caption-safe bounds;
- no unintended overlaps at checkpoints or densest state;
- readable minimum type and no clipped text;
- visible payoff hold;
- adjacent scenes do not reuse effectively identical composition and silhouette sets unless continuity requires it;
- editorial and whiteboard output use their respective theme grammar, not merely different colors.

## Artifacts and observability

Each run should retain:

```text
08_graphics/
  graphics_manifest.json
  master.html
  scenes/
    S13/
      layout.json
      source.json
      scene.html
      preview.html
      qa.json
      checkpoints/*.png
      repairs/*.json
_requests/
  graphics_layout_S13.*
  graphics_coder_S13.*
  graphics_code_repair_S13_attempt_01.*
```

The manifest should include engine version, theme, provider/model per stage, source hashes, accepted repair count, and QA status for each scene.

## Test plan

- Pydantic contract tests for valid and invalid layouts and source bundles.
- Prompt tests proving the selected theme and exact scene-local timing are supplied.
- Parser tests for missing, duplicate, and out-of-order source markers.
- Security tests for `fetch`, external URLs, global document lookup, timers, event listeners, `eval`, `Function`, imports, unscoped CSS, shell overrides, unsafe SVG, and inline handlers.
- Compiler tests proving one scene cannot modify another.
- Timeline tests proving cues snap to the first output frame at or after the Whisper anchor.
- Portrait geometry tests at 1080x1920 and the supported responsive preview size.
- Visual fixtures for every major scene family in both themes.
- Repair tests proving measured scene defects are supplied and unaffected scene hashes remain unchanged.
- Legacy manifest tests proving existing graphics packages still load.
- End-to-end mock-provider tests that generate source fixtures without rendering an MP4.

## Acceptance criteria

The implementation is complete when:

1. New real-provider graphics generations use scene-specific HTML/CSS/JavaScript.
2. The model is no longer limited to the fixed object-type silhouettes in the current renderer.
3. Editorial and whiteboard scenes have materially different drawing and motion grammar.
4. Future elements do not leak into the opening frame.
5. No accepted source can access the network, global page state, or another scene.
6. Every meaningful action is anchored to verified narration words and produces an observable frame change.
7. A failure repairs only its scene and preserves all accepted scene hashes.
8. Under-fill, overlap, clipping, and runtime errors block acceptance with actionable evidence.
9. Existing projects remain reproducible through the legacy renderer.
10. No MP4 render is required to generate, inspect, validate, or repair the graphics package.


# Sketch Image + Animation Pipeline

This branch keeps the existing Factory Desk, narration/voice/Whisper pipeline, Director approval, prototype builder, Playwright recorder, composition renderer and final QA.

Only the graphics-generation path changes.

## Old path

```text
Director graphics scene
  -> layout agent
  -> graphics code agent
  -> generated HTML/CSS/JavaScript/SVG
  -> HyperFrames / browser motion graphics
```

## New path

```text
final narration audio
  -> Whisper word timestamps
  -> Director decides exact visual medium and exact scene brief
      |
      +-- screen_recording
      |      -> existing prototype builder
      |      -> existing Playwright recorder
      |
      +-- static sketch scene
             -> sketch asset translator
             -> Codex imagegen keyframe PNG
             -> detailed whiteboard drawing-animation prompt
             -> optional configured image-to-video command
             -> animated MP4 (or static PNG fallback)

all media
  -> existing composition + render pipeline
```

## Why the Director still comes first

The image stage does not decide what to illustrate.

The approved Director plan already owns:

- start/end on the Whisper clock;
- whether the beat is a sketch or a screen recording;
- narration excerpt;
- purpose;
- exact visual brief;
- screen-proof requirement when applicable.

The sketch asset stage only translates that contract into:

1. one image prompt;
2. one animation prompt;
3. a keyframe PNG;
4. an optional animated MP4.

This prevents generic illustrations from being generated first and forced into the narration afterward.

## Codex image generation

Production image generation asks Codex to use its system-provided `imagegen` skill and preferred built-in `image_gen` tool.

The task explicitly requires the selected result to be copied from the Codex generated-images area into:

```text
projects/<episode>/08_graphics/images/<scene-id>.png
```

The branch intentionally does **not** silently fall back to Codex's API-key `scripts/image_gen.py` path. If the built-in tool is unavailable, the stage fails with the retained log so the operator can choose what to do next.

The coordinating Codex model comes from the existing `graphics_builder` model route in Factory Desk. You can override it with:

```bash
SVF_CODEX_IMAGE_MODEL=<codex-model>
```

## Animation prompts

Every keyframe gets a detailed prompt under:

```text
08_graphics/prompts/<scene-id>.animation.md
```

The prompt instructs an image-to-video model to:

- start from a blank whiteboard;
- draw the exact reference image in a logical stroke order;
- keep characters / objects / labels stable;
- add only subtle camera movement;
- end on the completed Director-approved composition;
- avoid morphing, 3D conversion, extra text, object substitution and distortion.

## Optional Grok / image-to-video command

Because Grok/Imagine media workflows may differ by machine, the branch uses a command-template adapter rather than hard-coding an undocumented CLI command.

Set:

```bash
SVF_GROK_ANIMATE_COMMAND='your-command --image {image} --prompt-file {prompt} --duration {duration} --output {output}'
```

Available placeholders:

```text
{image}
{prompt}
{output}
{duration}
{scene_id}
```

When no animation command is configured, `svf generate-graphics` still creates the PNG keyframes and animation prompts. The mixed-media preview uses the static PNG until an MP4 exists at:

```text
08_graphics/animations/<scene-id>.mp4
```

Run `svf generate-graphics <episode>` again after adding animations; existing images are reused and the MP4s become the scene `generated_asset`.

## Existing UI

No separate application is introduced.

The existing Factory Desk **Generate graphics** action is redirected to this image-first pipeline by the package initializer in this branch. The existing CLI `svf generate-graphics` is redirected the same way.

Model orchestration remains the same project-wide/per-episode system already used by the repository.

## Files written

```text
08_graphics/
├── sketch_asset_plan.json
├── sketch_manifest.json
├── graphics_plan.json              # compatibility summary for existing UI/composition
├── images/
│   └── Sxx.png
├── prompts/
│   ├── Sxx.image.md
│   ├── Sxx.image.codex.md
│   ├── Sxx.image.imagegen.log
│   └── Sxx.animation.md
└── animations/
    ├── Sxx.mp4                     # when available
    └── Sxx.animation.log
```

The approved Director plan is updated so each sketch scene's `generated_asset` points to the animated MP4 when available, otherwise the PNG keyframe. The existing composition renderer already understands both image and video assets, so HTML/CSS graphics generation is no longer needed for these scenes.

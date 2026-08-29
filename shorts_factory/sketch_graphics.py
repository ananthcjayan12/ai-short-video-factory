from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .integrations import load_env
from .io import load_model, write_json
from .models import (
    DirectorPlan,
    EpisodeBrief,
    EpisodeStage,
    GraphicsAction,
    GraphicsFrame,
    GraphicsObject,
    GraphicsPlan,
    GraphicsScenePlan,
    Narration,
    WordTimestampBundle,
)
from .orchestrator import resolve_task
from .pipeline import _run_graphics_agent, _structured_agent, load_config
from .progress import emit
from .project import ProjectStore
from .rendering.composition import build as build_composition


GRAPHICS_RENDERERS = {"hyperframes", "static"}


class SketchSceneAsset(BaseModel):
    """Prompt-only translation of one already-approved Director graphics scene."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    image_prompt: str = Field(min_length=40)
    animation_prompt: str = Field(min_length=80)
    draw_order: list[str] = Field(min_length=2, max_length=12)
    focal_elements: list[str] = Field(min_length=1, max_length=10)
    camera_move: str = Field(min_length=2, max_length=180)
    final_hold: str = Field(
        default="Hold the completed drawing cleanly for the final beat.",
        min_length=10,
    )


class SketchAssetPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    episode_id: str
    visual_thesis: str
    scenes: list[SketchSceneAsset] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_scenes(self):
        ids = [scene.scene_id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("sketch scene IDs must be unique")
        return self


def _scene_words(words: WordTimestampBundle | None, scene: Any) -> list[dict[str, Any]]:
    if words is None:
        return []
    return [
        {
            "word": word.word,
            "start": round(word.start, 3),
            "end": round(word.end, 3),
        }
        for word in words.words
        if word.end > scene.start and word.start < scene.end
    ]


def _timed_animation_prompt(
    asset: SketchSceneAsset,
    scene: Any,
    words: WordTimestampBundle | None,
) -> str:
    """Compile narration timestamps and the validated draw order into one motion brief."""

    duration = max(0.1, float(scene.end - scene.start))
    final_hold_start = max(0.2, duration - min(1.0, duration * 0.15))
    scene_words = _scene_words(words, scene)
    steps = asset.draw_order
    schedule: list[str] = []
    for index, instruction in enumerate(steps):
        start_fraction = index / len(steps)
        end_fraction = (index + 1) / len(steps)
        start = duration * 0.82 * start_fraction
        end = duration * 0.82 * end_fraction
        phrase = ""
        if scene_words:
            word_start = min(len(scene_words) - 1, int(len(scene_words) * start_fraction))
            word_end = max(word_start + 1, int(math.ceil(len(scene_words) * end_fraction)))
            phrase = " ".join(word["word"] for word in scene_words[word_start:word_end])
            start = max(0.0, float(scene_words[word_start]["start"]) - float(scene.start))
            if word_end < len(scene_words):
                end = max(start + 0.2, float(scene_words[word_end]["start"]) - float(scene.start))
        start = min(max(0.0, start), max(0.0, final_hold_start - 0.2))
        end = min(final_hold_start, max(start + 0.2, end))
        schedule.append(
            f"- {start:.2f}s–{end:.2f}s, while narration says \"{phrase}\": {instruction}."
        )
    return (
        asset.animation_prompt.strip()
        + "\n\nREFERENCE MODE\n"
        "Use <IMAGE_1> only as the exact target composition and style reference; it is the final frame, not the opening frame. "
        "Frame one must be a clean blank whiteboard. Progressively reveal the reference as genuine black-marker strokes, "
        "with accents added only after their related black outlines. Do not dissolve, wipe, fade, or morph the completed image into view.\n\n"
        f"NARRATION-LOCKED DRAW SCHEDULE (scene duration {duration:.2f}s)\n"
        + "\n".join(schedule)
        + f"\n- {final_hold_start:.2f}s–{duration:.2f}s: {asset.final_hold}\n"
        "The supplied narration phrases are timing cues only. Do not render them as captions or extra text."
    )


def _asset_prompt(
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    graphics_scenes: list[Any],
    words: WordTimestampBundle | None,
) -> str:
    payload = {
        "episode": {
            "episode_id": brief.episode_id,
            "title": brief.title,
            "industry": brief.industry,
            "role": brief.role,
            "graphics_theme": brief.graphics_theme,
            "canvas": {
                "width": brief.width,
                "height": brief.height,
                "fps": brief.fps,
            },
            "full_narration": narration.text,
        },
        "director_visual_thesis": director.visual_thesis,
        "approved_graphics_scenes": [
            {
                "scene_id": scene.scene_id,
                "start": scene.start,
                "end": scene.end,
                "narration_excerpt": scene.narration_excerpt,
                "purpose": scene.purpose,
                "visual_brief": scene.visual_brief,
                "emphasis": scene.emphasis,
                "on_screen_text": scene.on_screen_text,
                "word_timestamps": _scene_words(words, scene),
            }
            for scene in graphics_scenes
        ],
    }
    return (
        "# ROLE\n"
        "You are the image-and-motion translator for an approved vertical sketch-video Director plan.\n"
        "The Director has ALREADY decided which beats are illustrations and which beats are screen recordings. "
        "Do not add scenes, remove scenes, change timing, or reinterpret the story. Your job is to translate each "
        "approved graphics scene into one faithful whiteboard keyframe prompt and one image-to-video drawing prompt.\n\n"
        "# IMAGE LANGUAGE\n"
        "Create premium modern whiteboard/sketch illustrations: clean white background, confident black marker/ink "
        "linework, subtle gray shading, restrained teal/blue accents, and yellow/red only for warning or error. "
        "The image must feel designed by an experienced editorial illustrator, not like clip-art or a generic AI infographic.\n"
        "Use one strong visual idea per scene. Preserve natural body language. Prefer concrete episode-specific objects "
        "already present in the approved Director brief. Do not add stock business symbols just to fill the frame.\n"
        "Do not paste narration into the artwork. Text should be minimal: short labels, amounts, job names, or one tiny question "
        "only when it materially improves comprehension. Never invent metrics, savings, confidence values or customer facts.\n"
        "Design every frame specifically for 1080x1920 portrait viewing, with useful negative space and a clear focal hierarchy.\n\n"
        "# ANIMATION LANGUAGE\n"
        "The animation prompt must make the finished keyframe appear to be DRAWN LIVE from a blank whiteboard. "
        "Specify a logical stroke-by-stroke draw order, occasional marker-hand entry only when useful, arrows after their "
        "source objects, subtle camera push/pan, one or two emphasis pulses, and a clean final hold. "
        "Strictly forbid morphing, object substitution, extra text, 3D rendering, photorealism, facial distortion, "
        "random particles, and camera shake. The animation must preserve the exact reference composition.\n\n"
        "# TIMING\n"
        "Use the supplied Whisper word timestamps only as editorial context. The image itself is a keyframe; the animation "
        "should reveal the most important visual idea near the phrase that explains it. Do not return new timestamps and "
        "do not change Director scene boundaries.\n\n"
        "# OUTPUT\n"
        "Return exactly one SketchSceneAsset for every approved graphics scene, in the same order.\n\n"
        "# INPUT\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def _mock_asset_plan(
    episode_id: str,
    director: DirectorPlan,
    graphics_scenes: list[Any],
) -> SketchAssetPlan:
    return SketchAssetPlan(
        episode_id=episode_id,
        visual_thesis=director.visual_thesis,
        scenes=[
            SketchSceneAsset(
                scene_id=scene.scene_id,
                image_prompt=(
                    "Premium 9:16 whiteboard sketch on clean white background. "
                    + scene.visual_brief
                    + " Use black marker linework, subtle teal accents, minimal labels, and one clear focal story."
                ),
                animation_prompt=(
                    "Animate the supplied whiteboard keyframe from a blank white board. Draw the main subject first, "
                    "then supporting objects, then arrows and emphasis marks. Preserve every object and label exactly. "
                    "Use a subtle camera push and finish with a clean one-second hold. No morphing, no extra text, no 3D, "
                    "no photorealism, no distortion, no camera shake."
                ),
                draw_order=[
                    "main subject",
                    "supporting objects",
                    "arrows and relationships",
                    "final emphasis",
                ],
                focal_elements=[scene.purpose],
                camera_move="Very gentle portrait push-in toward the final visual proof.",
            )
            for scene in graphics_scenes
        ],
    )


def _codex_image_model(store: ProjectStore, episode_id: str) -> str:
    override = os.getenv("SVF_CODEX_IMAGE_MODEL", "").strip()
    if override:
        return override
    route = resolve_task(load_config(store, episode_id), "sketch_imagegen")
    if route.get("provider") != "codex":
        raise RuntimeError(
            "Sketch image generation uses Codex imagegen. Route sketch_imagegen to the Codex provider in Factory Desk "
            "or set SVF_CODEX_IMAGE_MODEL explicitly."
        )
    return str(route["model"])


def _grok_video_model(store: ProjectStore, episode_id: str) -> str:
    override = os.getenv("SVF_GROK_CLI_VIDEO_MODEL", "").strip()
    if override:
        return override
    route = resolve_task(load_config(store, episode_id), "sketch_animator")
    if route.get("provider") != "grok" or route.get("capability") != "video":
        raise RuntimeError(
            "Sketch animation requires the Grok CLI video route. Route sketch_animator to Grok in Factory Desk."
        )
    return str(route["model"])


def _run_codex_imagegen(
    store: ProjectStore,
    episode_id: str,
    *,
    scene: SketchSceneAsset,
    output: Path,
    prompt_file: Path,
) -> None:
    """Ask Codex to use its bundled imagegen skill and built-in image_gen tool.

    The system imagegen skill saves built-in results below CODEX_HOME, so the task
    explicitly requires copying the selected final into the episode workspace.
    We intentionally do not auto-fallback to the API-key CLI path.
    """

    output.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(scene.image_prompt + "\n", encoding="utf-8")
    model = _codex_image_model(store, episode_id)
    task_file = prompt_file.with_suffix(".codex.md")
    task_file.write_text(
        (
            "Use the system-provided imagegen skill for this project asset.\n\n"
            "IMPORTANT EXECUTION RULES:\n"
            "- Use the preferred BUILT-IN image_gen tool mode.\n"
            "- Do NOT silently use scripts/image_gen.py or an OPENAI_API_KEY fallback.\n"
            "- Generate exactly one final raster image.\n"
            "- The result is a project asset. After generation, copy the selected final from CODEX_HOME/generated_images "
            "into the exact destination below.\n"
            "- Do not create SVG, HTML, CSS, Canvas, or JavaScript instead of the raster image.\n"
            "- If built-in image_gen is unavailable in this Codex session, fail clearly.\n\n"
            f"DESTINATION:\n{output.resolve()}\n\n"
            f"IMAGE PROMPT:\n{scene.image_prompt}\n"
        ),
        encoding="utf-8",
    )
    command = (
        f"codex exec --skip-git-repo-check --model {shlex.quote(model)} - "
        f"< {shlex.quote(str(task_file.resolve()))}"
    )
    emit(
        35,
        f"{scene.scene_id}: generating whiteboard keyframe with Codex imagegen",
        task="graphics_builder",
    )
    result = subprocess.run(
        command,
        shell=True,
        cwd=output.parent,
        text=True,
        capture_output=True,
        timeout=max(120, int(os.getenv("SVF_IMAGEGEN_TIMEOUT_SECONDS", "900"))),
    )
    log_path = prompt_file.with_suffix(".imagegen.log")
    log_path.write_text(
        (result.stdout or "") + "\n" + (result.stderr or ""),
        encoding="utf-8",
    )
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(
            f"Codex imagegen failed for {scene.scene_id}. Built-in image_gen may not be exposed in this Codex session. "
            f"Inspect {log_path}. The pipeline intentionally did not switch to the API-key fallback automatically."
        )


def _write_mock_png(path: Path) -> None:
    """Tiny deterministic PNG used only by offline tests/mock mode."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l4t9WQAAAABJRU5ErkJggg=="
        )
    )


def _run_optional_animation(
    scene_id: str,
    image: Path,
    prompt: Path,
    output: Path,
    duration: float,
    model: str,
) -> bool:
    if output.is_file():
        emit(58, f"{scene_id}: reusing existing Grok animation", task="graphics_builder")
        return True
    grok_bin = os.getenv("SVF_GROK_BIN", "").strip() or shutil.which("grok")
    if not grok_bin:
        raise RuntimeError("Grok CLI is not installed or SVF_GROK_BIN is invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    tool_duration = 6 if duration <= 8 else 10
    task_file = prompt.with_suffix(".grok-video.md")
    task_file.write_text(
        (
            "Use the bundled Imagine skill and Grok CLI's native video-generation tool for this asset.\n\n"
            "EXECUTION RULES:\n"
            "- Use reference_to_video because the supplied image is the completed target drawing, not frame one.\n"
            "- Start on a clean blank whiteboard and draw toward the supplied reference composition.\n"
            f"- Generate one silent 9:16 video with the supported {tool_duration}-second duration.\n"
            "- Do not use curl, an xAI API key, the REST API, or an external media command.\n"
            "- Do not create code, SVG, HTML, or a textual substitute.\n"
            "- Copy the completed MP4 to the exact destination below.\n"
            "- If reference_to_video/image_to_video is unavailable in this Grok CLI session, fail clearly.\n\n"
            f"REFERENCE IMAGE:\n{image.resolve()}\n\n"
            f"DESTINATION:\n{output.resolve()}\n\n"
            "ANIMATION BRIEF:\n"
            + prompt.read_text(encoding="utf-8").strip()
            + "\n"
        ),
        encoding="utf-8",
    )
    command = [
        grok_bin,
        "--always-approve",
        "--no-subagents",
        "--max-turns",
        "8",
        "--prompt-file",
        str(task_file.resolve()),
    ]
    if model:
        command[1:1] = ["--model", model]
    emit(
        62,
        f"{scene_id}: animating with Grok CLI Imagine",
        task="graphics_builder",
    )
    result = subprocess.run(
        command,
        cwd=output.parent,
        text=True,
        capture_output=True,
        timeout=max(120, int(os.getenv("SVF_GROK_ANIMATE_TIMEOUT_SECONDS", "1200"))),
    )
    log = output.with_suffix(".animation.log")
    combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
    log.write_text(combined_output, encoding="utf-8")
    if result.returncode != 0 or not output.is_file():
        normalized_output = combined_output.casefold()
        if "personal-team-blocked:spending-limit" in normalized_output:
            raise RuntimeError(
                "Grok CLI Imagine reached this account's media spending/credit limit (HTTP 403). "
                "Add Grok credits or upgrade the signed-in account, then retry this scene."
            )
        if "not authenticated" in normalized_output or "grok login" in normalized_output:
            raise RuntimeError("Grok CLI is not authenticated. Run `grok login`, then retry this scene.")
        raise RuntimeError(
            f"Grok CLI animation failed for {scene_id}; inspect {log}. "
            "Confirm `grok login` is complete and this CLI build exposes an Imagine video tool."
        )
    return True


def _compat_scene(scene: Any, asset: SketchSceneAsset) -> GraphicsScenePlan:
    duration = scene.end - scene.start
    object_id = f"{scene.scene_id.lower()}_keyframe"
    return GraphicsScenePlan(
        scene_id=scene.scene_id,
        start=scene.start,
        end=scene.end,
        scene_shell="editorial_stage",
        motion_grammar="image_to_video_whiteboard",
        layout_variant="director_keyframe",
        visual_thesis=scene.visual_brief,
        headline=(scene.on_screen_text[0] if scene.on_screen_text else scene.purpose)[:120],
        support="Whiteboard keyframe + image-to-video drawing animation",
        visual_world="clean modern whiteboard sketch",
        opening_state="blank whiteboard before the illustration is drawn",
        payoff_state="completed Director-approved sketch composition",
        camera_move=(
            "push_in"
            if "push" in asset.camera_move.casefold()
            else "pan_left"
            if "pan left" in asset.camera_move.casefold()
            else "pan_right"
            if "pan right" in asset.camera_move.casefold()
            else "locked"
        ),
        continuity_object=(asset.focal_elements[0] if asset.focal_elements else None),
        objects=[
            GraphicsObject(
                object_id=object_id,
                object_type="artifact",
                role="generated whiteboard keyframe",
                label=(scene.on_screen_text[0] if scene.on_screen_text else scene.purpose)[:72],
                detail=scene.visual_brief[:240],
                slot="hero",
                frame=GraphicsFrame(
                    x=4,
                    y=4,
                    width=92,
                    height=92,
                    depth="foreground",
                ),
                visual_form="generated raster whiteboard illustration",
                show_detail=True,
                initially_visible=True,
            )
        ],
        actions=[
            GraphicsAction(
                at_seconds=0.0,
                action="hold",
                target=object_id,
                value="external image-to-video animation owns internal drawing motion",
                duration_seconds=max(0.2, min(4.0, duration)),
            )
        ],
        review_checkpoints=[
            round(max(0.0, min(duration, duration * 0.5)), 3)
        ],
    )


def _provider_worker_count(env_name: str, fallback: str, item_count: int) -> int:
    try:
        configured = int(os.getenv(env_name, fallback))
    except ValueError as exc:
        raise RuntimeError(f"{env_name} must be a positive integer") from exc
    if configured < 1:
        raise RuntimeError(f"{env_name} must be at least 1")
    return max(1, min(item_count, configured))


def _archive_asset(project: Path, scene_id: str, path: Path) -> None:
    if not path.is_file():
        return
    archive = project / "08_graphics/versions" / scene_id
    archive.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(archive / f"{time.time_ns()}-{path.name}"))


def generate_sketch_graphics_plan(
    store: ProjectStore,
    episode_id: str,
    *,
    agent_kind: str | None = None,
    consume_response: bool = False,
    operation: str = "images",
    scene_id: str | None = None,
    suggestion: str | None = None,
) -> GraphicsPlan:
    """Create or revise ordered sketch assets without invalidating sibling scenes."""

    allowed_operations = {"all", "images", "image", "animations", "animation"}
    if operation not in allowed_operations:
        raise ValueError(f"Unknown sketch operation: {operation}")
    if operation in {"image", "animation"} and not scene_id:
        raise ValueError(f"{operation} requires a scene_id")
    suggestion = (suggestion or "").strip()
    if suggestion and operation != "image":
        raise ValueError("A regeneration suggestion is only valid for one image")

    load_env()
    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    director_path = project / "03_director/director_plan.approved.json"
    director = load_model(director_path, DirectorPlan)
    graphics_scenes = [
        scene for scene in director.scenes if scene.renderer in GRAPHICS_RENDERERS
    ]
    if not graphics_scenes:
        raise RuntimeError(
            "The approved Director plan has no sketch/static graphics scenes"
        )

    words_path = project / "02_voice/audio_word_timestamps.json"
    words = (
        load_model(words_path, WordTimestampBundle)
        if words_path.is_file()
        else None
    )
    root = project / "08_graphics"
    image_root = root / "images"
    prompt_root = root / "prompts"
    animation_root = root / "animations"
    for directory in (image_root, prompt_root, animation_root):
        directory.mkdir(parents=True, exist_ok=True)

    configured_mock = False
    if agent_kind is None:
        configured_mock = (
            resolve_task(load_config(store, episode_id), "sketch_asset_planner")[
                "provider_mode"
            ]
            == "mock"
        )

    emit(
        10,
        f"Translating {len(graphics_scenes)} Director beats into whiteboard image assets",
        task="graphics_builder",
    )
    asset_plan_path = root / "sketch_asset_plan.json"
    if asset_plan_path.is_file() and operation != "all":
        asset_plan = load_model(asset_plan_path, SketchAssetPlan)
    elif operation in {"animation", "animations"}:
        raise RuntimeError("Generate the ordered scene images before animating them")
    elif agent_kind == "mock" or configured_mock:
        asset_plan = _mock_asset_plan(episode_id, director, graphics_scenes)
    else:
        agent = _structured_agent(
            store,
            "sketch_asset_planner",
            {"episode_id": episode_id},
            agent_kind=agent_kind,
            consume_response=consume_response,
        )
        asset_plan = _run_graphics_agent(
            agent,
            stage="sketch_asset_plan",
            prompt=_asset_prompt(
                brief=brief,
                narration=narration,
                director=director,
                graphics_scenes=graphics_scenes,
                words=words,
            ),
            output_model=SketchAssetPlan,
            request_dir=project / "_requests",
        )

    expected = [scene.scene_id for scene in graphics_scenes]
    actual = [scene.scene_id for scene in asset_plan.scenes]
    if actual != expected:
        raise RuntimeError(
            "Sketch asset order differs from Director order; "
            f"expected={expected}, actual={actual}"
        )
    write_json(asset_plan_path, asset_plan)

    animation_available = bool(
        os.getenv("SVF_GROK_BIN", "").strip() or shutil.which("grok")
    )
    if operation in {"animation", "animations"} and not animation_available:
        raise RuntimeError(
            "Grok CLI is not installed. Install it or set SVF_GROK_BIN, then run `grok login`."
        )
    all_jobs = list(enumerate(zip(graphics_scenes, asset_plan.scenes)))
    known_scene_ids = {scene.scene_id for scene in graphics_scenes}
    if scene_id and scene_id not in known_scene_ids:
        raise ValueError(f"Unknown sketch scene: {scene_id}")
    selected_jobs = [
        job for job in all_jobs if scene_id is None or job[1][0].scene_id == scene_id
    ]
    warnings: list[str] = []

    for _index, (director_scene, asset) in all_jobs:
        image_prompt = prompt_root / f"{director_scene.scene_id}.image.md"
        prompt_text = asset.image_prompt
        if suggestion and director_scene.scene_id == scene_id:
            prompt_text += (
                "\n\nOPERATOR REGENERATION SUGGESTION (follow this while preserving the Director-approved facts):\n"
                + suggestion
            )
        image_prompt.write_text(prompt_text + "\n", encoding="utf-8")
        (prompt_root / f"{director_scene.scene_id}.animation.md").write_text(
            _timed_animation_prompt(asset, director_scene, words) + "\n",
            encoding="utf-8",
        )

    if operation in {"all", "images", "image"}:
        image_workers = _provider_worker_count(
            "SVF_CODEX_IMAGE_MAX_WORKERS", "3", len(selected_jobs),
        )
        emit(
            22,
            f"Generating {len(selected_jobs)} ordered image scene(s) on Codex's {image_workers} allowed worker(s)",
            task="graphics_builder",
        )

        def generate_image(job: tuple[int, tuple[Any, SketchSceneAsset]]) -> None:
            _index, (director_scene, asset) = job
            destination = image_root / f"{director_scene.scene_id}.png"
            force = operation == "image"
            if destination.is_file() and not force:
                emit(38, f"{director_scene.scene_id}: reusing existing keyframe", task="graphics_builder")
                return
            prompt_path = prompt_root / f"{director_scene.scene_id}.image.md"
            generation_asset = asset.model_copy(update={
                "image_prompt": prompt_path.read_text(encoding="utf-8").strip()
            })
            pending = image_root / ".pending" / f"{director_scene.scene_id}-{time.time_ns()}.png"
            if agent_kind == "mock" or configured_mock:
                _write_mock_png(pending)
            else:
                _run_codex_imagegen(
                    store,
                    episode_id,
                    scene=generation_asset,
                    output=pending,
                    prompt_file=prompt_path,
                )
            if force:
                _archive_asset(project, director_scene.scene_id, destination)
                _archive_asset(
                    project,
                    director_scene.scene_id,
                    animation_root / f"{director_scene.scene_id}.mp4",
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(pending, destination)

        if image_workers == 1:
            for job in selected_jobs:
                generate_image(job)
        else:
            with ThreadPoolExecutor(max_workers=image_workers, thread_name_prefix="codex-image") as executor:
                futures = [executor.submit(generate_image, job) for job in selected_jobs]
                for future in as_completed(futures):
                    future.result()
    else:
        image_workers = 0

    if operation in {"all", "animations", "animation"}:
        grok_video_model = _grok_video_model(store, episode_id)
        video_workers = _provider_worker_count(
            "SVF_GROK_VIDEO_MAX_WORKERS", "10", len(selected_jobs),
        )
        emit(
            56,
            f"Animating {len(selected_jobs)} ordered scene(s) on Grok's {video_workers} allowed worker(s)",
            task="graphics_builder",
        )

        def animate_scene(job: tuple[int, tuple[Any, SketchSceneAsset]]) -> str | None:
            _index, (director_scene, _asset) = job
            image = image_root / f"{director_scene.scene_id}.png"
            if not image.is_file():
                return f"{director_scene.scene_id}: image is missing; animation skipped"
            destination = animation_root / f"{director_scene.scene_id}.mp4"
            force = operation == "animation"
            if destination.is_file() and not force:
                emit(64, f"{director_scene.scene_id}: reusing existing animation", task="graphics_builder")
                return None
            pending = animation_root / ".pending" / f"{director_scene.scene_id}-{time.time_ns()}.mp4"
            try:
                ready = _run_optional_animation(
                    director_scene.scene_id,
                    image,
                    prompt_root / f"{director_scene.scene_id}.animation.md",
                    pending,
                    director_scene.end - director_scene.start,
                    grok_video_model,
                )
            except RuntimeError as exc:
                return f"{director_scene.scene_id}: Grok animation failed; static image retained. Reason: {exc}"
            if not ready:
                return (
                    f"{director_scene.scene_id}: Grok CLI did not create an animation; static image retained."
                )
            if force:
                _archive_asset(project, director_scene.scene_id, destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(pending, destination)
            return None

        if video_workers == 1:
            animation_warnings = [animate_scene(job) for job in selected_jobs]
        else:
            with ThreadPoolExecutor(max_workers=video_workers, thread_name_prefix="grok-video") as executor:
                futures = [executor.submit(animate_scene, job) for job in selected_jobs]
                animation_warnings = [future.result() for future in as_completed(futures)]
        warnings.extend(value for value in animation_warnings if value)
        if operation == "animation" and warnings:
            raise RuntimeError(warnings[0])
    else:
        video_workers = 0

    assets_by_scene: dict[str, str] = {}
    for director_scene in graphics_scenes:
        animated = animation_root / f"{director_scene.scene_id}.mp4"
        image = image_root / f"{director_scene.scene_id}.png"
        chosen = animated if animated.is_file() else image if image.is_file() else None
        if chosen:
            assets_by_scene[director_scene.scene_id] = chosen.relative_to(project).as_posix()

    # Composition already prioritizes generated_asset/source_asset, so attaching
    # real image/video files removes the need for HTML/CSS graphics scenes.
    updated_scenes = [
        scene.model_copy(
            update={"generated_asset": assets_by_scene[scene.scene_id]}
        )
        if scene.scene_id in assets_by_scene
        else scene
        for scene in director.scenes
    ]
    director = director.model_copy(update={"scenes": updated_scenes})
    write_json(director_path, director)

    compat = GraphicsPlan(
        episode_id=episode_id,
        duration_seconds=director.duration_seconds,
        theme=brief.graphics_theme,
        creative_thesis=asset_plan.visual_thesis,
        scenes=[
            _compat_scene(scene, asset)
            for scene, asset in zip(graphics_scenes, asset_plan.scenes)
        ],
        warnings=warnings,
    )
    # Retain the repo's existing graphics_plan.json contract so Factory Desk,
    # artifact browsing and composition do not need a parallel application.
    write_json(root / "graphics_plan.json", compat)
    write_json(
        root / "sketch_manifest.json",
        {
            "episode_id": episode_id,
            "pipeline": "director -> ordered codex images -> optional per-scene grok animations",
            "operation": operation,
            "selected_scene_id": scene_id,
            "assets": assets_by_scene,
            "animation_provider": "grok_cli" if animation_available else None,
            "animation_configured": animation_available,
            "image_workers": image_workers,
            "video_workers": video_workers,
            "warnings": warnings,
        },
    )

    emit(
        88,
        "Building mixed-media preview with generated sketch assets",
        task="graphics_builder",
    )
    build_composition(
        project,
        preview=True,
        width=brief.width,
        height=brief.height,
        fps=brief.fps,
    )
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(
        100,
        f"Prepared {len(compat.scenes)} image-first sketch scenes",
        task="graphics_builder",
    )
    return compat

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .custom_graphics import (
    CustomGraphicsLayoutPlan,
    CustomGraphicsPackage,
    CustomGraphicsSceneBundle,
    CustomGraphicsSource,
    CustomGraphicsSourceError,
    custom_package_summary,
    validate_custom_graphics_source,
    write_custom_graphics_package,
)
from .io import load_model, write_json
from .models import DirectorPlan, EpisodeBrief, EpisodeStage, GraphicsPlan, GraphicsTheme, Narration, WordTimestampBundle
from .orchestrator import resolve_task
from .pipeline import (
    CustomGraphicsVisualValidationError,
    _align_custom_layout_to_words,
    _run_graphics_agent,
    _structured_agent,
    _validate_custom_graphics_visuals,
    _validate_graphics_against_director,
    load_config,
)
from .progress import emit
from .project import ProjectStore
from .prompts import custom_graphics_code_repair_prompt, custom_graphics_coder_prompt
from .rendering.composition import build as build_composition


BaseRenderer = Literal[
    "manual_talking_head",
    "infinite_talk",
    "playwright",
    "hyperframes",
    "static",
]


class EditorialBeatDirection(BaseModel):
    """Editorial intent for one approved Director scene inside a larger sequence."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(min_length=1)
    renderer: BaseRenderer
    transition_in: str = Field(min_length=3, max_length=180)
    transition_out: str = Field(min_length=3, max_length=180)
    continuity_object: str | None = Field(default=None, max_length=96)
    overlay_intent: str = Field(
        default="",
        max_length=180,
        description=(
            "Optional editorial overlay idea for screen-recording or talking-head footage. "
            "This release records the intent but does not replace the base media renderer."
        ),
    )


class EditorialSequenceLayout(BaseModel):
    """One creative-director response spanning two or three adjacent timeline beats."""

    model_config = ConfigDict(extra="forbid")

    sequence_id: str = Field(pattern=r"^Q\d{2}$")
    visual_thesis: str = Field(min_length=3, max_length=240)
    opening_handoff: str = Field(min_length=3, max_length=180)
    closing_handoff: str = Field(min_length=3, max_length=180)
    continuity_object: str | None = Field(default=None, max_length=96)
    beats: list[EditorialBeatDirection] = Field(min_length=1, max_length=3)
    graphics_layouts: list[CustomGraphicsLayoutPlan] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_unique_scene_contracts(self):
        beat_ids = [beat.scene_id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("editorial sequence beat IDs must be unique")
        layout_ids = [layout.scene_id for layout in self.graphics_layouts]
        if len(layout_ids) != len(set(layout_ids)):
            raise ValueError("editorial sequence graphics layout IDs must be unique")
        return self


class EditorialSequenceRecord(BaseModel):
    """Persisted deterministic grouping plus the creative layout response."""

    model_config = ConfigDict(extra="forbid")

    sequence_id: str = Field(pattern=r"^Q\d{2}$")
    scene_ids: list[str] = Field(min_length=1, max_length=3)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    previous_scene_id: str | None = None
    next_scene_id: str | None = None
    layout: EditorialSequenceLayout | None = None


class EditorialSequencePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    episode_id: str
    theme: GraphicsTheme
    visual_bible: dict[str, Any]
    sequences: list[EditorialSequenceRecord] = Field(min_length=1)


@dataclass(frozen=True)
class _SequenceWindow:
    sequence_id: str
    scene_indexes: tuple[int, ...]


def _positive_int(name: str, default: int, *, minimum: int = 1, maximum: int = 8) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _positive_float(name: str, default: float, *, minimum: float = 1.0, maximum: float = 60.0) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _sequence_windows(director: DirectorPlan) -> list[_SequenceWindow]:
    """Group the real Director timeline into two-to-three beat editorial sequences.

    We group *all* renderers, not the graphics-only filtered list. This is the key
    continuity fix: a graphics scene can now intentionally hand off to a Playwright
    proof scene or presenter beat instead of pretending the next graphics scene is
    adjacent in the final edit.
    """

    scenes = sorted(director.scenes, key=lambda scene: scene.start)
    target = _positive_int("SVF_EDITORIAL_BEATS_PER_SEQUENCE", 2, minimum=2, maximum=3)
    max_duration = _positive_float("SVF_EDITORIAL_MAX_SEQUENCE_SECONDS", 16.0, minimum=6.0, maximum=30.0)
    groups: list[list[int]] = []
    cursor = 0
    while cursor < len(scenes):
        remaining = len(scenes) - cursor
        take = min(target, remaining)
        # Avoid a trailing singleton when three beats can form one coherent batch.
        if remaining == 3:
            take = 3
        indexes = [cursor]
        for candidate in range(cursor + 1, min(len(scenes), cursor + take)):
            duration = scenes[candidate].end - scenes[indexes[0]].start
            if duration > max_duration:
                break
            indexes.append(candidate)
        groups.append(indexes)
        cursor = indexes[-1] + 1
    if len(groups) >= 2 and len(groups[-1]) == 1 and len(groups[-2]) < 3:
        candidate = [*groups[-2], *groups[-1]]
        duration = scenes[candidate[-1]].end - scenes[candidate[0]].start
        if duration <= max_duration:
            groups[-2] = candidate
            groups.pop()
    return [
        _SequenceWindow(sequence_id=f"Q{index:02d}", scene_indexes=tuple(group))
        for index, group in enumerate(groups, 1)
    ]


def build_editorial_sequence_plan(director: DirectorPlan, *, theme: GraphicsTheme) -> EditorialSequencePlan:
    scenes = sorted(director.scenes, key=lambda scene: scene.start)
    records: list[EditorialSequenceRecord] = []
    for window in _sequence_windows(director):
        first = window.scene_indexes[0]
        last = window.scene_indexes[-1]
        records.append(EditorialSequenceRecord(
            sequence_id=window.sequence_id,
            scene_ids=[scenes[index].scene_id for index in window.scene_indexes],
            start=scenes[first].start,
            end=scenes[last].end,
            previous_scene_id=scenes[first - 1].scene_id if first else None,
            next_scene_id=scenes[last + 1].scene_id if last + 1 < len(scenes) else None,
        ))
    return EditorialSequencePlan(
        episode_id=director.episode_id,
        theme=theme,
        visual_bible={
            "visual_thesis": director.visual_thesis,
            "continuity_rule": (
                "Treat each sequence as one editorial thought. Reuse or transform a meaningful object, "
                "shape, crop, direction, or composition across adjacent beats instead of resetting to a new card."
            ),
            "screen_recording_rule": (
                "Playwright footage is real proof media. Do not redraw the application as a graphic; plan a clean visual handoff into and out of it."
            ),
            "talking_head_rule": (
                "Presenter footage remains real base media. Keep transitions and any suggested overlay minimal enough to preserve face readability."
            ),
            "graphics_rule": (
                "HyperFrames scenes should evolve through state changes, spatial transformations, traces, wipes, merges, or focused reveals—not slide-deck swaps."
            ),
        },
        sequences=records,
    )


def _scene_words(words: WordTimestampBundle | None, start: float, end: float) -> list[dict[str, Any]]:
    if words is None:
        return []
    return [
        word.model_dump(mode="json")
        for word in words.words
        if word.end > start and word.start < end
    ]


def _sequence_prompt(
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    plan: EditorialSequencePlan,
    record: EditorialSequenceRecord,
    words: WordTimestampBundle | None,
    previous_handoff: str | None,
) -> str:
    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    sequence_scenes = [scene_by_id[scene_id] for scene_id in record.scene_ids]
    previous = scene_by_id.get(record.previous_scene_id) if record.previous_scene_id else None
    following = scene_by_id.get(record.next_scene_id) if record.next_scene_id else None
    graphics_scene_ids = [
        scene.scene_id for scene in sequence_scenes
        if scene.renderer in {"hyperframes", "static"}
    ]
    payload = {
        "episode": {
            "episode_id": brief.episode_id,
            "title": brief.title,
            "theme": brief.graphics_theme,
            "full_narration": narration.text,
        },
        "visual_bible": plan.visual_bible,
        "sequence": {
            "sequence_id": record.sequence_id,
            "start": record.start,
            "end": record.end,
            "scenes": [scene.model_dump(mode="json") for scene in sequence_scenes],
            "previous_scene": previous.model_dump(mode="json") if previous else None,
            "next_scene": following.model_dump(mode="json") if following else None,
            "previous_sequence_handoff": previous_handoff,
            "word_timestamps": _scene_words(words, record.start, record.end),
        },
        "required_graphics_scene_ids": graphics_scene_ids,
    }
    return (
        "# ROLE\n"
        "You are the editorial motion-design director for one continuous short-form video sequence.\n\n"
        "# CORE CHANGE\n"
        "You are NOT designing one isolated poster-like scene. You receive two or three adjacent Director beats as one editorial thought. "
        "The beats may mix presenter footage, Playwright screen proof, and HyperFrames graphics. Plan the transitions across all of them together.\n\n"
        "# BASE MEDIA RULES\n"
        "- manual_talking_head / infinite_talk: the presenter clip remains the base visual. Do not replace it with generated graphics.\n"
        "- playwright: the recorded application remains the base visual. Do not fake or redraw the UI.\n"
        "- hyperframes / static: return a complete CustomGraphicsLayoutPlan for that scene.\n"
        "- For presenter or Playwright beats, use beats[].overlay_intent only to describe a restrained future overlay idea; no graphics_layout is allowed for those scene IDs in this release.\n\n"
        "# CONTINUITY\n"
        "Pick a meaningful continuity object or compositional motif and carry, transform, crop, point, or visually hand it off between beats. "
        "A screen-recording cut should feel motivated by the preceding graphic; a presenter return should feel like the payoff of the previous proof. "
        "Do not invent continuity between non-adjacent graphics scenes while ignoring the real media that sits between them.\n\n"
        "# GRAPHICS CONTRACT\n"
        "For every required graphics scene ID, return exactly one CustomGraphicsLayoutPlan using the approved scene_id/start/end/theme. "
        "Use one to three opening elements, exact narration anchor phrases for all non-hold actions, a visible state change, and a final-third payoff with at least 0.7 seconds of readability. "
        "The outgoing state should explicitly support the next beat's transition.\n\n"
        "# COVERAGE\n"
        "beats[] must contain every scene in the supplied sequence in the same order. graphics_layouts[] must contain exactly the required graphics scene IDs and no others.\n\n"
        "# INPUT\n```json\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
        + "\n```"
    )


def _validate_sequence_layout(
    layout: EditorialSequenceLayout,
    *,
    record: EditorialSequenceRecord,
    director: DirectorPlan,
    brief: EpisodeBrief,
    words: WordTimestampBundle | None,
) -> EditorialSequenceLayout:
    if layout.sequence_id != record.sequence_id:
        raise RuntimeError(f"Editorial layout returned {layout.sequence_id}; expected {record.sequence_id}")
    beat_ids = [beat.scene_id for beat in layout.beats]
    if beat_ids != record.scene_ids:
        raise RuntimeError(
            f"Editorial sequence {record.sequence_id} changed beat coverage/order; expected={record.scene_ids}, actual={beat_ids}"
        )
    scene_by_id = {scene.scene_id: scene for scene in director.scenes}
    for beat in layout.beats:
        expected = scene_by_id[beat.scene_id].renderer
        if beat.renderer != expected:
            raise RuntimeError(
                f"Editorial sequence {record.sequence_id}/{beat.scene_id} changed renderer {expected} -> {beat.renderer}"
            )
    expected_graphics = [
        scene_id for scene_id in record.scene_ids
        if scene_by_id[scene_id].renderer in {"hyperframes", "static"}
    ]
    actual_graphics = [item.scene_id for item in layout.graphics_layouts]
    if actual_graphics != expected_graphics:
        raise RuntimeError(
            f"Editorial sequence {record.sequence_id} graphics coverage differs; expected={expected_graphics}, actual={actual_graphics}"
        )
    aligned: list[CustomGraphicsLayoutPlan] = []
    for candidate in layout.graphics_layouts:
        if candidate.theme != brief.graphics_theme:
            raise RuntimeError(
                f"Editorial graphics layout theme {candidate.theme!r} does not match {brief.graphics_theme!r}"
            )
        aligned.append(_align_custom_layout_to_words(
            candidate, scene_by_id[candidate.scene_id], words, fps=brief.fps,
        ))
    return layout.model_copy(update={"graphics_layouts": aligned})


def _plan_sequence_layouts(
    store: ProjectStore,
    episode_id: str,
    *,
    brief: EpisodeBrief,
    narration: Narration,
    director: DirectorPlan,
    words: WordTimestampBundle | None,
    plan: EditorialSequencePlan,
    agent_kind: str | None,
    consume_response: bool,
    request_dir: Path,
) -> EditorialSequencePlan:
    layout_agent = _structured_agent(
        store, "graphics_layout", {"episode_id": episode_id},
        agent_kind=agent_kind, consume_response=consume_response,
    )
    resolved_records: list[EditorialSequenceRecord] = []
    previous_handoff: str | None = None
    total = len(plan.sequences)
    for index, record in enumerate(plan.sequences, 1):
        emit(
            12 + round((index - 1) / max(1, total) * 28),
            f"{record.sequence_id}: directing {len(record.scene_ids)} adjacent timeline beats together",
            task="graphics_layout",
        )
        base_prompt = _sequence_prompt(
            brief=brief,
            narration=narration,
            director=director,
            plan=plan,
            record=record,
            words=words,
            previous_handoff=previous_handoff,
        )
        candidate: EditorialSequenceLayout | None = None
        last_error: Exception | None = None
        for attempt in range(3):
            prompt = base_prompt
            if last_error is not None:
                prompt += (
                    f"\n\n# BOUNDED SEQUENCE REPAIR {attempt}/2\n"
                    "Return the complete corrected EditorialSequenceLayout. Preserve the approved scene IDs, order, renderers, timings, theme, and exact narration anchors.\n"
                    f"Measured defects:\n{last_error}"
                )
                if candidate is not None:
                    prompt += f"\n\nPrevious response:\n{candidate.model_dump_json(indent=2)}"
            try:
                candidate = _run_graphics_agent(
                    layout_agent,
                    stage=(
                        f"graphics_layout_{record.sequence_id.lower()}"
                        if attempt == 0 else f"graphics_layout_{record.sequence_id.lower()}_repair_{attempt}"
                    ),
                    prompt=prompt,
                    output_model=EditorialSequenceLayout,
                    request_dir=request_dir,
                )
                candidate = _validate_sequence_layout(
                    candidate,
                    record=record,
                    director=director,
                    brief=brief,
                    words=words,
                )
                break
            except (RuntimeError, ValueError) as exc:
                if "usage limit is exhausted" in str(exc).casefold():
                    raise
                last_error = exc
        else:
            raise RuntimeError(
                f"Editorial sequence repair failed for {record.sequence_id}: {last_error}"
            )
        previous_handoff = candidate.closing_handoff
        resolved_records.append(record.model_copy(update={"layout": candidate}))
    return plan.model_copy(update={"sequences": resolved_records})


def _generate_custom_source(
    store: ProjectStore,
    episode_id: str,
    *,
    layout: CustomGraphicsLayoutPlan,
    theme: GraphicsTheme,
    agent_kind: str | None,
    consume_response: bool,
    request_dir: Path,
    initial_source: CustomGraphicsSource | None = None,
    initial_issues: list[str] | None = None,
    stage_prefix: str = "graphics_coder",
) -> tuple[CustomGraphicsSource, list[str]]:
    coder_agent = _structured_agent(
        store, "graphics_coder", {"episode_id": episode_id},
        agent_kind=agent_kind, consume_response=consume_response,
    )
    repair_agent = _structured_agent(
        store, "graphics_code_repair", {"episode_id": episode_id},
        agent_kind=agent_kind, consume_response=consume_response,
    )
    repairs: list[str] = []
    source = initial_source
    issues = list(initial_issues or [])
    if source is None:
        source = _run_graphics_agent(
            coder_agent,
            stage=f"{stage_prefix}_{layout.scene_id.lower()}",
            prompt=custom_graphics_coder_prompt(layout, graphics_theme=theme),
            output_model=CustomGraphicsSource,
            request_dir=request_dir,
        )
        try:
            validate_custom_graphics_source(layout, source)
            return source, repairs
        except CustomGraphicsSourceError as exc:
            issues = exc.issues
            repairs.append("initial code: " + "; ".join(exc.issues))
    for attempt in range(1, 3):
        source = _run_graphics_agent(
            repair_agent,
            stage=f"{stage_prefix}_{layout.scene_id.lower()}_repair_{attempt}",
            prompt=custom_graphics_code_repair_prompt(layout, source, issues),
            output_model=CustomGraphicsSource,
            request_dir=request_dir,
        )
        try:
            validate_custom_graphics_source(layout, source)
            return source, repairs
        except CustomGraphicsSourceError as exc:
            issues = exc.issues
            repairs.append(f"repair {attempt}: " + "; ".join(exc.issues))
    raise CustomGraphicsSourceError(issues)


def _flatten_graphics_layouts(plan: EditorialSequencePlan) -> list[CustomGraphicsLayoutPlan]:
    layouts: list[CustomGraphicsLayoutPlan] = []
    for record in plan.sequences:
        if record.layout:
            layouts.extend(record.layout.graphics_layouts)
    return layouts


def _code_layouts(
    store: ProjectStore,
    episode_id: str,
    *,
    layouts: list[CustomGraphicsLayoutPlan],
    theme: GraphicsTheme,
    agent_kind: str | None,
    consume_response: bool,
    request_dir: Path,
) -> list[CustomGraphicsSceneBundle]:
    workers = _positive_int("SVF_CUSTOM_GRAPHICS_CONCURRENCY", 3, minimum=1, maximum=4)
    workers = min(workers, max(1, len(layouts)))
    emit(
        44,
        f"Coding {len(layouts)} graphics scene(s) on {workers} bounded worker(s) after sequence layouts are locked",
        task="graphics_coder",
    )
    completed = 0
    lock = Lock()

    def run(index: int, layout: CustomGraphicsLayoutPlan) -> tuple[int, CustomGraphicsSceneBundle]:
        source, repairs = _generate_custom_source(
            store,
            episode_id,
            layout=layout,
            theme=theme,
            agent_kind=agent_kind,
            consume_response=consume_response,
            request_dir=request_dir,
        )
        return index, CustomGraphicsSceneBundle(layout=layout, source=source, repairs=repairs)

    bundles: dict[int, CustomGraphicsSceneBundle] = {}
    if workers == 1:
        for index, layout in enumerate(layouts):
            _, bundle = run(index, layout)
            bundles[index] = bundle
            completed += 1
            emit(44 + round(completed / len(layouts) * 18), f"{layout.scene_id}: source validated", task="graphics_coder")
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="graphics-code") as executor:
            futures = {
                executor.submit(run, index, layout): (index, layout)
                for index, layout in enumerate(layouts)
            }
            try:
                for future in as_completed(futures):
                    index, layout = futures[future]
                    _, bundle = future.result()
                    bundles[index] = bundle
                    with lock:
                        completed += 1
                        emit(
                            44 + round(completed / len(layouts) * 18),
                            f"{layout.scene_id}: source validated ({completed}/{len(layouts)})",
                            task="graphics_coder",
                        )
            except Exception:
                for future in futures:
                    future.cancel()
                raise
    return [bundles[index] for index in range(len(layouts))]


def _load_coded_package_checkpoint(
    project: Path,
    *,
    episode_id: str,
    duration_seconds: float,
    theme: GraphicsTheme,
    layouts: list[CustomGraphicsLayoutPlan],
) -> CustomGraphicsPackage | None:
    """Return a fully validated coding checkpoint when its inputs still match."""
    path = project / "08_graphics/custom_graphics.json"
    if not path.is_file():
        return None
    try:
        package = load_model(path, CustomGraphicsPackage)
        if package.episode_id != episode_id or package.theme != theme:
            return None
        if abs(package.duration_seconds - duration_seconds) > 0.02:
            return None
        if len(package.scenes) != len(layouts):
            return None
        for bundle, layout in zip(package.scenes, layouts):
            if bundle.layout != layout:
                return None
            validate_custom_graphics_source(bundle.layout, bundle.source)
    except (OSError, ValueError, CustomGraphicsSourceError):
        return None
    return package


def _repair_visual_failures(
    store: ProjectStore,
    episode_id: str,
    *,
    package: CustomGraphicsPackage,
    report: Any,
    brief: EpisodeBrief,
    request_dir: Path,
    agent_kind: str | None,
    consume_response: bool,
) -> CustomGraphicsPackage:
    by_scene: dict[str, list[str]] = {}
    for finding in report.findings:
        if not finding.issues:
            continue
        targets = (
            [bundle.layout.scene_id for bundle in package.scenes]
            if finding.scene_id == "package" else [finding.scene_id]
        )
        for scene_id in targets:
            by_scene.setdefault(scene_id, []).extend(
                f"{finding.moment}: {issue}" for issue in finding.issues
            )
    repaired: list[CustomGraphicsSceneBundle] = []
    for bundle in package.scenes:
        issues = list(dict.fromkeys(by_scene.get(bundle.layout.scene_id, [])))
        if not issues:
            repaired.append(bundle)
            continue
        emit(78, f"{bundle.layout.scene_id}: repairing measured visual defects", task="graphics_code_repair")
        source, repairs = _generate_custom_source(
            store,
            episode_id,
            layout=bundle.layout,
            theme=brief.graphics_theme,
            agent_kind=agent_kind,
            consume_response=consume_response,
            request_dir=request_dir,
            initial_source=bundle.source,
            initial_issues=issues,
            stage_prefix="graphics_visual",
        )
        repaired.append(bundle.model_copy(update={
            "source": source,
            "repairs": [*bundle.repairs, *issues, *repairs],
        }))
    return package.model_copy(update={"scenes": repaired})


def generate_graphics_plan(
    store: ProjectStore,
    episode_id: str,
    *,
    agent_kind: str | None = None,
    consume_response: bool = False,
) -> GraphicsPlan:
    """Generate graphics from multi-beat editorial sequences while preserving real media.

    Creative planning runs sequentially over 2-3 adjacent Director scenes, including
    Playwright and talking-head scenes. Coding then runs in parallel only for the
    HyperFrames/static scenes. Screen recordings and presenter clips remain the
    authoritative base assets in the existing compositor.
    """

    project = store.project_dir(episode_id)
    brief = store.brief(episode_id)
    narration = load_model(project / "01_narration/narration.json", Narration)
    director = load_model(project / "03_director/director_plan.approved.json", DirectorPlan)
    graphics_scenes = [scene for scene in director.scenes if scene.renderer in {"hyperframes", "static"}]
    if not graphics_scenes:
        raise RuntimeError("The approved director plan has no HyperFrames/static graphics scenes")
    words_path = project / "02_voice/audio_word_timestamps.json"
    words = load_model(words_path, WordTimestampBundle) if words_path.is_file() else None

    configured_mock = False
    if agent_kind is None:
        configured_mock = resolve_task(load_config(store, episode_id), "graphics_layout")["provider_mode"] == "mock"
    if agent_kind == "mock" or configured_mock:
        # Keep the existing deterministic offline fixture path unchanged.
        from .pipeline import generate_graphics_plan as legacy_generate_graphics_plan
        return legacy_generate_graphics_plan(
            store, episode_id, agent_kind="mock", consume_response=consume_response,
        )
    if words is None:
        raise RuntimeError("Editorial graphics require validated scene-local Whisper word timestamps")

    request_dir = project / "_requests"
    sequence_plan = build_editorial_sequence_plan(director, theme=brief.graphics_theme)
    write_json(project / "03_director/editorial_sequence_plan.json", sequence_plan)
    emit(
        8,
        f"Grouped {len(director.scenes)} Director beats into {len(sequence_plan.sequences)} editorial sequence call(s)",
        task="graphics_layout",
    )
    sequence_plan = _plan_sequence_layouts(
        store,
        episode_id,
        brief=brief,
        narration=narration,
        director=director,
        words=words,
        plan=sequence_plan,
        agent_kind=agent_kind,
        consume_response=consume_response,
        request_dir=request_dir,
    )
    write_json(project / "03_director/editorial_sequence_plan.json", sequence_plan)

    layouts = _flatten_graphics_layouts(sequence_plan)
    expected_ids = [scene.scene_id for scene in graphics_scenes]
    actual_ids = [layout.scene_id for layout in layouts]
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"Editorial graphics layout order differs from Director graphics order; expected={expected_ids}, actual={actual_ids}"
        )
    bundles = _code_layouts(
        store,
        episode_id,
        layouts=layouts,
        theme=brief.graphics_theme,
        agent_kind=agent_kind,
        consume_response=consume_response,
        request_dir=request_dir,
    )
    package = CustomGraphicsPackage(
        episode_id=episode_id,
        duration_seconds=director.duration_seconds,
        theme=brief.graphics_theme,
        scenes=bundles,
    )
    summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
    _validate_graphics_against_director(summary, director)

    emit(65, "Compiling sequence-directed custom graphics previews", task="graphics_builder")
    write_custom_graphics_package(
        project, package, summary, width=brief.width, height=brief.height, fps=brief.fps,
    )
    emit(72, "Checking cue frames, clipping, overlap, and action liveness", task="graphics_builder")
    try:
        _validate_custom_graphics_visuals(
            project, fps=brief.fps, width=brief.width, height=brief.height,
        )
    except CustomGraphicsVisualValidationError as exc:
        package = _repair_visual_failures(
            store,
            episode_id,
            package=package,
            report=exc.report,
            brief=brief,
            request_dir=request_dir,
            agent_kind=agent_kind,
            consume_response=consume_response,
        )
        summary = custom_package_summary(package, creative_thesis=director.visual_thesis)
        _validate_graphics_against_director(summary, director)
        write_custom_graphics_package(
            project, package, summary, width=brief.width, height=brief.height, fps=brief.fps,
        )
        _validate_custom_graphics_visuals(
            project, fps=brief.fps, width=brief.width, height=brief.height,
        )

    emit(88, "Building full timeline with Playwright, presenter media, and directed graphics", task="graphics_builder")
    build_composition(project, preview=True, width=brief.width, height=brief.height, fps=brief.fps)
    store.transition(episode_id, EpisodeStage.COMPOSITION_READY)
    emit(
        100,
        f"Generated {len(summary.scenes)} graphics scenes from {len(sequence_plan.sequences)} editorial sequence call(s)",
        task="graphics_builder",
    )
    return summary

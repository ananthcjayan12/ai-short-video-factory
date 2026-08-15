from __future__ import annotations

import warnings
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EpisodeStage(str, Enum):
    INPUT = "input"
    NARRATION_READY = "narration_ready"
    VOICE_READY = "voice_ready"
    TIMING_READY = "timing_ready"
    DIRECTOR_REVIEW = "director_review"
    DIRECTOR_APPROVED = "director_approved"
    ASSETS_READY = "assets_ready"
    COMPOSITION_READY = "composition_ready"
    FINAL_REVIEW = "final_review"
    APPROVED = "approved"


class EpisodeBrief(BaseModel):
    episode_id: str
    title: str
    pain_point: str
    industry: str
    role: str
    backend_summary: list[str] = Field(default_factory=list)
    viewer_diy: list[str] = Field(default_factory=list)
    target_seconds: float = 58.0
    case_nature: Literal["real", "hypothetical", "synthetic_demo"] = "synthetic_demo"
    format: Literal["vertical_short"] = "vertical_short"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    synthetic_data_only: bool = True


class ProjectSettings(BaseModel):
    """Production policy shared by every episode under one project root."""

    include_talking_head: bool = True


class StoryBeat(BaseModel):
    beat_id: str
    purpose: Literal["hook", "problem", "insight", "solution", "proof", "diy", "cta"]
    summary: str
    claim_ids: list[str] = Field(default_factory=list)
    emotional_register: Literal["curiosity", "tension", "clarity", "proof", "trust", "agency"]
    ai_responsibility: str | None = None
    deterministic_responsibility: str | None = None
    proof_opportunity: str | None = None


class StorySpine(BaseModel):
    """Grounded human narrative extracted before technical beats are planned."""

    protagonist: str = Field(min_length=1)
    recurring_moment: str | None = None
    operational_pain: str = Field(min_length=1)
    stakes: str | None = None
    initial_assumption: str | None = None
    turning_point: str = Field(min_length=1)
    changed_workday: str | None = None
    source_gaps: list[str] = Field(default_factory=list)


class StoryPlan(BaseModel):
    episode_id: str
    target_seconds: float
    case_nature: Literal["real", "hypothetical", "synthetic_demo"] = "synthetic_demo"
    story_spine: StorySpine | None = None
    beats: list[StoryBeat] = Field(min_length=4, max_length=10)

    @model_validator(mode="after")
    def validate_sequence(self):
        expected = [f"B{i:02d}" for i in range(1, len(self.beats) + 1)]
        actual = [beat.beat_id for beat in self.beats]
        if actual != expected:
            raise ValueError(f"story beat IDs must be sequential: {expected}")
        if self.beats[0].purpose != "hook" or self.beats[-1].purpose != "cta":
            raise ValueError("story plan must begin with a hook and end with a CTA")
        return self


class NarrationParagraph(BaseModel):
    paragraph_id: str
    beat_id: str
    text: str
    claim_ids: list[str] = Field(default_factory=list)


class Narration(BaseModel):
    episode_id: str
    text: str
    word_count: int
    target_seconds: float
    hook: str
    consultation_line: str
    paragraphs: list[NarrationParagraph] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_copy_contract(self):
        actual_words = len(self.text.split())
        if self.word_count != actual_words:
            warnings.warn(
                f"Narration reported word_count={self.word_count}; normalized to deterministic count {actual_words}",
                UserWarning,
                stacklevel=2,
            )
            self.word_count = actual_words
        if self.paragraphs:
            expected = [f"P{i:02d}" for i in range(1, len(self.paragraphs) + 1)]
            actual = [paragraph.paragraph_id for paragraph in self.paragraphs]
            if actual != expected:
                raise ValueError(f"narration paragraph IDs must be sequential: {expected}")
            beat_ids = [paragraph.beat_id for paragraph in self.paragraphs]
            if len(beat_ids) != len(set(beat_ids)):
                raise ValueError("each story beat may be used by only one narration paragraph")
        return self


class NarrationQualityReport(BaseModel):
    episode_id: str
    passed: bool
    total_words: int = Field(ge=0)
    pain_words: int = Field(ge=0)
    pain_word_ratio: float = Field(ge=0, le=1)
    cta_words: int = Field(ge=0)
    opening_has_protagonist: bool
    solution_uses_client_story_voice: bool
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VoiceMetadata(BaseModel):
    episode_id: str
    audio_path: str
    duration_seconds: float
    source: Literal["generated", "manual", "mock"] = "manual"
    transcript_path: str | None = None
    timing_path: str | None = None
    word_timestamps_path: str | None = None


class WordTimestamp(BaseModel):
    index: int = Field(ge=0)
    paragraph_id: str
    beat_id: str
    word: str = Field(min_length=1)
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.end <= self.start:
            raise ValueError("word timestamp end must be after start")
        return self


class ParagraphTiming(BaseModel):
    paragraph_id: str
    beat_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    word_start_index: int = Field(ge=0)
    word_end_index: int = Field(ge=0)
    match_score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.end <= self.start:
            raise ValueError("paragraph timing end must be after start")
        if self.word_end_index < self.word_start_index:
            raise ValueError("paragraph word range is invalid")
        return self


class WordTimestampBundle(BaseModel):
    episode_id: str
    audio_duration_seconds: float = Field(gt=0)
    source: Literal["openai_whisper_word_timestamps"] = "openai_whisper_word_timestamps"
    whisper_model: str
    audio_sha256: str = Field(min_length=64, max_length=64)
    words: list[WordTimestamp] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_words(self):
        expected = list(range(len(self.words)))
        actual = [word.index for word in self.words]
        if actual != expected:
            raise ValueError("word timestamp indexes must be sequential")
        previous = 0.0
        for word in self.words:
            if word.start < previous - 0.05:
                raise ValueError(f"word timestamps overlap or are out of order at index {word.index}")
            if word.end > self.audio_duration_seconds + 0.25:
                raise ValueError(f"word timestamp {word.index} exceeds audio duration")
            previous = word.end
        return self


class AudioTiming(BaseModel):
    episode_id: str
    audio_duration_seconds: float = Field(gt=0)
    source: Literal["openai_whisper_word_timestamps"] = "openai_whisper_word_timestamps"
    whisper_model: str
    audio_sha256: str = Field(min_length=64, max_length=64)
    word_timestamps_path: str
    paragraphs: list[ParagraphTiming] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paragraphs(self):
        previous = 0.0
        for paragraph in self.paragraphs:
            if paragraph.start < previous - 0.05:
                raise ValueError(f"paragraph timings overlap at {paragraph.paragraph_id}")
            if paragraph.end > self.audio_duration_seconds + 0.25:
                raise ValueError(f"paragraph timing {paragraph.paragraph_id} exceeds audio duration")
            previous = paragraph.end
        return self


SceneType = Literal[
    "talking_head",
    "screen_recording",
    "motion_graphic",
    "diagram",
    "ui_mockup",
    "broll",
    "cta",
]

RendererType = Literal[
    "manual_talking_head",
    "infinite_talk",
    "playwright",
    "hyperframes",
    "static",
]


class Scene(BaseModel):
    scene_id: str
    start: float
    end: float
    type: SceneType
    renderer: RendererType
    narration_excerpt: str
    purpose: str
    visual_brief: str
    source_asset: str | None = None
    generated_asset: str | None = None
    demo_job_id: str | None = None
    emphasis: list[str] = Field(default_factory=list)
    on_screen_text: list[str] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


class DirectorBudgets(BaseModel):
    max_visual_moments: int = Field(default=7, ge=0)
    max_generated_assets: int = Field(default=5, ge=0)
    max_scene_seconds: float = Field(default=8.0, gt=0)
    max_consecutive_non_talking_head_seconds: float = Field(default=16.0, gt=0)
    require_talking_head_hook: bool = True
    require_talking_head_close: bool = True


class DirectorPlan(BaseModel):
    episode_id: str
    duration_seconds: float
    visual_thesis: str
    scenes: list[Scene]
    budgets: DirectorBudgets = Field(default_factory=DirectorBudgets)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timeline(self):
        if not self.scenes:
            raise ValueError("director plan requires scenes")
        ordered = sorted(self.scenes, key=lambda s: s.start)
        previous = 0.0
        for scene in ordered:
            if scene.start < previous - 1e-6:
                raise ValueError(f"overlapping scene {scene.scene_id}")
            if scene.end <= scene.start:
                raise ValueError(f"invalid duration for {scene.scene_id}")
            previous = scene.end
        if ordered[-1].end > self.duration_seconds + 0.25:
            raise ValueError("scene timeline exceeds narration duration")
        return self


GraphicsShell = Literal[
    "flow_stage", "comparison_stage", "timeline_stage", "document_stage",
    "system_stage", "queue_stage", "editorial_stage",
]
GraphicsObjectType = Literal[
    "channel", "document", "process", "decision", "database", "status",
    "metric", "person", "annotation", "text",
]
GraphicsActionType = Literal[
    "reveal", "highlight", "connect", "count_to", "stamp", "transform", "hold",
]


class GraphicsObject(BaseModel):
    object_id: str
    object_type: GraphicsObjectType
    role: str
    label: str
    detail: str
    slot: Literal["hero", "left", "center", "right", "top", "bottom"]


class GraphicsAction(BaseModel):
    at_seconds: float = Field(ge=0)
    action: GraphicsActionType
    target: str
    value: str | None = None
    source: str | None = None


class GraphicsScenePlan(BaseModel):
    scene_id: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    scene_shell: GraphicsShell
    motion_grammar: str
    layout_variant: str
    visual_thesis: str
    headline: str
    support: str
    continuity_object: str | None = None
    objects: list[GraphicsObject] = Field(min_length=1, max_length=7)
    actions: list[GraphicsAction] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_graphics_scene(self):
        if self.end <= self.start:
            raise ValueError(f"invalid graphics duration for {self.scene_id}")
        object_ids = [item.object_id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError(f"duplicate graphics object IDs in {self.scene_id}")
        known = set(object_ids)
        duration = self.end - self.start
        for action in self.actions:
            if action.target not in known:
                raise ValueError(f"graphics action targets unknown object {action.target}")
            if action.source and action.source not in known:
                raise ValueError(f"graphics action references unknown source {action.source}")
            if action.at_seconds > duration + 0.05:
                raise ValueError(f"graphics action exceeds {self.scene_id} duration")
        return self


class GraphicsPlan(BaseModel):
    episode_id: str
    duration_seconds: float = Field(gt=0)
    creative_thesis: str
    scenes: list[GraphicsScenePlan] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graphics_plan(self):
        ids = [scene.scene_id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("graphics scene IDs must be unique")
        return self


class DemoAction(BaseModel):
    at_seconds: float = 0.0
    action: Literal["goto", "click", "upload", "wait", "screenshot", "assert_text"]
    selector: str | None = None
    value: str | None = None
    milliseconds: int | None = None


PrototypeCueAction = Literal[
    "reveal", "highlight", "move", "connect", "compare", "transform", "status_change", "hold",
]


class PrototypeCue(BaseModel):
    """A visual change anchored to a phrase in the Whisper transcript."""

    cue_id: str
    anchor_text: str = Field(min_length=1)
    at_seconds: float = Field(ge=0)
    action: PrototypeCueAction
    target_testid: str = Field(min_length=1)
    visual_change: str = Field(min_length=1)


class DemoJob(BaseModel):
    job_id: str
    scene_id: str
    url: str
    viewport_width: int = 1080
    viewport_height: int = 1920
    output_path: str
    actions: list[DemoAction]
    duration_seconds: float | None = Field(default=None, gt=0)
    timeline_cues: list[PrototypeCue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timeline_cues(self):
        cue_ids = [cue.cue_id for cue in self.timeline_cues]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("prototype cue IDs must be unique within a demo job")
        if self.timeline_cues != sorted(self.timeline_cues, key=lambda cue: cue.at_seconds):
            raise ValueError("prototype timeline cues must be ordered by at_seconds")
        if self.duration_seconds is not None:
            for cue in self.timeline_cues:
                if cue.at_seconds > self.duration_seconds + 0.05:
                    raise ValueError(f"prototype cue {cue.cue_id} exceeds demo duration")
        return self


class CompositionManifest(BaseModel):
    episode_id: str
    title: str
    width: int
    height: int
    fps: int
    duration_seconds: float
    voice_path: str | None
    scenes: list[Scene]


class EpisodeState(BaseModel):
    episode_id: str
    stage: EpisodeStage = EpisodeStage.INPUT
    approved_director: bool = False
    approved_final: bool = False
    versions: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class TaskModelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    reasoning_effort: str | None = None

    @field_validator("provider", "model")
    @classmethod
    def require_value(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class ProgressEvent(BaseModel):
    event_id: str
    episode_id: str
    job_id: str
    stage: str
    task: str
    capability: str
    status: Literal["queued", "running", "succeeded", "failed", "stopped", "interrupted"]
    completed: float = 0
    total: float = 1
    unit: str = "step"
    percent: float = Field(default=0, ge=0, le=100)
    message: str
    timestamp: str
    speed: float | None = None
    eta_seconds: float | None = None


class ProductionJob(BaseModel):
    job_id: str
    episode_id: str
    action: str
    label: str
    stage: str
    task: str
    capability: str
    status: Literal["queued", "running", "succeeded", "failed", "stopped", "interrupted"]
    message: str
    request: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    error: str | None = None
    progress: float = Field(default=0, ge=0, le=100)
    pid: int | None = None
    resumable: bool = False
    created_at: str
    updated_at: str


class PromptInvocation(BaseModel):
    task: str
    stage: str
    provider: str
    model: str
    status: Literal["running", "succeeded", "failed", "manual", "mock"]
    prompt_path: str
    schema_path: str
    response_path: str
    started_at: str
    finished_at: str | None = None
    attempts: int = 0
    estimated_input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None

class PrototypeSpec(BaseModel):
    episode_id: str
    app_name: str
    purpose: str
    inputs: list[str]
    ai_jobs: list[str]
    deterministic_jobs: list[str]
    expected_states: list[str]
    build_notes: list[str] = Field(default_factory=list)


class BuildResult(BaseModel):
    episode_id: str
    status: Literal["ready", "manual_required", "failed"]
    prototype_dir: str
    entrypoint: str | None = None
    notes: list[str] = Field(default_factory=list)

class DemoJobBundle(BaseModel):
    episode_id: str
    jobs: list[DemoJob]

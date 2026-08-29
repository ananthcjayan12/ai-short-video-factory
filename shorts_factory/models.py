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


GraphicsTheme = Literal["editorial", "whiteboard"]


class EpisodeBrief(BaseModel):
    episode_id: str
    title: str
    pain_point: str
    industry: str
    role: str
    backend_summary: list[str] = Field(default_factory=list)
    viewer_diy: list[str] = Field(default_factory=list)
    suggested_stack: str | None = None
    source_narration: str | None = None
    source_reference: str | None = None
    is_filled_episode: bool = False
    target_seconds: float = Field(default=58.0, ge=5, le=480)
    case_nature: Literal["real", "hypothetical", "synthetic_demo"] = "synthetic_demo"
    format: Literal["vertical_short"] = "vertical_short"
    width: int = 1080
    height: int = 1920
    fps: Literal[24, 30, 60] = 60
    synthetic_data_only: bool = True
    graphics_theme: GraphicsTheme = "editorial"


class FilledEpisodeSource(BaseModel):
    """Operator-supplied source retained with a filled episode brief."""

    document: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    narration: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_line_range(self):
        if self.line_end < self.line_start:
            raise ValueError("source line_end must not precede line_start")
        return self


class FilledEpisode(BaseModel):
    """Validated source contract for one entry in the filled-episode library."""

    source_id: str = Field(pattern=r"^PAIN-\d{3}$")
    episode_id: str = Field(pattern=r"^filled-pain-\d{3}$")
    title: str = Field(min_length=3)
    industry: str = Field(min_length=2)
    role: str = Field(min_length=2)
    pain_point: str = Field(min_length=8)
    backend_summary: list[str] = Field(min_length=1, max_length=12)
    viewer_diy: list[str] = Field(min_length=1, max_length=12)
    suggested_stack: str | None = None
    target_seconds: float = Field(default=58.0, ge=15, le=480)
    case_nature: Literal["real", "hypothetical", "synthetic_demo"] = "real"
    source: FilledEpisodeSource

    def to_brief(self) -> EpisodeBrief:
        return EpisodeBrief(
            episode_id=self.episode_id,
            title=self.title,
            pain_point=self.pain_point,
            industry=self.industry,
            role=self.role,
            backend_summary=self.backend_summary,
            viewer_diy=self.viewer_diy,
            suggested_stack=self.suggested_stack,
            source_narration=self.source.narration,
            source_reference=(
                f"{self.source.document}, {self.source.heading}, "
                f"lines {self.source.line_start}-{self.source.line_end}"
            ),
            is_filled_episode=True,
            target_seconds=self.target_seconds,
            case_nature=self.case_nature,
            synthetic_data_only=True,
        )


class FilledEpisodeCatalog(BaseModel):
    source_document: str = Field(min_length=1)
    episodes: list[FilledEpisode] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_episodes(self):
        source_ids = [episode.source_id for episode in self.episodes]
        episode_ids = [episode.episode_id for episode in self.episodes]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("filled episode source IDs must be unique")
        if len(episode_ids) != len(set(episode_ids)):
            raise ValueError("filled episode production IDs must be unique")
        return self


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
    provider: str | None = None
    model: str | None = None
    voice_id: str | None = None
    chunk_manifest_path: str | None = None
    chunk_count: int = Field(default=0, ge=0)


class TTSVoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    category: str | None = None


class TTSVoiceCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    voices: list[TTSVoiceOption] = Field(default_factory=list)


class VoiceChunkQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    duration_seconds: float = Field(ge=0)
    rms_dbfs: float
    clipping_ratio: float = Field(ge=0, le=1)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    sample_width: int = Field(gt=0)
    issues: list[str] = Field(default_factory=list)


class VoiceChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    paragraph_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    audio_path: str = Field(min_length=1)
    alignment_path: str | None = None
    cache_key: str = Field(min_length=64, max_length=64)
    reused: bool = False
    start_seconds: float = Field(ge=0)
    speech_duration_seconds: float = Field(gt=0)
    trailing_pause_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    quality: VoiceChunkQuality

    @model_validator(mode="after")
    def validate_chunk_timing(self):
        expected = self.start_seconds + self.speech_duration_seconds + self.trailing_pause_seconds
        if abs(self.end_seconds - expected) > 0.002:
            raise ValueError("voice chunk end must equal start + speech + trailing pause")
        if not self.quality.passed:
            raise ValueError("only quality-approved voice chunks may enter the master timeline")
        return self


class VoiceChunkManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    episode_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    pause_seconds: float = Field(ge=0, le=2)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    sample_width: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    chunks: list[VoiceChunkRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_master_timeline(self):
        cursor = 0.0
        for chunk in self.chunks:
            if abs(chunk.start_seconds - cursor) > 0.002:
                raise ValueError("voice chunks must form one continuous master timeline")
            cursor = chunk.end_seconds
        if abs(self.duration_seconds - cursor) > 0.002:
            raise ValueError("manifest duration must match the final chunk end")
        return self


class PrototypeVisualFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    scene_id: str = Field(min_length=1)
    viewport: str = Field(min_length=1)
    moment: str = Field(min_length=1)
    issues: list[str] = Field(default_factory=list)
    scene_height: int | None = Field(default=None, alias="sceneHeight", ge=0)
    scroll_height: int | None = Field(default=None, alias="scrollHeight", ge=0)


class PrototypeVisualReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    findings: list[PrototypeVisualFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        has_failures = any(finding.issues for finding in self.findings)
        if self.ok == has_failures:
            raise ValueError("prototype visual report status must agree with its findings")
        return self


class PrototypeRepairIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["static_contract", "demo_contract", "visual_qa", "repair_provider"]
    message: str = Field(min_length=1)
    findings: list[PrototypeVisualFinding] = Field(default_factory=list)


class PrototypeRepairAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    status: Literal["repaired", "failed"]
    prompt_path: str = Field(min_length=1)
    log_path: str = Field(min_length=1)
    source_hash_before: str = Field(min_length=64, max_length=64)
    source_hash_after: str = Field(min_length=64, max_length=64)
    issues_before: list[PrototypeRepairIssue] = Field(min_length=1)
    issues_after: list[PrototypeRepairIssue] = Field(default_factory=list)


class PrototypeRepairReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    episode_id: str = Field(min_length=1)
    status: Literal["not_needed", "repaired", "failed"]
    max_attempts: int = Field(ge=0, le=4)
    attempts: list[PrototypeRepairAttempt] = Field(default_factory=list)
    final_issues: list[PrototypeRepairIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_repair_status(self):
        if self.status == "failed" and not self.final_issues:
            raise ValueError("failed prototype repair reports require final issues")
        if self.status in {"not_needed", "repaired"} and self.final_issues:
            raise ValueError("successful prototype repair reports cannot retain final issues")
        return self


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
    "system_stage", "queue_stage", "editorial_stage", "spatial_stage",
    "collage_stage", "map_stage", "metaphor_stage", "data_stage",
]
GraphicsObjectType = Literal[
    "channel", "document", "process", "decision", "database", "status",
    "metric", "person", "annotation", "text", "artifact", "map_region",
    "route", "boundary", "axis", "number", "quote", "figure", "evidence",
    "building", "phone", "check", "warning",
]
GraphicsActionType = Literal[
    "reveal", "highlight", "connect", "count_to", "stamp", "transform", "hold",
    "move", "trace", "draw", "wipe", "cross_out", "split", "merge", "scatter",
    "focus", "exit",
]


class GraphicsFrame(BaseModel):
    """Free-form portrait placement expressed as percentages of the graphics stage."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    width: float = Field(gt=0, le=100)
    height: float = Field(gt=0, le=100)
    rotation: float = Field(default=0, ge=-30, le=30)
    depth: Literal["background", "midground", "foreground"] = "midground"

    @model_validator(mode="after")
    def validate_visible_frame(self):
        if self.x + self.width > 100 or self.y + self.height > 100:
            raise ValueError("graphics frame must remain completely inside the stage")
        return self


class GraphicsObject(BaseModel):
    object_id: str
    object_type: GraphicsObjectType
    role: str
    label: str
    detail: str
    slot: Literal["hero", "left", "center", "right", "top", "bottom"]
    frame: GraphicsFrame | None = None
    visual_form: str = ""
    show_detail: bool = False
    initially_visible: bool = False


class GraphicsAction(BaseModel):
    at_seconds: float = Field(ge=0)
    action: GraphicsActionType
    target: str
    value: str | None = None
    source: str | None = None
    duration_seconds: float = Field(default=0.65, gt=0, le=4)
    anchor_text: str | None = None
    anchor_occurrence: int = Field(default=0, ge=0)
    direction: Literal["left", "right", "up", "down", "in", "out", "clockwise", "counterclockwise"] | None = None


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
    visual_world: str = ""
    opening_state: str = ""
    payoff_state: str = ""
    camera_move: Literal["locked", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down"] = "locked"
    continuity_object: str | None = None
    objects: list[GraphicsObject] = Field(min_length=1, max_length=7)
    actions: list[GraphicsAction] = Field(min_length=1, max_length=16)
    review_checkpoints: list[float] = Field(default_factory=list, max_length=3)

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
            if action.action == "connect" and not action.source:
                raise ValueError(f"graphics connect action requires a source in {self.scene_id}")
            if action.at_seconds > duration + 0.05:
                raise ValueError(f"graphics action exceeds {self.scene_id} duration")
        for checkpoint in self.review_checkpoints:
            if checkpoint < 0 or checkpoint > duration + 0.05:
                raise ValueError(f"graphics checkpoint exceeds {self.scene_id} duration")
        return self


class GraphicsPlan(BaseModel):
    episode_id: str
    duration_seconds: float = Field(gt=0)
    theme: GraphicsTheme = "editorial"
    creative_thesis: str
    scenes: list[GraphicsScenePlan] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graphics_plan(self):
        ids = [scene.scene_id for scene in self.scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("graphics scene IDs must be unique")
        return self


class GraphicsVisualFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(min_length=1)
    moment: str = Field(min_length=1)
    time_seconds: float = Field(ge=0)
    frame: int = Field(ge=0)
    issues: list[str] = Field(default_factory=list)


class GraphicsVisualReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    fps: Literal[24, 30, 60]
    findings: list[GraphicsVisualFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        has_failures = any(finding.issues for finding in self.findings)
        if self.ok == has_failures:
            raise ValueError("graphics visual report status must agree with its findings")
        return self


class DemoAction(BaseModel):
    at_seconds: float = 0.0
    action: Literal["goto", "click", "upload", "wait", "screenshot", "assert_text"]
    selector: str | None = None
    value: str | None = None
    milliseconds: int | None = None

    @model_validator(mode="after")
    def validate_action_contract(self):
        if self.action == "goto" and not self.value:
            raise ValueError("goto actions require a URL value")
        if self.action == "click" and not self.selector:
            raise ValueError("click actions require a selector")
        if self.action == "upload" and (not self.selector or not self.value):
            raise ValueError("upload actions require a selector and file value")
        if self.action == "wait" and self.milliseconds is not None and self.milliseconds < 0:
            raise ValueError("wait milliseconds must be non-negative")
        if self.action == "assert_text" and (not self.selector or self.value is None):
            raise ValueError("assert_text actions require a selector and expected value")
        return self


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
    voice_id: str | None = None

    @field_validator("provider", "model")
    @classmethod
    def require_value(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("voice_id")
    @classmethod
    def normalize_voice_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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

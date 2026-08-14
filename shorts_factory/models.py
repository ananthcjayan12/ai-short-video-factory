from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EpisodeStage(str, Enum):
    INPUT = "input"
    NARRATION_READY = "narration_ready"
    VOICE_READY = "voice_ready"
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
    format: Literal["vertical_short"] = "vertical_short"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    synthetic_data_only: bool = True


class Narration(BaseModel):
    episode_id: str
    text: str
    word_count: int
    target_seconds: float
    hook: str
    consultation_line: str


class VoiceMetadata(BaseModel):
    episode_id: str
    audio_path: str
    duration_seconds: float
    source: Literal["generated", "manual", "mock"] = "manual"
    transcript_path: str | None = None


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
    max_visual_moments: int = 7
    max_generated_assets: int = 5
    max_scene_seconds: float = 8.0
    max_consecutive_non_talking_head_seconds: float = 16.0
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


class DemoAction(BaseModel):
    at_seconds: float = 0.0
    action: Literal["goto", "click", "upload", "wait", "screenshot", "assert_text"]
    selector: str | None = None
    value: str | None = None
    milliseconds: int | None = None


class DemoJob(BaseModel):
    job_id: str
    scene_id: str
    url: str
    viewport_width: int = 1080
    viewport_height: int = 1920
    output_path: str
    actions: list[DemoAction]


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

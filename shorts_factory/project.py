from __future__ import annotations

from pathlib import Path

from .io import load_model, write_json
from .models import EpisodeBrief, EpisodeStage, EpisodeState, ProjectSettings


FOLDERS = [
    "00_input", "01_narration", "02_voice", "03_director", "04_prototype",
    "05_asset_jobs", "06_recordings", "07_talking_head", "08_graphics",
    "09_composition", "10_final", "_requests", "_control",
]


class ProjectStore:
    def __init__(self, root: Path | str = "projects") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, episode_id: str) -> Path:
        return self.root / episode_id

    def settings(self) -> ProjectSettings:
        path = self.root / ".svf-project.json"
        if not path.exists():
            return ProjectSettings()
        return load_model(path, ProjectSettings)

    def save_settings(self, settings: ProjectSettings) -> ProjectSettings:
        write_json(self.root / ".svf-project.json", settings)
        return settings

    def create(self, brief: EpisodeBrief, *, overwrite: bool = False) -> Path:
        d = self.project_dir(brief.episode_id)
        if d.exists() and not overwrite:
            raise FileExistsError(f"Episode exists: {brief.episode_id}")
        d.mkdir(parents=True, exist_ok=True)
        for folder in FOLDERS:
            (d / folder).mkdir(parents=True, exist_ok=True)
        write_json(d / "00_input/episode_brief.json", brief)
        write_json(d / "episode-state.json", EpisodeState(episode_id=brief.episode_id))
        return d

    def brief(self, episode_id: str) -> EpisodeBrief:
        return load_model(self.project_dir(episode_id) / "00_input/episode_brief.json", EpisodeBrief)

    def state(self, episode_id: str) -> EpisodeState:
        return load_model(self.project_dir(episode_id) / "episode-state.json", EpisodeState)

    def transition(self, episode_id: str, stage: EpisodeStage) -> EpisodeState:
        state = self.state(episode_id)
        state.stage = stage
        write_json(self.project_dir(episode_id) / "episode-state.json", state)
        return state

    def approve_director(self, episode_id: str) -> EpisodeState:
        state = self.state(episode_id)
        state.approved_director = True
        state.stage = EpisodeStage.DIRECTOR_APPROVED
        write_json(self.project_dir(episode_id) / "episode-state.json", state)
        return state

    def approve_final(self, episode_id: str) -> EpisodeState:
        state = self.state(episode_id)
        state.approved_final = True
        state.stage = EpisodeStage.APPROVED
        write_json(self.project_dir(episode_id) / "episode-state.json", state)
        return state

    def next_version(self, episode_id: str, key: str) -> int:
        state = self.state(episode_id)
        version = state.versions.get(key, 0) + 1
        state.versions[key] = version
        write_json(self.project_dir(episode_id) / "episode-state.json", state)
        return version

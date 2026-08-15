from pathlib import Path
from shorts_factory.models import EpisodeBrief, EpisodeStage, ProjectSettings
from shorts_factory.project import ProjectStore


def test_project_state_machine(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    brief = EpisodeBrief(episode_id="x", title="X", pain_point="Pain", industry="Test", role="Owner")
    store.create(brief)
    assert store.state("x").stage == EpisodeStage.INPUT
    store.transition("x", EpisodeStage.NARRATION_READY)
    assert store.state("x").stage == EpisodeStage.NARRATION_READY


def test_project_settings_are_shared_across_episodes(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    assert store.settings().include_talking_head is True
    store.save_settings(ProjectSettings(include_talking_head=False))
    assert ProjectStore(tmp_path / "projects").settings().include_talking_head is False

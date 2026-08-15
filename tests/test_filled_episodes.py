from __future__ import annotations

from fastapi.testclient import TestClient

from shorts_factory.filled_episodes import (
    DEFAULT_SOURCE_PATH,
    materialize_filled_episode,
    parse_filled_episode_catalog,
)
from shorts_factory.models import EpisodeStage
from shorts_factory.project import ProjectStore
from shorts_factory.ui import server


def test_markdown_story_library_parses_into_100_validated_episode_contracts():
    catalog = parse_filled_episode_catalog(DEFAULT_SOURCE_PATH)

    assert len(catalog.episodes) == 100
    assert [episode.source_id for episode in catalog.episodes] == [
        f"PAIN-{index:03d}" for index in range(1, 101)
    ]
    assert len({episode.episode_id for episode in catalog.episodes}) == 100
    assert {episode.industry for episode in catalog.episodes} == {
        "Contractor / Handyman", "Property Management", "Hotels", "Bookkeeping", "Restaurant",
        "E-commerce / Retail", "Recruiting / Staffing", "Law Firm", "Dental Clinic", "Logistics / Freight",
    }
    assert all(episode.backend_summary for episode in catalog.episodes)
    assert all(episode.viewer_diy for episode in catalog.episodes)
    assert all(episode.suggested_stack for episode in catalog.episodes)
    assert all(episode.source.narration for episode in catalog.episodes)


def test_materialized_filled_episode_is_input_only_and_retains_its_source(tmp_path):
    episode = parse_filled_episode_catalog(DEFAULT_SOURCE_PATH).episodes[0]
    store = ProjectStore(tmp_path / "projects")

    project = materialize_filled_episode(store, episode)

    brief = store.brief(episode.episode_id)
    assert store.state(episode.episode_id).stage.value == "input"
    assert brief.is_filled_episode is True
    assert brief.source_narration == episode.source.narration
    assert brief.source_reference and "lines" in brief.source_reference
    assert (project / "00_input/filled_episode_source.json").exists()
    assert (project / "00_input/source_narration.md").exists()
    assert not (project / "01_narration/narration.json").exists()


def test_factory_desk_lists_and_initializes_filled_episode_without_running_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    client = TestClient(server.app)

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert len(dashboard.json()["filled_episodes"]) == 100
    assert dashboard.json()["filled_episodes"][0]["imported"] is False

    created = client.post("/api/filled-episodes/PAIN-001/create")
    assert created.status_code == 201
    assert created.json()["brief"]["episode_id"] == "filled-pain-001"
    assert created.json()["state"]["stage"] == "input"
    assert created.json()["narration"] is None

    refreshed = client.get("/api/dashboard").json()
    assert refreshed["filled_episodes"][0]["imported"] is True
    assert refreshed["filled_episodes"][0]["progress"] == 8

    duration = client.put(
        "/api/episodes/filled-pain-001/duration", json={"target_seconds": 480},
    )
    assert duration.status_code == 200
    assert duration.json()["brief"]["target_seconds"] == 480
    assert duration.json()["state"]["stage"] == "input"
    assert duration.json()["narration"] is None

    too_long = client.put(
        "/api/episodes/filled-pain-001/duration", json={"target_seconds": 481},
    )
    assert too_long.status_code == 422

    ProjectStore(server.PROJECTS_ROOT).transition("filled-pain-001", EpisodeStage.NARRATION_READY)
    locked = client.put(
        "/api/episodes/filled-pain-001/duration", json={"target_seconds": 120},
    )
    assert locked.status_code == 409
    assert "before narration" in locked.json()["detail"]

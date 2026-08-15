from __future__ import annotations

import time
import sys
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from shorts_factory.ui import server
from shorts_factory.models import EpisodeBrief, ProductionJob
from shorts_factory.project import ProjectStore


def test_factory_desk_create_and_run_validated_job(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    client = TestClient(server.app)

    created = client.post(
        "/api/episodes",
        json={
            "episode_id": "pain-ui",
            "title": "Invoice exception finder",
            "pain_point": "Operators manually inspect every invoice even when most are correct.",
            "industry": "Operations",
            "role": "Finance lead",
            "target_seconds": 58,
        },
    )
    assert created.status_code == 201
    assert created.json()["state"]["stage"] == "input"

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["episodes"][0]["episode_id"] == "pain-ui"
    assert dashboard.json()["settings"]["include_talking_head"] is True
    assert all(action["capability"] for action in dashboard.json()["actions"])

    settings = client.put("/api/project/settings", json={"include_talking_head": False})
    assert settings.status_code == 200
    assert settings.json()["include_talking_head"] is False
    assert client.get("/api/dashboard").json()["settings"]["include_talking_head"] is False

    started = client.post("/api/episodes/pain-ui/actions/narrate-mock", json={})
    assert started.status_code == 202
    assert started.json()["capability"] == "structured"

    job_id = started.json()["job_id"]
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.01)
    assert job["status"] == "succeeded"
    detail = client.get("/api/episodes/pain-ui").json()
    assert detail["narration"]["word_count"] > 0
    assert (tmp_path / "projects/pain-ui/_control/jobs" / f"{job_id}.json").exists()
    assert client.get("/api/episodes/pain-ui/progress").json()["events"][-1]["status"] == "succeeded"
    job_logs = client.get(f"/api/jobs/{job_id}/logs")
    assert job_logs.status_code == 200
    assert job_logs.json()["lines"]
    prompt_records = client.get("/api/episodes/pain-ui/prompts").json()["records"]
    assert {record["invocation"]["task"] for record in prompt_records} >= {"story_structure", "narration"}

    model_map = client.put(
        "/api/episodes/pain-ui/models",
        json={"tasks": {"director": {"provider": "mock", "model": "deterministic"}}},
    )
    assert model_map.status_code == 200
    assert model_map.json()["tasks"]["director"]["provider"] == "mock"

    grok_map = client.put(
        "/api/episodes/pain-ui/models",
        json={"tasks": {"director": {"provider": "grok", "model": "grok-4.5", "reasoning_effort": "high"}}},
    )
    assert grok_map.status_code == 200
    assert grok_map.json()["tasks"]["director"]["reasoning_effort"] == "high"

    voice_map = client.put(
        "/api/episodes/pain-ui/models",
        json={"tasks": {"voice_generator": {"provider": "elevenlabs", "model": "eleven_v3"}}},
    )
    assert voice_map.status_code == 200
    assert voice_map.json()["tasks"]["voice_generator"]["provider"] == "elevenlabs"

    invalid_map = client.put(
        "/api/episodes/pain-ui/models",
        json={"tasks": {"screen_recorder": {"provider": "codex", "model": "gpt-5.6-sol"}}},
    )
    assert invalid_map.status_code == 422

    reset = client.post(
        "/api/episodes/pain-ui/reset", json={"from_stage": "narration", "confirm": True},
    )
    assert reset.status_code == 200
    assert (tmp_path / "projects/pain-ui/01_narration").exists()
    assert not (tmp_path / "projects/pain-ui/01_narration/narration.json").exists()
    assert list((tmp_path / "projects/pain-ui/_control/archive").glob("*/01_narration/narration.json"))


def test_factory_desk_rejects_invalid_episode_and_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    client = TestClient(server.app)

    response = client.post(
        "/api/episodes",
        json={
            "episode_id": "Not Safe!",
            "title": "Invalid identifier",
            "pain_point": "This request should fail schema validation.",
        },
    )
    assert response.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        server._safe_project_file("missing", "../../outside.txt")
    assert exc_info.value.status_code == 403


def test_prototype_route_serves_built_dist_and_relative_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    project = ProjectStore(server.PROJECTS_ROOT)
    project.create(EpisodeBrief(
        episode_id="prototype-ui", title="Prototype", pain_point="A static prototype must load its assets.",
        industry="Test", role="Owner",
    ))
    prototype_root = server.PROJECTS_ROOT / "prototype-ui/04_prototype"
    dist = prototype_root / "dist"
    dist.mkdir(parents=True)
    (prototype_root / "index.html").write_text("source prototype")
    (dist / "index.html").write_text('<link rel="stylesheet" href="./styles.css">built prototype')
    (dist / "styles.css").write_text("body { color: green; }")

    client = TestClient(server.app)

    index = client.get("/prototype/prototype-ui/index.html")
    stylesheet = client.get("/prototype/prototype-ui/styles.css")

    assert index.status_code == 200
    assert "built prototype" in index.text
    assert stylesheet.status_code == 200
    assert "color: green" in stylesheet.text


def test_factory_desk_accepts_long_pain_point(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    client = TestClient(server.app)
    long_pain_point = (
        "Invoices arrive through email, paper, photos, and forwarded messages. " * 30
    )
    assert len(long_pain_point) > 1000

    response = client.post(
        "/api/episodes",
        json={
            "episode_id": "pain-long",
            "title": "Omnichannel invoice inbox",
            "pain_point": long_pain_point,
            "industry": "Small Business",
            "role": "Owner",
            "target_seconds": 58,
            "case_nature": "real",
        },
    )

    assert response.status_code == 201
    assert response.json()["brief"]["pain_point"] == long_pain_point
    assert response.json()["brief"]["case_nature"] == "real"


def test_running_job_can_be_terminated_with_its_process_group(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    test_queue = server.JobQueue()
    monkeypatch.setattr(server, "queue", test_queue)
    monkeypatch.setattr(
        test_queue,
        "_command",
        lambda job: [sys.executable, "-c", "import time; print('worker ready', flush=True); time.sleep(30)"],
    )
    client = TestClient(server.app)
    created = client.post(
        "/api/episodes",
        json={
            "episode_id": "terminate-ui",
            "title": "Termination test",
            "pain_point": "A mistaken production action must be cancellable.",
        },
    )
    assert created.status_code == 201
    started = client.post("/api/episodes/terminate-ui/actions/narrate-mock", json={})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    for _ in range(100):
        running = client.get(f"/api/jobs/{job_id}").json()
        if running["status"] == "running" and running["pid"]:
            break
        time.sleep(0.01)
    assert running["status"] == "running"

    stopped = client.post(f"/api/jobs/{job_id}/terminate")

    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert "preserved" in stopped.json()["message"]
    time.sleep(0.05)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "stopped"
    test_queue._executor.shutdown(wait=True, cancel_futures=True)


def test_starting_worker_is_not_marked_interrupted_before_it_has_a_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECTS_ROOT", tmp_path / "projects")
    test_queue = server.JobQueue()
    now = datetime.now(UTC).isoformat()
    job = ProductionJob(
        job_id="startup-race", episode_id="startup-episode", action="narrate-mock",
        label="Draft narration offline", stage="story", task="narration_writer", capability="structured",
        status="running", message="Starting worker", created_at=now, updated_at=now,
    )
    ProjectStore(server.PROJECTS_ROOT).create(EpisodeBrief(
        episode_id="startup-episode", title="Startup race", pain_point="A worker starts before it has a PID.",
        industry="Test", role="Owner",
    ))
    test_queue._save(job)

    recovered = test_queue.get(job.job_id)

    assert recovered is not None
    assert recovered.status == "running"
    test_queue._executor.shutdown(wait=True, cancel_futures=True)

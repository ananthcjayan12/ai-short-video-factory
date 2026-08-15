from __future__ import annotations

import json

import pytest

from shorts_factory.io import load_model
from shorts_factory.models import EpisodeBrief, PrototypeRepairIssue, PrototypeRepairReport
from shorts_factory.orchestrator import default_config, resolve_task
from shorts_factory.pipeline import repair_prototype
from shorts_factory import pipeline
from shorts_factory.project import ProjectStore


def _store_with_prototype(tmp_path) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "projects")
    episode_id = "repair-test"
    store.create(EpisodeBrief(
        episode_id=episode_id, title="Repair test",
        pain_point="A generated prototype can fail a deterministic browser contract.",
        industry="Test", role="Operator",
    ))
    prototype = store.project_dir(episode_id) / "04_prototype"
    prototype.mkdir(parents=True, exist_ok=True)
    (prototype / "app.js").write_text('data-testid="scene-S05"\n', encoding="utf-8")
    return store, episode_id


def test_prototype_repair_is_independently_routed():
    route = resolve_task(default_config(), "prototype_repair")
    assert route["capability"] == "code"
    assert route["provider"] == "codex"
    assert route["model"] == "gpt-5.6-sol"


def test_bounded_prototype_repair_archives_edits_and_revalidates(tmp_path, monkeypatch):
    store, episode_id = _store_with_prototype(tmp_path)
    issue = PrototypeRepairIssue(
        stage="visual_qa", message="Scene root selector has the wrong case",
    )
    validation_results = iter([(None, [issue]), (store.project_dir(episode_id) / "04_prototype/index.html", [])])
    monkeypatch.setattr(pipeline, "_prototype_validation_issues", lambda *args: next(validation_results))

    def fake_repair_agent(*, route, prompt, out_dir, timeout):
        source = out_dir / "app.js"
        source.write_text(source.read_text(encoding="utf-8").replace("scene-S05", "scene-s05"), encoding="utf-8")
        return 0, "repaired selector case"

    monkeypatch.setattr(pipeline, "_run_prototype_repair_agent", fake_repair_agent)
    report = repair_prototype(store, episode_id, max_attempts=2)

    project = store.project_dir(episode_id)
    assert report.status == "repaired"
    assert len(report.attempts) == 1
    assert report.attempts[0].source_hash_before != report.attempts[0].source_hash_after
    assert list((project / "_requests/prototype_repairs").glob("run-*/attempt-01/before/app.js"))
    assert "scene-s05" in (project / "04_prototype/app.js").read_text(encoding="utf-8")
    saved = load_model(project / "_requests/prototype_repair_report.json", PrototypeRepairReport)
    assert saved.status == "repaired"
    prompt = (project / saved.attempts[0].prompt_path).read_text(encoding="utf-8")
    assert "Never weaken, bypass, hide, or special-case a validator" in prompt
    assert 'data-testid="scene-<lowercase-scene-id>"' in prompt


def test_failed_prototype_repair_stays_failed_after_limit(tmp_path, monkeypatch):
    store, episode_id = _store_with_prototype(tmp_path)
    issue = PrototypeRepairIssue(stage="static_contract", message="Missing required entrypoint")
    monkeypatch.setattr(pipeline, "_prototype_validation_issues", lambda *args: (None, [issue]))
    monkeypatch.setattr(
        pipeline, "_run_prototype_repair_agent",
        lambda **kwargs: (2, "provider failed without changing the prototype"),
    )

    with pytest.raises(RuntimeError, match="exhausted 1 attempt"):
        repair_prototype(store, episode_id, max_attempts=1)

    report_path = store.project_dir(episode_id) / "_requests/prototype_repair_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["attempts"][0]["status"] == "failed"
    assert payload["final_issues"]

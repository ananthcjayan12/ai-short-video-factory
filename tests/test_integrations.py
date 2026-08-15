from __future__ import annotations

import subprocess

import pytest

from shorts_factory import agents, integrations
from shorts_factory.agents import ProviderAgent
from shorts_factory.models import StoryPlan, TaskModelSelection


def test_codex_adapter_uses_read_only_structured_contract(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, *, prompt=None, cwd=None, timeout):
        captured.update(command=command, prompt=prompt, cwd=cwd, timeout=timeout)
        output = command[command.index("--output-last-message") + 1]
        with open(output, "w", encoding="utf-8") as handle:
            handle.write('{"provider":"codex","model":"gpt-5.6-sol","reasoning_effort":"high"}')
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(integrations, "_require_binary", lambda *args, **kwargs: "/bin/codex")
    monkeypatch.setattr(integrations, "_run", fake_run)
    schema = TaskModelSelection.model_json_schema()
    result = integrations.invoke_structured_provider(
        provider="codex", model="gpt-5.6-sol", prompt="Choose a route", schema=schema,
        timeout=30, reasoning_effort="high",
    )
    assert result.payload["reasoning_effort"] == "high"
    assert "read-only" in captured["command"]
    assert "--output-schema" in captured["command"]
    assert 'model_reasoning_effort="high"' in captured["command"]
    assert "JSON SCHEMA" in captured["prompt"]


def test_codex_strict_schema_requires_every_object_property():
    schema = integrations._strict_schema(StoryPlan.model_json_schema())

    def assert_strict(node):
        if isinstance(node, list):
            for item in node:
                assert_strict(item)
            return
        if not isinstance(node, dict):
            return
        assert "default" not in node
        if node.get("type") == "object" or "properties" in node:
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node.get("properties", {}))
        for value in node.values():
            assert_strict(value)

    assert_strict(schema)
    story_beat = schema["$defs"]["StoryBeat"]
    assert "claim_ids" in story_beat["required"]
    assert "ai_responsibility" in story_beat["required"]


def test_provider_agent_rejects_unvalidated_result(tmp_path, monkeypatch):
    monkeypatch.setattr(
        agents,
        "invoke_structured_provider",
        lambda **kwargs: integrations.StructuredProviderResult(
            payload={"provider": "codex"}, provider="codex", model="gpt-5.6-sol",
        ),
    )
    agent = ProviderAgent(provider="codex", model="gpt-5.6-sol", retries=0)
    with pytest.raises(RuntimeError, match="validation error"):
        agent.run(
            stage="route", prompt="Choose", output_model=TaskModelSelection,
            request_dir=tmp_path,
        )
    assert (tmp_path / "route_invocation.json").read_text(encoding="utf-8").find('"status": "failed"') >= 0
    assert (tmp_path / "route_response.json").read_text(encoding="utf-8").find('"provider": "codex"') >= 0


def test_elevenlabs_response_contract_validates_alignment():
    response = integrations.ElevenLabsTTSResponse.model_validate({
        "audio_base64": "AA==",
        "alignment": {
            "characters": ["H", "i"],
            "character_start_times_seconds": [0.0, 0.1],
            "character_end_times_seconds": [0.1, 0.2],
        },
    })
    assert response.alignment is not None
    assert response.alignment.characters == ["H", "i"]

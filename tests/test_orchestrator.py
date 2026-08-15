import pytest
from shorts_factory.orchestrator import PROVIDERS, default_config, provider_models, resolve_task


def test_capability_route_is_explicit():
    cfg = default_config()
    route = resolve_task(cfg, "director")
    assert route["capability"] == "structured"
    assert route["provider"] == "claude_code"


def test_invalid_capability_route_fails():
    cfg = default_config()
    cfg["tasks"]["screen_recorder"]["provider"] = "codex"
    with pytest.raises(ValueError):
        resolve_task(cfg, "screen_recorder")


def test_reference_ai_integrations_are_registered_with_explicit_capabilities():
    expected = {
        "codex", "claude_code", "anthropic", "gemini", "grok", "antigravity",
        "copilot", "moonshot", "zai", "elevenlabs",
    }
    assert expected <= set(PROVIDERS)
    assert "structured" in PROVIDERS["grok"]["capabilities"]
    assert PROVIDERS["elevenlabs"]["capabilities"] == ["audio"]
    assert "code" not in PROVIDERS["antigravity"]["capabilities"]


def test_gemini_text_and_tts_models_cannot_be_cross_routed():
    assert provider_models("gemini", "audio") == ["gemini-3.1-flash-tts-preview"]
    cfg = default_config()
    cfg["tasks"]["director"].update({"provider": "gemini", "model": "gemini-3.1-flash-tts-preview"})
    with pytest.raises(ValueError, match="not registered"):
        resolve_task(cfg, "director")
    cfg["tasks"]["voice_generator"].update({"provider": "gemini", "model": "gemini-3.1-flash-tts-preview"})
    resolved = resolve_task(cfg, "voice_generator")
    assert resolved["capability"] == "audio"
    assert resolved["timeout_seconds"] == 900


def test_reasoning_effort_is_validated_for_cli_provider():
    cfg = default_config()
    cfg["tasks"]["director"].update({
        "provider": "grok", "model": "grok-4.5", "reasoning_effort": "ultra",
    })
    with pytest.raises(ValueError, match="reasoning effort"):
        resolve_task(cfg, "director")

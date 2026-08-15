from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[1]
NATIVE_STRUCTURED_PROVIDERS = {
    "anthropic", "antigravity", "claude_code", "codex", "copilot", "gemini", "grok", "moonshot", "zai",
}
GEMINI_MIN_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class StructuredProviderResult:
    payload: dict[str, Any]
    provider: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


class CharacterAlignment(BaseModel):
    characters: list[str] = Field(default_factory=list)
    character_start_times_seconds: list[float] = Field(default_factory=list)
    character_end_times_seconds: list[float] = Field(default_factory=list)


class ElevenLabsTTSResponse(BaseModel):
    audio_base64: str
    alignment: CharacterAlignment | None = None
    normalized_alignment: CharacterAlignment | None = None


class TTSResult(BaseModel):
    provider: str
    model: str
    voice_id: str
    audio_path: str
    alignment_path: str | None = None


def load_env() -> None:
    """Load local .env values without overriding the operator's environment."""
    for path in (REPO_ROOT / ".env", REPO_ROOT.parent / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    def normalize(node: Any) -> Any:
        if isinstance(node, list):
            return [normalize(item) for item in node]
        if not isinstance(node, dict):
            return node
        # OpenAI/Codex strict structured output does not accept JSON-Schema
        # defaults and requires every declared object property to be listed in
        # `required`. Pydantic omits defaulted fields from that list, so adapt
        # only the provider-facing schema; the original Pydantic model remains
        # the authoritative local validator.
        result = {key: normalize(value) for key, value in node.items() if key != "default"}
        if result.get("type") == "object" or "properties" in result:
            result["additionalProperties"] = False
            result["required"] = list(result.get("properties", {}).keys())
        return result

    return normalize(schema)


def _extract_json(text: str, provider: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise RuntimeError(f"{provider} returned no JSON object") from None
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{provider} returned JSON, but not an object")
    return payload


def _run(
    command: list[str], *, prompt: str | None = None, cwd: Path | None = None, timeout: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, input=prompt, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Provider command timed out after {timeout} seconds") from exc


def _require_binary(name: str, env_var: str, extra: tuple[Path, ...] = ()) -> str:
    configured = os.getenv(env_var, "").strip()
    candidates = [Path(configured)] if configured else []
    discovered = shutil.which(name)
    if discovered:
        candidates.append(Path(discovered))
    candidates.extend(extra)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError(f"{name} CLI was not found; install it or set {env_var}")


def _bounded_prompt(prompt: str, schema: dict[str, Any]) -> str:
    return (
        "You are a bounded structured-output worker. Do not edit files, browse, use tools, or run commands. "
        "Return only one JSON object that conforms to the supplied schema.\n\n"
        f"TASK\n{prompt}\n\nJSON SCHEMA\n{json.dumps(schema, separators=(',', ':'))}"
    )


def _invoke_cli(
    provider: str, model: str, prompt: str, schema: dict[str, Any], timeout: int,
    reasoning_effort: str | None,
) -> StructuredProviderResult:
    provider_schema = _strict_schema(schema)
    routed_prompt = _bounded_prompt(prompt, provider_schema)
    effort = reasoning_effort or ("high" if provider == "grok" else "low")
    with tempfile.TemporaryDirectory(prefix=f"svf-{provider}-") as directory:
        temp = Path(directory)
        output_path = temp / "response.json"
        schema_path = temp / "schema.json"
        schema_path.write_text(json.dumps(provider_schema), encoding="utf-8")

        if provider == "codex":
            binary = _require_binary(
                "codex", "SVF_CODEX_BIN",
                tuple(sorted((Path.home() / ".vscode/extensions").glob("openai.chatgpt-*/bin/*/codex"), reverse=True)),
            )
            command = [
                binary, "exec", "-", "--ephemeral", "--sandbox", "read-only", "--color", "never",
                "--output-last-message", str(output_path), "--output-schema", str(schema_path),
                "--cd", str(REPO_ROOT), "--model", model,
                "--config", f'model_reasoning_effort="{effort}"',
            ]
            result = _run(command, prompt=routed_prompt, timeout=timeout)
            response = output_path.read_text(encoding="utf-8") if output_path.exists() else result.stdout
        elif provider == "grok":
            binary = _require_binary(
                "grok", "SVF_GROK_BIN", (Path.home() / ".local/bin/grok", Path.home() / ".grok/bin/grok"),
            )
            command = [
                binary, "--no-auto-update", "--verbatim", "-p", routed_prompt,
                "--system-prompt-override", "Return only the requested JSON. Do not use tools or edit files.",
                "--tools", "read_file,list_dir,grep", "--output-format", "plain", "--cwd", str(REPO_ROOT),
                "--model", model, "--effort", effort, "--sandbox", "read-only",
                "--permission-mode", "dontAsk", "--max-turns", "16", "--no-plan", "--no-subagents",
                "--no-memory", "--disable-web-search",
            ]
            result = _run(command, timeout=timeout)
            response = result.stdout
        elif provider == "antigravity":
            binary = _require_binary("agy", "SVF_ANTIGRAVITY_BIN", (Path.home() / ".local/bin/agy",))
            command = [binary, "--print", routed_prompt, "--sandbox"]
            if model not in {"authenticated-default", "default", "auto"}:
                command.extend(["--model", model])
            result = _run(command, cwd=temp, timeout=timeout)
            response = result.stdout
        elif provider == "copilot":
            binary = _require_binary("copilot", "SVF_COPILOT_BIN", (Path.home() / ".local/bin/copilot",))
            command = [
                binary, "-p", routed_prompt, "-s", "--model", model, "--stream=off", "--no-ask-user",
                "--no-auto-update", "--no-color", "--no-custom-instructions",
            ]
            result = _run(command, cwd=temp, timeout=timeout)
            response = result.stdout
        elif provider == "claude_code":
            binary = _require_binary("claude", "SVF_CLAUDE_BIN")
            command = [binary, "--model", model, "-p", routed_prompt]
            result = _run(command, cwd=temp, timeout=timeout)
            response = result.stdout
        else:
            raise RuntimeError(f"Unsupported CLI provider: {provider}")

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-3000:]
            raise RuntimeError(f"{provider} CLI exited with code {result.returncode}: {detail}")
        if not response.strip():
            raise RuntimeError(f"{provider} CLI returned no response")
        return StructuredProviderResult(
            payload=_extract_json(response, provider), provider=provider, model=model,
        )


def _request_json(request: urllib.request.Request, *, provider: str, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-3000:]
        raise RuntimeError(f"{provider} API failed with HTTP {exc.code}: {detail}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{provider} API timed out after {timeout} seconds") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{provider} API returned an invalid response")
    return payload


def _api_key(provider: str) -> str:
    load_env()
    names = {
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "moonshot": ("MOONSHOT_API_KEY",),
        "zai": ("ZAI_API_KEY", "ZHIPU_API_KEY", "BIGMODEL_API_KEY"),
    }[provider]
    for name in names:
        if os.getenv(name):
            return os.environ[name]
    raise RuntimeError(f"{provider} requires one of: {', '.join(names)}")


def _invoke_anthropic(model: str, prompt: str, schema: dict[str, Any], timeout: int) -> StructuredProviderResult:
    strict = _strict_schema(schema)

    def compatible(node: Any) -> Any:
        if isinstance(node, list):
            return [compatible(value) for value in node]
        if not isinstance(node, dict):
            return node
        unsupported = {"minimum", "maximum", "minLength", "maxLength", "maxItems"}
        result = {key: compatible(value) for key, value in node.items() if key not in unsupported}
        if result.get("type") == "array" and int(result.get("minItems", 0) or 0) > 1:
            result["minItems"] = 1
        return result

    payload = {
        "model": model,
        "max_tokens": int(os.getenv("SVF_ANTHROPIC_MAX_TOKENS", "16384")),
        "system": "Return only schema-valid JSON. Do not use tools.",
        "messages": [{"role": "user", "content": prompt}],
        "output_config": {"format": {"type": "json_schema", "schema": compatible(strict)}},
    }
    request = urllib.request.Request(
        os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/") + "/v1/messages",
        data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": _api_key("anthropic")},
    )
    data = _request_json(request, provider="anthropic", timeout=timeout)
    if data.get("stop_reason") in {"max_tokens", "refusal"}:
        raise RuntimeError(f"Anthropic stopped with {data['stop_reason']}")
    text = "\n".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    usage = data.get("usage") or {}
    return StructuredProviderResult(
        payload=_extract_json(text, "anthropic"), provider="anthropic", model=model,
        usage={"input_tokens": int(usage.get("input_tokens", 0)), "output_tokens": int(usage.get("output_tokens", 0))},
    )


def _gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "$defs", "$ref", "type", "format", "title", "description", "enum", "items", "prefixItems",
        "minItems", "maxItems", "minimum", "maximum", "anyOf", "oneOf", "properties", "required",
        "additionalProperties", "propertyOrdering",
    }

    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(value) for value in node]
        if not isinstance(node, dict):
            return node
        return {
            key: ({name: clean(value) for name, value in child.items()} if key in {"properties", "$defs"} else clean(child))
            for key, child in node.items() if key in allowed
        }

    return clean(schema)


def _invoke_gemini(model: str, prompt: str, schema: dict[str, Any], timeout: int) -> StructuredProviderResult:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Gemini integration requires: pip install -e '.[ai]'") from exc
    http_options = types.HttpOptions(timeout=max(GEMINI_MIN_TIMEOUT_SECONDS, timeout) * 1000)
    client = genai.Client(api_key=_api_key("gemini"), http_options=http_options)
    response = client.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="Return only schema-valid JSON. Do not use tools.",
            response_mime_type="application/json", response_json_schema=_gemini_schema(schema),
            max_output_tokens=int(os.getenv("SVF_GEMINI_MAX_OUTPUT_TOKENS", "16384")),
            http_options=http_options,
        ),
    )
    text = (getattr(response, "text", None) or "").strip()
    usage_meta = getattr(response, "usage_metadata", None)
    usage = {
        "input_tokens": int(getattr(usage_meta, "prompt_token_count", 0) or 0),
        "output_tokens": int(getattr(usage_meta, "candidates_token_count", 0) or 0),
    }
    return StructuredProviderResult(payload=_extract_json(text, "gemini"), provider="gemini", model=model, usage=usage)


def _invoke_openai_compatible(
    provider: str, model: str, prompt: str, timeout: int, reasoning_effort: str | None,
) -> StructuredProviderResult:
    urls = {
        "moonshot": os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1/chat/completions"),
        "zai": os.getenv("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/chat/completions"),
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only a JSON object. Do not use tools."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": int(os.getenv(f"SVF_{provider.upper()}_MAX_TOKENS", "16384")),
        "response_format": {"type": "json_object"},
    }
    if provider == "zai":
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = reasoning_effort or "high"
    request = urllib.request.Request(
        urls[provider], data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {_api_key(provider)}", "Content-Type": "application/json"},
    )
    data = _request_json(request, provider=provider, timeout=timeout)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"{provider} returned no choices")
    text = str((choices[0].get("message") or {}).get("content") or "")
    usage_raw = data.get("usage") or {}
    return StructuredProviderResult(
        payload=_extract_json(text, provider), provider=provider, model=model,
        usage={"input_tokens": int(usage_raw.get("prompt_tokens", 0)), "output_tokens": int(usage_raw.get("completion_tokens", 0))},
    )


def invoke_structured_provider(
    *, provider: str, model: str, prompt: str, schema: dict[str, Any], timeout: int,
    reasoning_effort: str | None = None,
) -> StructuredProviderResult:
    if provider in {"codex", "grok", "antigravity", "copilot", "claude_code"}:
        return _invoke_cli(provider, model, prompt, schema, timeout, reasoning_effort)
    if provider == "anthropic":
        return _invoke_anthropic(model, prompt, schema, timeout)
    if provider == "gemini":
        return _invoke_gemini(model, prompt, schema, timeout)
    if provider in {"moonshot", "zai"}:
        return _invoke_openai_compatible(provider, model, prompt, timeout, reasoning_effort)
    raise RuntimeError(f"No native structured adapter for {provider}")


def _write_wave(path: Path, pcm: bytes, *, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pcm.startswith(b"RIFF"):
        path.write_bytes(pcm)
        return
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm)


def _convert_to_wav(source: Path, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to normalize ElevenLabs audio")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(source), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(output)],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg could not normalize TTS audio: {result.stderr[-2000:]}")


def _generate_elevenlabs(text: str, model: str, voice_id: str, output: Path, timeout: int) -> TTSResult:
    load_env()
    api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("XI_API_KEY")
    if not api_key or not voice_id:
        raise RuntimeError("ElevenLabs requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps({
            "text": text, "model_id": model,
            "voice_settings": {
                "stability": float(os.getenv("ELEVENLABS_STABILITY", "0.5")),
                "similarity_boost": float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75")),
            },
        }).encode(),
        method="POST",
        headers={"xi-api-key": api_key, "accept": "application/json", "content-type": "application/json"},
    )
    response = ElevenLabsTTSResponse.model_validate(_request_json(request, provider="elevenlabs", timeout=timeout))
    output.parent.mkdir(parents=True, exist_ok=True)
    source = output.with_suffix(".elevenlabs.mp3")
    source.write_bytes(base64.b64decode(response.audio_base64))
    try:
        _convert_to_wav(source, output)
    finally:
        source.unlink(missing_ok=True)
    alignment_path = output.with_name("voice_alignment.json")
    alignment_path.write_text(response.model_dump_json(indent=2, exclude={"audio_base64"}), encoding="utf-8")
    return TTSResult(
        provider="elevenlabs", model=model, voice_id=voice_id, audio_path=str(output),
        alignment_path=str(alignment_path),
    )


def _generate_gemini_tts(text: str, model: str, voice_id: str, output: Path, timeout: int) -> TTSResult:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Gemini TTS requires: pip install -e '.[ai]'") from exc
    http_options = types.HttpOptions(timeout=max(GEMINI_MIN_TIMEOUT_SECONDS, timeout) * 1000)
    client = genai.Client(api_key=_api_key("gemini"), http_options=http_options)
    response = client.models.generate_content(
        model=model,
        contents=os.getenv("GEMINI_TTS_PROMPT_PREFIX", "Read this narration exactly as written, naturally and clearly:\n\n") + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)),
                language_code=os.getenv("GEMINI_TTS_LANGUAGE_CODE") or None,
            ),
            http_options=http_options,
        ),
    )
    pcm: bytes | None = None
    for candidate in getattr(response, "candidates", []) or []:
        for part in getattr(getattr(candidate, "content", None), "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline else None
            if data:
                pcm = data if isinstance(data, bytes) else base64.b64decode(data)
                break
    if not pcm:
        raise RuntimeError("Gemini TTS returned no audio data")
    _write_wave(output, pcm)
    return TTSResult(provider="gemini", model=model, voice_id=voice_id, audio_path=str(output))


def generate_tts(
    *, provider: str, model: str, text: str, output: Path, timeout: int, voice_id: str | None = None,
) -> TTSResult:
    load_env()
    if provider == "elevenlabs":
        return _generate_elevenlabs(
            text, model, voice_id or os.getenv("ELEVENLABS_VOICE_ID", ""), output, timeout,
        )
    if provider == "gemini":
        return _generate_gemini_tts(
            text, model, voice_id or os.getenv("GEMINI_TTS_VOICE", "Kore"), output, timeout,
        )
    raise RuntimeError(f"No native TTS adapter for {provider}")


def provider_credentials_available(provider: str) -> tuple[bool, str]:
    load_env()
    key_names = {
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "elevenlabs": ("ELEVENLABS_API_KEY", "XI_API_KEY"),
        "moonshot": ("MOONSHOT_API_KEY",),
        "zai": ("ZAI_API_KEY", "ZHIPU_API_KEY", "BIGMODEL_API_KEY"),
    }
    if provider in key_names:
        found = next((name for name in key_names[provider] if os.getenv(name)), None)
        return bool(found), found or " / ".join(key_names[provider])
    binary_names = {"codex": "codex", "grok": "grok", "antigravity": "agy", "copilot": "copilot", "claude_code": "claude"}
    if provider in binary_names:
        path = shutil.which(binary_names[provider])
        return bool(path), path or binary_names[provider]
    return False, "not configured"

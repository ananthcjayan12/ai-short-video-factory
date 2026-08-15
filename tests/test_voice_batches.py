from __future__ import annotations

import wave
from pathlib import Path

import pytest

from shorts_factory.integrations import TTSResult
from shorts_factory.models import Narration, NarrationParagraph, VoiceChunkManifest
from shorts_factory import voice_batches


def _narration() -> Narration:
    paragraphs = [
        NarrationParagraph(paragraph_id="P01", beat_id="B01", text="First paragraph has a complete thought.", claim_ids=[]),
        NarrationParagraph(paragraph_id="P02", beat_id="B02", text="Second paragraph keeps the narration clear.", claim_ids=[]),
    ]
    text = " ".join(paragraph.text for paragraph in paragraphs)
    return Narration(
        episode_id="voice-test", text=text, word_count=len(text.split()), target_seconds=30,
        hook=paragraphs[0].text, consultation_line="Book a consultation.", paragraphs=paragraphs,
    )


def _write_tone(path: Path, seconds: float = 0.25) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(24000 * seconds)
    sample = int(32768 * 0.1).to_bytes(2, "little", signed=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(sample * frames)


def test_batched_voice_generates_quality_checks_assembles_and_reuses(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_tts(*, provider, model, text, output, timeout, voice_id):
        calls.append((voice_id, text))
        _write_tone(output)
        return TTSResult(provider=provider, model=model, voice_id=voice_id, audio_path=str(output))

    monkeypatch.setattr(voice_batches, "generate_tts", fake_tts)
    output = tmp_path / "02_voice/voice_master.wav"
    manifest = voice_batches.generate_batched_voice(
        project=tmp_path, episode_id="voice-test", narration=_narration(), provider="gemini",
        model="gemini-3.1-flash-tts-preview", voice_id="Kore", output=output, timeout=30,
    )

    assert len(calls) == 2
    assert isinstance(manifest, VoiceChunkManifest)
    assert all(chunk.quality.passed for chunk in manifest.chunks)
    assert manifest.duration_seconds == pytest.approx(0.85, abs=0.001)
    assert output.exists()
    assert (tmp_path / "02_voice/audio_chunks/manifest.json").exists()

    calls.clear()
    reused = voice_batches.generate_batched_voice(
        project=tmp_path, episode_id="voice-test", narration=_narration(), provider="gemini",
        model="gemini-3.1-flash-tts-preview", voice_id="Kore", output=output, timeout=30,
    )
    assert calls == []
    assert all(chunk.reused for chunk in reused.chunks)

    voice_batches.generate_batched_voice(
        project=tmp_path, episode_id="voice-test", narration=_narration(), provider="gemini",
        model="gemini-3.1-flash-tts-preview", voice_id="Puck", output=output, timeout=30,
    )
    assert [voice_id for voice_id, _ in calls] == ["Puck", "Puck"]


def test_voice_quality_rejects_silence(tmp_path):
    silent = tmp_path / "silent.wav"
    with wave.open(str(silent), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x00\x00" * 6000)
    quality = voice_batches.inspect_voice_chunk(silent)
    assert quality.passed is False
    assert any("too quiet" in issue for issue in quality.issues)

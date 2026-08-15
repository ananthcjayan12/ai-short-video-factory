from __future__ import annotations

import hashlib
import math
import os
import re
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .integrations import generate_tts
from .io import atomic_write_text, load_model, write_json
from .models import Narration, VoiceChunkManifest, VoiceChunkQuality, VoiceChunkRecord


@dataclass(frozen=True)
class TTSChunkText:
    chunk_id: str
    paragraph_id: str
    text: str


def _normalized_words(text: str) -> str:
    return " ".join(text.split())


def _split_to_limit(text: str, max_chars: int) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if not sentences:
        return []
    result: list[str] = []
    current = ""
    for sentence in sentences:
        pieces = [sentence]
        if len(sentence) > max_chars:
            words = sentence.split()
            pieces = []
            piece = ""
            for word in words:
                candidate = f"{piece} {word}".strip()
                if piece and len(candidate) > max_chars:
                    pieces.append(piece)
                    piece = word
                else:
                    piece = candidate
            if piece:
                pieces.append(piece)
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > max_chars:
                result.append(current)
                current = piece
            else:
                current = candidate
    if current:
        result.append(current)
    return result


def narration_chunks(narration: Narration, *, max_chars: int | None = None) -> list[TTSChunkText]:
    """Deterministically divide narration into paragraph-sized, resumable TTS requests."""
    limit = max(200, min(4000, max_chars or int(os.getenv("SVF_TTS_CHUNK_MAX_CHARS", "900"))))
    paragraph_texts = [paragraph.text for paragraph in narration.paragraphs]
    if not paragraph_texts or _normalized_words(" ".join(paragraph_texts)) != _normalized_words(narration.text):
        paragraph_texts = [part.strip() for part in re.split(r"\n\s*\n", narration.text) if part.strip()]
    if not paragraph_texts:
        paragraph_texts = [narration.text.strip()]

    chunks: list[TTSChunkText] = []
    for paragraph_index, paragraph_text in enumerate(paragraph_texts, start=1):
        paragraph_id = f"P{paragraph_index:02d}"
        pieces = _split_to_limit(paragraph_text, limit)
        for piece_index, piece in enumerate(pieces, start=1):
            chunk_id = paragraph_id if len(pieces) == 1 else f"{paragraph_id}-{piece_index:02d}"
            chunks.append(TTSChunkText(chunk_id=chunk_id, paragraph_id=paragraph_id, text=piece))
    if not chunks:
        raise RuntimeError("Narration has no text to synthesize")
    return chunks


def inspect_voice_chunk(path: Path) -> VoiceChunkQuality:
    issues: list[str] = []
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_count = audio.getnframes()
            frames = audio.readframes(frame_count)
    except (OSError, wave.Error) as exc:
        return VoiceChunkQuality(
            passed=False, duration_seconds=0, rms_dbfs=-120, clipping_ratio=0,
            sample_rate=1, channels=1, sample_width=1, issues=[f"Unreadable WAV: {exc}"],
        )

    duration = frame_count / float(sample_rate) if sample_rate else 0
    if duration < 0.2:
        issues.append("Audio is shorter than 0.2 seconds")
    if sample_rate != 24000:
        issues.append(f"Expected 24000 Hz audio, received {sample_rate} Hz")
    if channels != 1:
        issues.append(f"Expected mono audio, received {channels} channels")
    if sample_width != 2:
        issues.append(f"Expected 16-bit PCM audio, received {sample_width * 8}-bit")

    samples = array("h")
    if sample_width == 2 and frames:
        samples.frombytes(frames)
        if os.sys.byteorder != "little":
            samples.byteswap()
    if samples:
        square_mean = sum(sample * sample for sample in samples) / len(samples)
        rms = math.sqrt(square_mean)
        rms_dbfs = 20 * math.log10(max(rms, 1) / 32768)
        clipping_ratio = sum(abs(sample) >= 32760 for sample in samples) / len(samples)
    else:
        rms_dbfs = -120.0
        clipping_ratio = 0.0
    minimum_rms = float(os.getenv("SVF_TTS_MIN_RMS_DBFS", "-50"))
    maximum_clipping = float(os.getenv("SVF_TTS_MAX_CLIPPING_RATIO", "0.01"))
    if rms_dbfs < minimum_rms:
        issues.append(f"Audio is too quiet ({rms_dbfs:.1f} dBFS)")
    if clipping_ratio > maximum_clipping:
        issues.append(f"Audio clipping ratio is too high ({clipping_ratio:.4f})")
    return VoiceChunkQuality(
        passed=not issues, duration_seconds=round(duration, 6), rms_dbfs=round(rms_dbfs, 3),
        clipping_ratio=round(clipping_ratio, 6), sample_rate=sample_rate,
        channels=channels, sample_width=sample_width, issues=issues,
    )


def _cache_key(*, provider: str, model: str, voice_id: str, text: str) -> str:
    settings = "|".join([
        provider, model, voice_id, _normalized_words(text),
        os.getenv("GEMINI_TTS_PROMPT_PREFIX", "Read this narration exactly as written, naturally and clearly:\n\n"),
        os.getenv("GEMINI_TTS_LANGUAGE_CODE", ""),
        os.getenv("ELEVENLABS_STABILITY", "0.5"),
        os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75"),
    ])
    return hashlib.sha256(settings.encode("utf-8")).hexdigest()


def _assemble_master(records: list[VoiceChunkRecord], project: Path, output: Path) -> tuple[int, int, int, float]:
    first_path = project / records[0].audio_path
    with wave.open(str(first_path), "rb") as first:
        channels, sample_width, sample_rate = first.getnchannels(), first.getsampwidth(), first.getframerate()
    pending = output.with_name(output.stem + ".pending.wav")
    pending.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(pending), "wb") as master:
            master.setnchannels(channels)
            master.setsampwidth(sample_width)
            master.setframerate(sample_rate)
            for record in records:
                with wave.open(str(project / record.audio_path), "rb") as chunk:
                    actual_format = (chunk.getnchannels(), chunk.getsampwidth(), chunk.getframerate())
                    if actual_format != (channels, sample_width, sample_rate):
                        raise RuntimeError(f"Voice chunk {record.chunk_id} has an inconsistent WAV format")
                    master.writeframes(chunk.readframes(chunk.getnframes()))
                pause_frames = round(record.trailing_pause_seconds * sample_rate)
                if pause_frames:
                    master.writeframes(b"\x00" * pause_frames * channels * sample_width)
        pending.replace(output)
    finally:
        pending.unlink(missing_ok=True)
    with wave.open(str(output), "rb") as master:
        duration = master.getnframes() / float(master.getframerate())
    return sample_rate, channels, sample_width, duration


def generate_batched_voice(
    *, project: Path, episode_id: str, narration: Narration, provider: str, model: str,
    voice_id: str, output: Path, timeout: int,
    progress: Callable[[int, int, str], None] | None = None,
) -> VoiceChunkManifest:
    chunks = narration_chunks(narration)
    pause_seconds = max(0.0, min(2.0, float(os.getenv("SVF_TTS_CHUNK_PAUSE_SECONDS", "0.35"))))
    chunks_root = project / "02_voice" / "audio_chunks"
    draft_records: list[tuple[TTSChunkText, Path, str, bool, VoiceChunkQuality, str | None]] = []

    for index, chunk in enumerate(chunks, start=1):
        chunk_dir = chunks_root / chunk.chunk_id
        audio_path = chunk_dir / "audio.wav"
        quality_path = chunk_dir / "quality.json"
        cache_path = chunk_dir / "cache_key.txt"
        text_path = chunk_dir / "narration.txt"
        cache_key = _cache_key(provider=provider, model=model, voice_id=voice_id, text=chunk.text)
        reused = False
        quality: VoiceChunkQuality | None = None
        if audio_path.exists() and quality_path.exists() and cache_path.exists() and text_path.exists():
            if cache_path.read_text(encoding="utf-8").strip() == cache_key:
                cached_quality = load_model(quality_path, VoiceChunkQuality)
                current_quality = inspect_voice_chunk(audio_path)
                reused = cached_quality.passed and current_quality.passed
                if reused:
                    quality = current_quality
                    write_json(quality_path, quality)
        alignment_path = chunk_dir / "voice_alignment.json"
        if not reused:
            chunk_dir.mkdir(parents=True, exist_ok=True)
            pending = chunk_dir / "audio.pending.wav"
            pending.unlink(missing_ok=True)
            alignment_path.unlink(missing_ok=True)
            result = generate_tts(
                provider=provider, model=model, text=chunk.text, output=pending,
                timeout=timeout, voice_id=voice_id,
            )
            quality = inspect_voice_chunk(pending)
            write_json(quality_path, quality)
            if not quality.passed:
                pending.unlink(missing_ok=True)
                raise RuntimeError(f"TTS chunk {chunk.chunk_id} failed quality checks: {'; '.join(quality.issues)}")
            pending.replace(audio_path)
            atomic_write_text(text_path, chunk.text + "\n")
            atomic_write_text(cache_path, cache_key + "\n")
            alignment_path = Path(result.alignment_path) if result.alignment_path else alignment_path
        assert quality is not None
        alignment_relative = (
            alignment_path.relative_to(project).as_posix() if alignment_path.exists() else None
        )
        draft_records.append((chunk, audio_path, cache_key, reused, quality, alignment_relative))
        if progress:
            progress(index, len(chunks), "reused" if reused else "generated")

    cursor = 0.0
    records: list[VoiceChunkRecord] = []
    for index, (chunk, audio_path, cache_key, reused, quality, alignment_relative) in enumerate(draft_records):
        trailing_pause = pause_seconds if index < len(draft_records) - 1 else 0.0
        end = cursor + quality.duration_seconds + trailing_pause
        records.append(VoiceChunkRecord(
            chunk_id=chunk.chunk_id, paragraph_id=chunk.paragraph_id, text=chunk.text,
            audio_path=audio_path.relative_to(project).as_posix(), alignment_path=alignment_relative,
            cache_key=cache_key, reused=reused, start_seconds=round(cursor, 6),
            speech_duration_seconds=quality.duration_seconds,
            trailing_pause_seconds=round(trailing_pause, 6), end_seconds=round(end, 6), quality=quality,
        ))
        cursor = end

    sample_rate, channels, sample_width, master_duration = _assemble_master(records, project, output)
    # Frame rounding can differ from decimal pause arithmetic by a few microseconds;
    # the master WAV is authoritative, so normalize the final timeline endpoint.
    records[-1].end_seconds = round(master_duration, 6)
    manifest = VoiceChunkManifest(
        episode_id=episode_id, provider=provider, model=model, voice_id=voice_id,
        pause_seconds=pause_seconds, sample_rate=sample_rate, channels=channels,
        sample_width=sample_width, duration_seconds=round(master_duration, 6), chunks=records,
    )
    write_json(chunks_root / "manifest.json", manifest)
    return manifest

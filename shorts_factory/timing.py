from __future__ import annotations

import difflib
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from .models import (
    AudioTiming,
    Narration,
    ParagraphTiming,
    WordTimestamp,
    WordTimestampBundle,
)


DEFAULT_WHISPER_MODEL = "base.en"
DEFAULT_WHISPER_LANGUAGE = "en"
MIN_PARAGRAPH_MATCH = 0.42
_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


def word_tokens(text: str) -> list[str]:
    return _WORD_RE.findall(" ".join(text.split()).lower().replace("\u2019", "'"))


def audio_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_whisper_words(transcription: dict[str, Any]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for segment in transcription.get("segments", []) or []:
        for item in segment.get("words", []) or []:
            start = item.get("start")
            end = item.get("end")
            if start is None or end is None:
                continue
            for token in word_tokens(str(item.get("word") or "")):
                words.append({"word": token, "start": float(start), "end": float(end)})
    return words


def _best_transcript_window(
    target_words: list[str],
    transcript_words: list[dict[str, Any]],
    cursor: int,
    *,
    is_last: bool,
) -> tuple[int, int, float] | None:
    if not target_words or cursor >= len(transcript_words):
        return None
    if is_last:
        candidate = [item["word"] for item in transcript_words[cursor:]]
        return cursor, len(transcript_words) - 1, difflib.SequenceMatcher(None, target_words, candidate).ratio()

    target_len = len(target_words)
    min_len = max(1, int(target_len * 0.6))
    max_len = max(min_len, int(target_len * 1.55) + 4)
    max_start = min(len(transcript_words), cursor + max(12, int(target_len * 0.35) + 6))
    best: tuple[int, int, float] | None = None
    for start in range(cursor, max_start):
        max_end = min(len(transcript_words), start + max_len)
        for end_exclusive in range(start + min_len, max_end + 1):
            candidate = [item["word"] for item in transcript_words[start:end_exclusive]]
            score = difflib.SequenceMatcher(None, target_words, candidate).ratio()
            if best is None or score > best[2]:
                best = (start, end_exclusive - 1, score)
    return best


def align_words_to_narration(
    *,
    narration: Narration,
    transcript_words: list[dict[str, Any]],
    audio_duration: float,
    audio_hash: str,
    whisper_model: str,
) -> tuple[WordTimestampBundle, AudioTiming]:
    """Map Whisper's actual word clock onto narration paragraphs.

    This is deliberately deterministic. Whisper resolves the audio ambiguity;
    Python performs the exact paragraph/window mapping and contract validation.
    """
    if not transcript_words:
        raise RuntimeError(
            "Whisper produced no word timestamps. Use a spoken voice track; a silent timing track cannot be aligned."
        )
    paragraphs = narration.paragraphs
    if not paragraphs:
        raise RuntimeError("Narration has no paragraph-to-beat mapping. Regenerate narration before alignment.")

    min_score = float(os.getenv("SVF_WHISPER_MIN_PARAGRAPH_MATCH", str(MIN_PARAGRAPH_MATCH)))
    cursor = 0
    ranges: list[dict[str, Any]] = []
    for index, paragraph in enumerate(paragraphs):
        target = word_tokens(paragraph.text)
        if not target:
            raise RuntimeError(f"{paragraph.paragraph_id} contains no spoken words to align")
        match = _best_transcript_window(
            target, transcript_words, cursor, is_last=index == len(paragraphs) - 1
        )
        if match is None:
            raise RuntimeError(f"Whisper could not align {paragraph.paragraph_id} to the voice transcript")
        start_index, end_index, score = match
        if score < min_score:
            raise RuntimeError(
                f"Whisper alignment for {paragraph.paragraph_id} was too weak "
                f"({score:.2f} < {min_score:.2f}). Check that the voice reads the final narration."
            )
        ranges.append({
            "paragraph_id": paragraph.paragraph_id,
            "beat_id": paragraph.beat_id,
            "start_index": start_index,
            "end_index": end_index,
            "raw_start": max(0.0, float(transcript_words[start_index]["start"])),
            "score": score,
        })
        cursor = end_index + 1

    tagged_words: list[WordTimestamp] = []
    timed_paragraphs: list[ParagraphTiming] = []
    cursor_time = 0.0
    for index, item in enumerate(ranges):
        output_start_index = len(tagged_words)
        for raw_word in transcript_words[item["start_index"] : item["end_index"] + 1]:
            start = round(max(0.0, float(raw_word["start"])), 3)
            end = round(min(audio_duration, float(raw_word["end"])), 3)
            if end <= start:
                continue
            tagged_words.append(WordTimestamp(
                index=len(tagged_words),
                paragraph_id=item["paragraph_id"],
                beat_id=item["beat_id"],
                word=str(raw_word["word"]),
                start=start,
                end=end,
            ))
        if len(tagged_words) == output_start_index:
            raise RuntimeError(f"Whisper produced no usable words for {item['paragraph_id']}")

        if index == len(ranges) - 1:
            paragraph_end = audio_duration
        else:
            paragraph_end = max(cursor_time + 0.05, min(audio_duration, ranges[index + 1]["raw_start"]))
        timed_paragraphs.append(ParagraphTiming(
            paragraph_id=item["paragraph_id"],
            beat_id=item["beat_id"],
            start=round(cursor_time, 3),
            end=round(paragraph_end, 3),
            word_start_index=output_start_index,
            word_end_index=len(tagged_words) - 1,
            match_score=round(item["score"], 3),
        ))
        cursor_time = paragraph_end

    bundle = WordTimestampBundle(
        episode_id=narration.episode_id,
        audio_duration_seconds=round(audio_duration, 3),
        whisper_model=whisper_model,
        audio_sha256=audio_hash,
        words=tagged_words,
    )
    timing = AudioTiming(
        episode_id=narration.episode_id,
        audio_duration_seconds=round(audio_duration, 3),
        whisper_model=whisper_model,
        audio_sha256=audio_hash,
        word_timestamps_path="02_voice/audio_word_timestamps.json",
        paragraphs=timed_paragraphs,
    )
    return bundle, timing


def transcribe_with_whisper(audio_path: Path) -> tuple[list[dict[str, Any]], str]:
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError(f"Cannot run Whisper because the voice file is missing or empty: {audio_path}")
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI Whisper is required for alignment. Install openai-whisper in the project environment."
        ) from exc

    model_name = os.getenv("SVF_WHISPER_MODEL", DEFAULT_WHISPER_MODEL)
    language = os.getenv("SVF_WHISPER_LANGUAGE", DEFAULT_WHISPER_LANGUAGE).strip() or None
    download_root = os.getenv("SVF_WHISPER_DOWNLOAD_ROOT") or None
    try:
        model = whisper.load_model(model_name, download_root=download_root)
        options: dict[str, Any] = {"word_timestamps": True, "fp16": False, "verbose": False}
        if language:
            options["language"] = language
        transcription = model.transcribe(str(audio_path), **options)
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed with model {model_name!r}: {exc}") from exc
    return extract_whisper_words(transcription), model_name

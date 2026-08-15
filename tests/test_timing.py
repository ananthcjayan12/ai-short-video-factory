from __future__ import annotations

from shorts_factory.models import Narration, NarrationParagraph
from shorts_factory.timing import align_words_to_narration


def test_whisper_words_become_validated_paragraph_and_word_contracts():
    narration = Narration(
        episode_id="timing-01",
        text="The invoices were scattered. We put them in one queue.",
        word_count=10,
        target_seconds=5,
        hook="The invoices were scattered.",
        consultation_line="We put them in one queue.",
        paragraphs=[
            NarrationParagraph(paragraph_id="P01", beat_id="B01", text="The invoices were scattered."),
            NarrationParagraph(paragraph_id="P02", beat_id="B02", text="We put them in one queue."),
        ],
    )
    raw_words = [
        {"word": word, "start": index * 0.4, "end": index * 0.4 + 0.3}
        for index, word in enumerate(
            ["the", "invoices", "were", "scattered", "we", "put", "them", "in", "one", "queue"]
        )
    ]

    words, timing = align_words_to_narration(
        narration=narration,
        transcript_words=raw_words,
        audio_duration=4.0,
        audio_hash="a" * 64,
        whisper_model="base.en",
    )

    assert [paragraph.beat_id for paragraph in timing.paragraphs] == ["B01", "B02"]
    assert timing.paragraphs[0].end == raw_words[4]["start"]
    assert timing.paragraphs[-1].end == 4.0
    assert words.words[0].paragraph_id == "P01"
    assert words.words[-1].paragraph_id == "P02"
    assert words.source == "openai_whisper_word_timestamps"

from __future__ import annotations

import re

from .models import EpisodeBrief, Narration, NarrationQualityReport, StoryPlan


WORD_PATTERN = re.compile(r"\b[\w'’-]+\b", re.UNICODE)


def _words(value: str) -> list[str]:
    return WORD_PATTERN.findall(value.casefold())


def _normalized(value: str) -> str:
    return " ".join(_words(value))


def assess_narration(brief: EpisodeBrief, story: StoryPlan, narration: Narration) -> NarrationQualityReport:
    """Check measurable symptoms of explainer copy masquerading as a client story."""

    total_words = len(_words(narration.text))
    purposes = {beat.beat_id: beat.purpose for beat in story.beats}
    pain_paragraphs = [
        paragraph for paragraph in narration.paragraphs
        if purposes.get(paragraph.beat_id) in {"hook", "problem"}
    ]
    pain_words = sum(len(_words(paragraph.text)) for paragraph in pain_paragraphs)
    pain_ratio = pain_words / total_words if total_words else 0.0
    cta_words = sum(
        len(_words(paragraph.text)) for paragraph in narration.paragraphs
        if purposes.get(paragraph.beat_id) == "cta"
    )

    opening = " ".join(_words(narration.text)[:45])
    role_terms = {token for token in _words(brief.role) if len(token) > 2}
    protagonist_terms = role_terms | {"client", "clients", "owner", "owners", "team", "staff", "business"}
    opening_has_protagonist = any(re.search(rf"\b{re.escape(term)}\b", opening) for term in protagonist_terms)

    story_body = " ".join(
        paragraph.text for paragraph in narration.paragraphs
        if purposes.get(paragraph.beat_id) in {"insight", "solution", "proof"}
    )
    solution_uses_client_story_voice = brief.case_nature != "real" or bool(
        re.search(r"\bwe\b", story_body.casefold())
    )

    blocking: list[str] = []
    warnings: list[str] = []
    if narration.paragraphs:
        joined = " ".join(paragraph.text.strip() for paragraph in narration.paragraphs).strip()
        if _normalized(joined) != _normalized(narration.text):
            blocking.append("top-level narration does not match its ordered spoken paragraphs")
    if not opening_has_protagonist:
        blocking.append(
            "the opening 45 words do not establish the client, viewer role, team, or business as the protagonist"
        )
    if pain_ratio < 0.24:
        blocking.append(
            f"only {pain_ratio:.0%} of the narration is allocated to the hook/problem; use at least 24%"
        )
    elif pain_ratio < 0.30:
        warnings.append(
            f"only {pain_ratio:.0%} of the narration is allocated to the hook/problem; 30-40% usually tells a stronger story"
        )
    if not solution_uses_client_story_voice:
        blocking.append(
            "the real-case solution/proof section never says what we changed, so it reads like a generic product explanation"
        )
    if cta_words > 22:
        blocking.append(f"the CTA uses {cta_words} words; keep the close to one restrained sentence of at most 22 words")
    elif cta_words > 18:
        warnings.append(f"the CTA uses {cta_words} words; 8-18 words is preferable")

    sentence_words = [len(_words(item)) for item in re.split(r"(?<=[.!?])\s+", narration.text) if _words(item)]
    if sentence_words and sum(sentence_words) / len(sentence_words) < 8:
        warnings.append("the average sentence is very short, which can make the narration sound like a feature checklist")

    return NarrationQualityReport(
        episode_id=brief.episode_id,
        passed=not blocking,
        total_words=total_words,
        pain_words=pain_words,
        pain_word_ratio=round(pain_ratio, 4),
        cta_words=cta_words,
        opening_has_protagonist=opening_has_protagonist,
        solution_uses_client_story_voice=solution_uses_client_story_voice,
        blocking_issues=blocking,
        warnings=warnings,
    )

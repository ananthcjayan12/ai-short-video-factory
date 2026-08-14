from __future__ import annotations

from .models import EpisodeBrief, Narration, VoiceMetadata


def narration_prompt(brief: EpisodeBrief) -> str:
    return f"""You are the story writer for a high-retention YouTube Shorts channel about real small-business AI integrations.

CASE
Title: {brief.title}
Industry: {brief.industry}
Role: {brief.role}
Pain: {brief.pain_point}
Backend facts:
- """ + "\n- ".join(brief.backend_summary) + """

Viewer DIY:
- """ + "\n- ".join(brief.viewer_diy) + f"""

Write one natural 50–60 second narration. It should feel like a case study: the client had a weird operational problem, we noticed what was actually difficult, then explain the AI + code solution in very simple language. Vary sentence length. Do not sound like an AI tutorial or SaaS ad. The AI must do a genuinely intelligent part. Explain what deterministic code does separately. Mention a DIY path briefly, then end with a soft signal that a custom integration can connect the real systems.

Do not fabricate numerical ROI or claim facts that are not in the case. If this is a hypothetical/example case, do not imply a real paid engagement in factual metadata."""


def director_prompt(brief: EpisodeBrief, narration: Narration, voice: VoiceMetadata | None) -> str:
    duration = voice.duration_seconds if voice else narration.target_seconds
    return f"""You are an elite short-form video Director. Convert the approved narration into a precise visual plan.

VIDEO
1080x1920 vertical, {duration:.2f}s master duration.
Narration:
{narration.text}

AVAILABLE SCENE TYPES
- talking_head: human credibility, hook, insight, CTA
- screen_recording: real prototype execution recorded by Playwright
- motion_graphic: HyperFrames HTML/CSS/GSAP explainer
- diagram: deterministic system/backend explanation
- ui_mockup: synthetic client workflow/UI
- broll: only when it adds information
- cta: presenter close

RULES
1. Narration/voice is the master clock; do not change its wording.
2. Opening hook and final CTA should be presenter-led unless there is a strong reason otherwise.
3. Never leave the same visual idea unchanged for too long.
4. Do not visualize words literally when a causal diagram or before/after is clearer.
5. Use screen recording only where a real prototype can demonstrate the claim.
6. Explain backend in plain English visually: AI handles ambiguity; code handles exact actions.
7. Max ~7 meaningful visual moments and ~5 generated assets. Prefer reusable deterministic graphics.
8. Avoid >16 seconds with no talking-head beat.
9. Each scene must identify the renderer: manual_talking_head, infinite_talk, playwright, hyperframes, or static.
10. The plan must be feasible with synthetic data.

Return a frame-accurate scene plan with start/end seconds, purpose, narration excerpt, visual brief, renderer, on-screen text and any demo job id."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .integrations import invoke_structured_provider
from .io import atomic_write_text, read_json, write_json
from .models import (
    DirectorBudgets, DirectorPlan, Narration, NarrationParagraph, PromptInvocation,
    Scene, StoryBeat, StoryPlan, StorySpine,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _save_invocation(request_dir: Path, invocation: PromptInvocation) -> None:
    write_json(request_dir / f"{invocation.stage}_invocation.json", invocation)


class AgentPending(RuntimeError):
    pass


class StructuredAgent(ABC):
    @abstractmethod
    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        raise NotImplementedError


class ManualAgent(StructuredAgent):
    def __init__(self, consume_response: bool = False) -> None:
        self.consume_response = consume_response

    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        request_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = request_dir / f"{stage}_prompt.md"
        schema_path = request_dir / f"{stage}_schema.json"
        response_path = request_dir / f"{stage}_response.json"
        atomic_write_text(prompt_path, prompt)
        write_json(schema_path, output_model.model_json_schema())
        if self.consume_response and response_path.exists():
            result = output_model.model_validate(read_json(response_path))
            _save_invocation(request_dir, PromptInvocation(
                task=stage, stage=stage, provider="manual", model="manual", status="succeeded",
                prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(response_path),
                started_at=_now(), finished_at=_now(), attempts=1,
            ))
            return result
        _save_invocation(request_dir, PromptInvocation(
            task=stage, stage=stage, provider="manual", model="manual", status="manual",
            prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(response_path),
            started_at=_now(), attempts=0,
        ))
        raise AgentPending(f"Manual response required: {prompt_path} -> {response_path}")


class CommandAgent(StructuredAgent):
    def __init__(self, *, command_template: str, model: str, timeout: int = 900, retries: int = 1,
                 fallback_template: str = "", fallback_model: str = "", provider: str = "command",
                 fallback_provider: str = "") -> None:
        if not command_template.strip():
            raise ValueError("command template is required")
        self.command_template = command_template
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.fallback_template = fallback_template
        self.fallback_model = fallback_model
        self.provider = provider
        self.fallback_provider = fallback_provider

    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        request_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = request_dir / f"{stage}_prompt.md"
        schema_path = request_dir / f"{stage}_schema.json"
        output_path = request_dir / f"{stage}_response.json"
        schema = output_model.model_json_schema()
        routed = (
            prompt.rstrip() + "\n\n# OUTPUT CONTRACT\n"
            "Return ONLY JSON that validates against this JSON Schema:\n```json\n"
            + json.dumps(schema, indent=2) + "\n```\n"
        )
        atomic_write_text(prompt_path, routed)
        write_json(schema_path, schema)
        started_at = _now()
        started = time.monotonic()
        attempts = [(self.command_template, self.model, self.provider, f"primary-{i+1}") for i in range(self.retries + 1)]
        if self.fallback_template:
            attempts.append((self.fallback_template, self.fallback_model or self.model, self.fallback_provider or "fallback", "fallback"))
        failures: list[str] = []
        for attempt_number, (template, model, provider, label) in enumerate(attempts, 1):
            output_path.unlink(missing_ok=True)
            cmd = template.format(
                prompt=shlex.quote(str(prompt_path)), output=shlex.quote(str(output_path)),
                model=shlex.quote(model), stage=shlex.quote(stage), timeout=shlex.quote(str(self.timeout)),
            )
            try:
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                failures.append(f"{label}: timeout")
                continue
            (request_dir / f"{stage}-{label}.log").write_text(
                (result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8"
            )
            if result.returncode != 0:
                failures.append(f"{label}: exit {result.returncode}")
                continue
            if not output_path.exists() and result.stdout.strip():
                atomic_write_text(output_path, result.stdout.strip())
            try:
                validated = output_model.model_validate(read_json(output_path))
                output_size = len(output_path.read_text(encoding="utf-8"))
                _save_invocation(request_dir, PromptInvocation(
                    task=stage, stage=stage, provider=provider, model=model, status="succeeded",
                    prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(output_path),
                    started_at=started_at, finished_at=_now(), attempts=attempt_number,
                    estimated_input_tokens=max(1, len(routed) // 4),
                    output_tokens=max(1, output_size // 4),
                ))
                return validated
            except Exception as exc:
                failures.append(f"{label}: invalid JSON: {exc}")
        message = "All structured agent attempts failed: " + " | ".join(failures)
        _save_invocation(request_dir, PromptInvocation(
            task=stage, stage=stage, provider=self.provider, model=self.model, status="failed",
            prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(output_path),
            started_at=started_at, finished_at=_now(), attempts=len(attempts),
            estimated_input_tokens=max(1, len(routed) // 4), error=f"{message} ({time.monotonic() - started:.1f}s)",
        ))
        raise RuntimeError(message)


class ProviderAgent(StructuredAgent):
    """Run a registered API/subscription CLI and validate its result locally."""

    def __init__(self, *, provider: str, model: str, timeout: int = 900, retries: int = 1,
                 reasoning_effort: str | None = None, fallback_provider: str = "",
                 fallback_model: str = "", fallback_reasoning_effort: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model
        self.fallback_reasoning_effort = fallback_reasoning_effort

    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        request_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = request_dir / f"{stage}_prompt.md"
        schema_path = request_dir / f"{stage}_schema.json"
        output_path = request_dir / f"{stage}_response.json"
        schema = output_model.model_json_schema()
        atomic_write_text(prompt_path, prompt)
        write_json(schema_path, schema)
        started_at = _now()
        started = time.monotonic()
        attempts = [
            (self.provider, self.model, self.reasoning_effort, f"primary-{index + 1}")
            for index in range(self.retries + 1)
        ]
        if self.fallback_provider:
            attempts.append((
                self.fallback_provider, self.fallback_model or self.model,
                self.fallback_reasoning_effort, "fallback",
            ))
        failures: list[str] = []
        for attempt_number, (provider, model, reasoning, label) in enumerate(attempts, 1):
            try:
                response = invoke_structured_provider(
                    provider=provider, model=model, prompt=prompt, schema=schema,
                    timeout=self.timeout, reasoning_effort=reasoning,
                )
                # Retain the provider result before local validation so a
                # repairable contract issue never destroys paid/generated work.
                write_json(output_path, response.payload)
                validated = output_model.model_validate(response.payload)
                write_json(output_path, validated)
                _save_invocation(request_dir, PromptInvocation(
                    task=stage, stage=stage, provider=response.provider, model=response.model,
                    status="succeeded", prompt_path=str(prompt_path), schema_path=str(schema_path),
                    response_path=str(output_path), started_at=started_at, finished_at=_now(),
                    attempts=attempt_number, estimated_input_tokens=response.usage.get("input_tokens") or max(1, len(prompt) // 4),
                    output_tokens=response.usage.get("output_tokens") or max(1, len(validated.model_dump_json()) // 4),
                ))
                return validated
            except Exception as exc:
                failures.append(f"{label} ({provider}/{model}): {exc}")
                atomic_write_text(request_dir / f"{stage}-{label}.log", str(exc) + "\n")
        message = "All structured provider attempts failed: " + " | ".join(failures)
        _save_invocation(request_dir, PromptInvocation(
            task=stage, stage=stage, provider=self.provider, model=self.model, status="failed",
            prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(output_path),
            started_at=started_at, finished_at=_now(), attempts=len(attempts),
            estimated_input_tokens=max(1, len(prompt) // 4),
            error=f"{message} ({time.monotonic() - started:.1f}s)",
        ))
        raise RuntimeError(message)


class MockAgent(StructuredAgent):
    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context

    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        episode_id = self.context["episode_id"]
        request_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = request_dir / f"{stage}_prompt.md"
        schema_path = request_dir / f"{stage}_schema.json"
        response_path = request_dir / f"{stage}_response.json"
        atomic_write_text(prompt_path, prompt)
        write_json(schema_path, output_model.model_json_schema())
        result: BaseModel
        if output_model is StoryPlan:
            brief = self.context.get("brief")
            backend_claim = "backend-01" if getattr(brief, "backend_summary", []) else "pain-01"
            diy_claim = "diy-01" if getattr(brief, "viewer_diy", []) else backend_claim
            result = StoryPlan(
                episode_id=episode_id,
                target_seconds=float(getattr(brief, "target_seconds", 58)),
                case_nature=getattr(brief, "case_nature", "synthetic_demo"),
                story_spine=StorySpine(
                    protagonist=f"a {getattr(brief, 'role', 'business operator').lower()}",
                    recurring_moment="the recurring manual reconciliation",
                    operational_pain=getattr(brief, "pain_point", "the workflow repeatedly needs manual recovery"),
                    stakes="the operator spends attention resolving ambiguous records",
                    turning_point="the difficult step is contextual interpretation, not the deterministic transformation",
                    changed_workday="the operator reviews exceptions instead of every item",
                    source_gaps=["No quantified outcome is supplied"],
                ),
                beats=[
                    StoryBeat(beat_id="B01", purpose="hook", summary="Open on the operational contradiction", claim_ids=["pain-01"], emotional_register="curiosity"),
                    StoryBeat(beat_id="B02", purpose="problem", summary="Show why the obvious workflow fails", claim_ids=["pain-01"], emotional_register="tension"),
                    StoryBeat(beat_id="B03", purpose="insight", summary="Identify the ambiguous decision", claim_ids=[backend_claim], emotional_register="clarity", ai_responsibility="Interpret ambiguous business context"),
                    StoryBeat(beat_id="B04", purpose="solution", summary="Separate AI judgment from exact code", claim_ids=[backend_claim], emotional_register="clarity", ai_responsibility="Rank contextual matches", deterministic_responsibility="Accept strong matches and route exceptions"),
                    StoryBeat(beat_id="B05", purpose="proof", summary="Demonstrate the happy path and exception path", claim_ids=[backend_claim], emotional_register="proof", proof_opportunity="Run the synthetic prototype"),
                    StoryBeat(beat_id="B06", purpose="diy", summary="Give the viewer a small build path", claim_ids=[diy_claim], emotional_register="agency"),
                    StoryBeat(beat_id="B07", purpose="cta", summary="Close on connecting the real systems", claim_ids=["pain-01"], emotional_register="trust"),
                ],
            )
        if output_model is Narration:
            text = self.context.get("mock_narration") or (
                "One of our contractor clients had a strange problem. The receipts were correct, but the jobs were wrong. "
                "Their crew bought materials from several suppliers, and later the owner had to remember which purchase belonged to which project. "
                "We built a matcher that first lets vision AI read the receipt, then adds business context: who bought it, where that person worked that day, the supplier, the items and recent job history. "
                "Normal code accepts only strong matches. If the context is ambiguous, the system asks one short question instead of guessing. "
                "That means the owner reviews exceptions, not every receipt. A basic version can be built with a message inbox, n8n, a vision model and a jobs sheet. "
                "For a real business, I would connect the schedule, accounting and project system directly, and keep humans only on the uncertain cases."
            )
            story = self.context.get("story")
            beats = getattr(story, "beats", [])
            paragraphs = []
            if beats:
                chunks = [part.strip() for part in text.split(". ")]
                for index, beat in enumerate(beats):
                    start = round(index * len(chunks) / len(beats))
                    end = round((index + 1) * len(chunks) / len(beats))
                    paragraph_text = ". ".join(chunks[start:end]).strip()
                    if paragraph_text and not paragraph_text.endswith("."):
                        paragraph_text += "."
                    paragraphs.append(NarrationParagraph(
                        paragraph_id=f"P{index + 1:02d}", beat_id=beat.beat_id,
                        text=paragraph_text, claim_ids=beat.claim_ids,
                    ))
            result = Narration(
                episode_id=episode_id, text=text, word_count=len(text.split()),
                target_seconds=float(getattr(self.context.get("brief"), "target_seconds", 58)),
                hook="The receipts were correct, but the jobs were wrong.",
                consultation_line="Connect the real business systems and keep humans only on uncertain cases.",
                paragraphs=paragraphs,
            )
        elif output_model is DirectorPlan:
            scenes = [
                Scene(scene_id="S01", start=0, end=4, type="talking_head", renderer="manual_talking_head",
                      narration_excerpt="One of our contractor clients...", purpose="Hook with face and credibility",
                      visual_brief="Presenter direct-to-camera. Large subtitle: THE RECEIPT WAS RIGHT. THE JOB WAS WRONG."),
                Scene(scene_id="S02", start=4, end=9, type="motion_graphic", renderer="hyperframes",
                      narration_excerpt="Their crew bought materials...", purpose="Make the routing confusion instantly visual",
                      visual_brief="Receipt card branches toward Riverside Villa, Downtown Office, Harbor Shop; question mark pulses."),
                Scene(scene_id="S03", start=9, end=17, type="screen_recording", renderer="playwright",
                      narration_excerpt="vision AI read the receipt", purpose="Show a real working prototype, not a slideshow",
                      visual_brief="Upload/receive receipt, extract supplier/date/items/amount.", demo_job_id="demo-extract"),
                Scene(scene_id="S04", start=17, end=22, type="talking_head", renderer="manual_talking_head",
                      narration_excerpt="the hard part was context", purpose="Human insight beat",
                      visual_brief="Presenter explains reading the receipt is easy; deciding the job is the intelligent step."),
                Scene(scene_id="S05", start=22, end=30, type="diagram", renderer="hyperframes",
                      narration_excerpt="who bought it, where that person worked...", purpose="Explain backend simply",
                      visual_brief="Worker + schedule + supplier + purchased items + history converge into one confidence meter."),
                Scene(scene_id="S06", start=30, end=38, type="screen_recording", renderer="playwright",
                      narration_excerpt="Normal code accepts only strong matches", purpose="Show confident happy path",
                      visual_brief="Click Find Job. Riverside Villa appears with 94% confidence and three evidence chips.", demo_job_id="demo-match"),
                Scene(scene_id="S07", start=38, end=43, type="talking_head", renderer="manual_talking_head",
                      narration_excerpt="instead of guessing", purpose="Trust/safety insight",
                      visual_brief="Presenter: Good AI should know when it does not know."),
                Scene(scene_id="S08", start=43, end=49, type="screen_recording", renderer="playwright",
                      narration_excerpt="asks one short question", purpose="Show exception queue",
                      visual_brief="Run ambiguous receipt. Screen shows REVIEW · 61% and asks Villa or Downtown Office?", demo_job_id="demo-review"),
                Scene(scene_id="S09", start=49, end=54, type="motion_graphic", renderer="hyperframes",
                      narration_excerpt="basic version", purpose="Make DIY route feel achievable",
                      visual_brief="Simple stack animation: WhatsApp/Telegram → n8n → Vision AI → Jobs Sheet."),
                Scene(scene_id="S10", start=54, end=58, type="cta", renderer="manual_talking_head",
                      narration_excerpt="For a real business...", purpose="Soft consultation close",
                      visual_brief="Presenter. Small CTA: Custom AI workflow integration · link in bio."),
            ]
            result = DirectorPlan(
                episode_id=episode_id, duration_seconds=58,
                visual_thesis="AI handles ambiguous receipt understanding; deterministic code handles confident routing; the owner sees only exceptions.",
                scenes=scenes,
                budgets=DirectorBudgets(max_visual_moments=7, max_generated_assets=5, max_scene_seconds=8, max_consecutive_non_talking_head_seconds=16),
            )
        elif output_model is not StoryPlan and output_model is not Narration:
            raise RuntimeError(f"MockAgent has no fixture for {output_model.__name__}")
        write_json(response_path, result)
        _save_invocation(request_dir, PromptInvocation(
            task=stage, stage=stage, provider="mock", model="deterministic", status="mock",
            prompt_path=str(prompt_path), schema_path=str(schema_path), response_path=str(response_path),
            started_at=_now(), finished_at=_now(), attempts=1,
            estimated_input_tokens=max(1, len(prompt) // 4),
        ))
        return result

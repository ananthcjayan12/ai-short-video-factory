from __future__ import annotations

import json
import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .io import atomic_write_text, read_json, write_json
from .models import DirectorBudgets, DirectorPlan, Narration, Scene


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
            return output_model.model_validate(read_json(response_path))
        raise AgentPending(f"Manual response required: {prompt_path} -> {response_path}")


class CommandAgent(StructuredAgent):
    def __init__(self, *, command_template: str, model: str, timeout: int = 900, retries: int = 1,
                 fallback_template: str = "", fallback_model: str = "") -> None:
        if not command_template.strip():
            raise ValueError("command template is required")
        self.command_template = command_template
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.fallback_template = fallback_template
        self.fallback_model = fallback_model

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
        attempts = [(self.command_template, self.model, f"primary-{i+1}") for i in range(self.retries + 1)]
        if self.fallback_template:
            attempts.append((self.fallback_template, self.fallback_model or self.model, "fallback"))
        failures: list[str] = []
        for template, model, label in attempts:
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
                return output_model.model_validate(read_json(output_path))
            except Exception as exc:
                failures.append(f"{label}: invalid JSON: {exc}")
        raise RuntimeError("All structured agent attempts failed: " + " | ".join(failures))


class MockAgent(StructuredAgent):
    def __init__(self, context: dict[str, Any]) -> None:
        self.context = context

    def run(self, *, stage: str, prompt: str, output_model: type[BaseModel], request_dir: Path) -> BaseModel:
        episode_id = self.context["episode_id"]
        if output_model is Narration:
            text = self.context.get("mock_narration") or (
                "One of our contractor clients had a strange problem. The receipts were correct, but the jobs were wrong. "
                "Their crew bought materials from several suppliers, and later the owner had to remember which purchase belonged to which project. "
                "We built a matcher that first lets vision AI read the receipt, then adds business context: who bought it, where that person worked that day, the supplier, the items and recent job history. "
                "Normal code accepts only strong matches. If the context is ambiguous, the system asks one short question instead of guessing. "
                "That means the owner reviews exceptions, not every receipt. A basic version can be built with a message inbox, n8n, a vision model and a jobs sheet. "
                "For a real business, I would connect the schedule, accounting and project system directly, and keep humans only on the uncertain cases."
            )
            return Narration(
                episode_id=episode_id, text=text, word_count=len(text.split()), target_seconds=58,
                hook="The receipts were correct, but the jobs were wrong.",
                consultation_line="Connect the real business systems and keep humans only on uncertain cases.",
            )
        if output_model is DirectorPlan:
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
            return DirectorPlan(
                episode_id=episode_id, duration_seconds=58,
                visual_thesis="AI handles ambiguous receipt understanding; deterministic code handles confident routing; the owner sees only exceptions.",
                scenes=scenes,
                budgets=DirectorBudgets(max_visual_moments=7, max_generated_assets=5, max_scene_seconds=8, max_consecutive_non_talking_head_seconds=16),
            )
        raise RuntimeError(f"MockAgent has no fixture for {output_model.__name__}")

from pathlib import Path

import pytest

from shorts_factory.agents import MockAgent
from shorts_factory.io import write_json
from shorts_factory.models import (
    DemoAction, DemoJob, DemoJobBundle, DirectorPlan, EpisodeBrief, EpisodeStage, Narration, StoryPlan,
    WordTimestamp, WordTimestampBundle,
)
from shorts_factory.pipeline import _stage_builder_demo_jobs, ensure_demo_jobs, generate_narration
from shorts_factory.project import ProjectStore
from shorts_factory.prompt_registry import PROMPT_ROOT, PROMPT_VARIABLE, _render, build_prompt
from shorts_factory.prompts import (
    narration_prompt, narration_rewrite_prompt, prototype_builder_prompt, story_structure_prompt,
)
from shorts_factory.story_quality import assess_narration


def test_mock_narration_is_a_validated_two_pass_contract(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="story-01", title="Quote review", pain_point="Every quote needs manual review.",
        industry="Logistics", role="Coordinator",
        backend_summary=["AI maps inconsistent charge labels."],
        viewer_diy=["Route uncertain fields to a review sheet."],
    ))

    narration = generate_narration(store, "story-01", agent_kind="mock")
    story = StoryPlan.model_validate_json(
        (store.project_dir("story-01") / "01_narration/story_plan.json").read_text(encoding="utf-8")
    )
    validated = Narration.model_validate(narration.model_dump())

    assert [paragraph.beat_id for paragraph in validated.paragraphs] == [beat.beat_id for beat in story.beats]
    assert store.state("story-01").stage == EpisodeStage.NARRATION_READY
    quality = (store.project_dir("story-01") / "01_narration/narration_quality.json")
    assert quality.exists()
    assert '"passed": true' in quality.read_text(encoding="utf-8")
    assert (store.project_dir("story-01") / "_requests/story_structure_invocation.json").exists()
    assert (store.project_dir("story-01") / "_requests/narration_invocation.json").exists()


def test_prompt_registry_rejects_missing_template_variables():
    with pytest.raises(ValueError, match="Missing prompt variables"):
        build_prompt("story_structure")


def test_every_prompt_template_treats_payload_braces_as_literal_data():
    hostile_payload = (
        'const {captured, tilt} = camera; '
        'const captured = {captured}; const tilt = {tilt}; '
        'const recursive = "{scene_id}"; .card{transform:rotate(2deg)}'
    )
    for path in PROMPT_ROOT.glob("*.txt"):
        template = path.read_text(encoding="utf-8")
        variables = set(PROMPT_VARIABLE.findall(template))
        if not variables:
            continue
        values = {name: f"value-{name}" for name in variables}
        injected_at = sorted(variables)[0]
        values[injected_at] = hostile_payload

        rendered = _render(path, values)

        assert hostile_payload in rendered, path.name
        assert "{captured}" in rendered, path.name
        assert "{tilt}" in rendered, path.name
        assert "{scene_id}" in rendered, path.name


def test_narration_prompt_is_a_client_story_written_for_screen_recorded_proof():
    brief = EpisodeBrief(
        episode_id="pain-002",
        title="Omnichannel invoice inbox with AI deduplication",
        pain_point="The client thought they needed a new system, but invoices were simply scattered across channels.",
        industry="Small Business",
        role="Owner",
        backend_summary=["AI extracts invoice fields and recognizes duplicate documents."],
        viewer_diy=["Route email and Drive uploads into one intake workflow."],
    )
    story = StoryPlan.model_validate({
        "episode_id": "pain-002",
        "target_seconds": 58,
        "case_nature": "real",
        "beats": [
            {"beat_id": "B01", "purpose": "hook", "summary": "Client pain", "claim_ids": ["pain-01"], "emotional_register": "curiosity"},
            {"beat_id": "B02", "purpose": "problem", "summary": "Scattered intake", "claim_ids": ["pain-01"], "emotional_register": "tension"},
            {"beat_id": "B03", "purpose": "solution", "summary": "Unified workflow", "claim_ids": ["backend-01"], "emotional_register": "clarity"},
            {"beat_id": "B04", "purpose": "diy", "summary": "Build it", "claim_ids": ["diy-01"], "emotional_register": "agency"},
            {"beat_id": "B05", "purpose": "cta", "summary": "Soft invitation", "claim_ids": [], "emotional_register": "trust"},
        ],
    })

    prompt = narration_prompt(brief, story)

    assert "curious, quietly confident builder" in prompt
    assert "Do not narrate mouse clicks" in prompt
    assert "FULL CLIENT BRIEF" in prompt
    assert brief.pain_point in prompt
    assert "Name only inputs, fields, states, and decisions actually supplied by the brief" in prompt
    assert "Create a shared discovery when the facts support it" in prompt
    assert "simple spoken English" in prompt
    assert "one episode-specific takeaway" in prompt
    assert "similar or related decision bottleneck" in prompt
    assert "without assuming they share this exact workflow" in prompt
    assert "asking them to build a full system" in prompt
    assert "soft follow-along series CTA" in prompt
    assert "Use only supplied claim IDs" in prompt
    assert "every factual statement is grounded and carries supplied claim IDs" in prompt
    assert "one spoken paragraph for every supplied beat" in prompt


def test_narration_rewrite_prompt_repairs_tone_without_weakening_contracts():
    brief = EpisodeBrief(
        episode_id="rewrite-01", title="Request review",
        pain_point="A coordinator has to interpret each incoming request.",
        industry="Services", role="Coordinator", case_nature="real",
        backend_summary=["AI extracts the requested fields."],
        viewer_diy=["Test extraction on five representative requests."],
    )
    story = StoryPlan.model_validate({
        "episode_id": "rewrite-01", "target_seconds": 58, "case_nature": "real",
        "beats": [
            {"beat_id": "B01", "purpose": "hook", "summary": "Daily requests", "claim_ids": ["pain-01"], "emotional_register": "curiosity"},
            {"beat_id": "B02", "purpose": "insight", "summary": "Interpretation matters", "claim_ids": ["pain-01"], "emotional_register": "clarity"},
            {"beat_id": "B03", "purpose": "solution", "summary": "Extract fields", "claim_ids": ["backend-01"], "emotional_register": "proof"},
            {"beat_id": "B04", "purpose": "diy", "summary": "Test examples", "claim_ids": ["diy-01"], "emotional_register": "agency"},
            {"beat_id": "B05", "purpose": "cta", "summary": "Follow along", "claim_ids": [], "emotional_register": "trust"},
        ],
    })
    paragraph_texts = [
        "A coordinator reviews incoming requests every day.",
        "The hard part is understanding what each request means.",
        "We use AI to extract the fields the workflow needs.",
        "Try the supplied test on a few representative requests.",
        "Follow along as we share more of these builds.",
    ]
    paragraphs = [
        {"paragraph_id": f"P{index:02d}", "beat_id": f"B{index:02d}", "text": text,
         "claim_ids": story.beats[index - 1].claim_ids}
        for index, text in enumerate(paragraph_texts, 1)
    ]
    draft = Narration.model_validate({
        "episode_id": "rewrite-01", "text": " ".join(paragraph_texts),
        "word_count": len(" ".join(paragraph_texts).split()), "target_seconds": 58,
        "hook": paragraph_texts[0], "consultation_line": paragraph_texts[-1],
        "paragraphs": paragraphs,
    })

    prompt = narration_rewrite_prompt(brief, story, draft, ["draft reads like a feature list"])

    assert "technically correct but emotionally distant" in prompt
    assert "create a shared discovery" in prompt
    assert "regular code, company rules, company data, or human review" in prompt
    assert "one short, practical takeaway earned from this episode" in prompt
    assert "similar or related problem" in prompt
    assert "build a sophisticated full system" in prompt
    assert "soft follow-along invitation" in prompt
    assert "preserve exact IDs and relevant claim IDs" in prompt
    assert "without adding unsupported facts" in prompt


def test_story_prompts_are_domain_neutral_and_require_a_grounded_spine():
    brief = EpisodeBrief(
        episode_id="neutral-01", title="Cost-code matcher",
        pain_point="Every Friday an owner reconciles estimates and actuals by hand.",
        industry="Small Business", role="Owner", case_nature="real",
        backend_summary=["AI maps inconsistent descriptions to cost codes."],
    )

    prompt = story_structure_prompt(brief)

    assert "story_spine" in prompt
    assert "source_gaps" in prompt
    assert "Prefer five substantial beats" in prompt
    assert "shared-discovery turning insight" in prompt
    assert "transferable lesson from this specific case" in prompt
    assert "similar or related bottleneck" in prompt
    assert "soft continuation of the portfolio series" in prompt
    assert "Every factual beat must carry exact supplied claim IDs" in prompt
    assert "email PDFs" not in prompt
    assert "NEW, DUPLICATE" not in prompt


def test_quality_gate_rejects_feature_copy_that_barely_covers_the_client_pain():
    brief = EpisodeBrief(
        episode_id="weak-01", title="Cost matcher",
        pain_point="An owner reconciles estimates and actuals every Friday.",
        industry="Small Business", role="Owner", case_nature="real",
    )
    story = StoryPlan.model_validate({
        "episode_id": "weak-01", "target_seconds": 58, "case_nature": "real",
        "beats": [
            {"beat_id": "B01", "purpose": "hook", "summary": "Mismatch", "claim_ids": ["pain-01"], "emotional_register": "curiosity"},
            {"beat_id": "B02", "purpose": "problem", "summary": "Manual work", "claim_ids": ["pain-01"], "emotional_register": "tension"},
            {"beat_id": "B03", "purpose": "solution", "summary": "Matcher", "claim_ids": ["pain-01"], "emotional_register": "clarity"},
            {"beat_id": "B04", "purpose": "cta", "summary": "Close", "claim_ids": ["pain-01"], "emotional_register": "trust"},
        ],
    })
    paragraphs = [
        {"paragraph_id": "P01", "beat_id": "B01", "text": "Estimates here and actuals elsewhere.", "claim_ids": ["pain-01"]},
        {"paragraph_id": "P02", "beat_id": "B02", "text": "Warnings arrived late.", "claim_ids": ["pain-01"]},
        {"paragraph_id": "P03", "beat_id": "B03", "text": "Transactions feed in. AI maps descriptions. Rules calculate every variance and produce a dashboard with categorized results for every incoming record.", "claim_ids": ["pain-01"]},
        {"paragraph_id": "P04", "beat_id": "B04", "text": "Contact us if you want a complete production implementation connected to all of your systems with monitoring and ongoing support.", "claim_ids": ["pain-01"]},
    ]
    narration = Narration.model_validate({
        "episode_id": "weak-01", "text": " ".join(item["text"] for item in paragraphs),
        "word_count": 49, "target_seconds": 58, "hook": paragraphs[0]["text"],
        "consultation_line": paragraphs[-1]["text"], "paragraphs": paragraphs,
    })

    report = assess_narration(brief, story, narration)

    assert not report.passed
    assert not report.opening_has_protagonist
    assert report.pain_word_ratio < 0.24
    assert not report.solution_uses_client_story_voice


def test_story_prompt_preserves_operator_declared_real_case():
    brief = EpisodeBrief(
        episode_id="real-01", title="Client workflow", pain_point="A client had invoices spread across channels.",
        industry="Small Business", role="Owner", case_nature="real",
    )

    from shorts_factory.prompts import story_structure_prompt

    prompt = story_structure_prompt(brief)
    assert "Operator-declared case nature: real" in prompt
    assert "Preserve the operator-supplied case nature exactly" in prompt


def test_offline_story_preserves_operator_declared_real_case(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="real-mock", title="Real client workflow",
        pain_point="A client had invoices spread across channels.",
        industry="Small Business", role="Owner", case_nature="real",
    ))

    generate_narration(store, "real-mock", agent_kind="mock")
    story = StoryPlan.model_validate_json(
        (store.project_dir("real-mock") / "01_narration/story_plan.json").read_text(encoding="utf-8")
    )

    assert story.case_nature == "real"


def test_narration_word_count_mismatch_warns_and_is_normalized():
    with pytest.warns(UserWarning, match="normalized to deterministic count 4"):
        narration = Narration.model_validate({
            "episode_id": "count-warning",
            "text": "One two three four",
            "word_count": 2,
            "target_seconds": 10,
            "hook": "One two",
            "consultation_line": "three four",
            "paragraphs": [],
        })

    assert narration.word_count == 4


def test_recording_contracts_are_created_for_approved_screen_scenes(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="capture-01", title="Capture contract",
        pain_point="A working prototype should be ready to record.", industry="Test", role="Owner",
    ))
    project = store.project_dir("capture-01")
    plan = MockAgent({"episode_id": "capture-01"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path,
    )
    write_json(project / "03_director/director_plan.approved.json", plan)
    (project / "04_prototype/index.html").write_text("<!doctype html><title>Demo</title>")

    bundle = ensure_demo_jobs(store, "capture-01")

    assert bundle.jobs
    assert all(job.url.endswith(f"#{job.scene_id}") for job in bundle.jobs)
    assert all(job.output_path.startswith("06_recordings/") for job in bundle.jobs)
    assert all((project / "05_asset_jobs" / f"{job.job_id}.json").is_file() for job in bundle.jobs)


def test_prototype_prompt_prioritizes_camera_ready_portrait_proof():
    brief = EpisodeBrief(
        episode_id="portrait-proof", title="Portrait proof",
        pain_point="The operational state needs to be visible in the reel.", industry="Test", role="Owner",
    )
    words = WordTimestampBundle(
        episode_id="portrait-proof", audio_duration_seconds=9, whisper_model="base.en",
        audio_sha256="a" * 64,
        words=[
            WordTimestamp(index=0, paragraph_id="P01", beat_id="B01", word="reviewer", start=5.4, end=5.8),
            WordTimestamp(index=1, paragraph_id="P01", beat_id="B01", word="sees", start=5.8, end=6.1),
            WordTimestamp(index=2, paragraph_id="P01", beat_id="B01", word="evidence", start=6.1, end=6.7),
        ],
    )
    prompt = prototype_builder_prompt(brief, [{
        "scene_id": "S05", "start": 5.0, "end": 8.0,
        "purpose": "Show the reviewed record", "narration_excerpt": "A reviewer sees the evidence.",
        "on_screen_text": ["CONFIDENCE + EVIDENCE"], "emphasis": ["reviewer", "evidence"],
    }], words)

    assert "VISUAL PRODUCTION ASSET" in prompt
    assert "1080x1920" in prompt
    assert "Do not rely on a normal phone breakpoint" in prompt
    assert "on_screen_text` is editorial guidance, not a checklist to transcribe" in prompt
    assert "window.__svfSetTime(localSeconds, timelineCues)" in prompt
    assert '"local_start": 1.1' in prompt
    assert "exact consecutive `anchor_text` phrase" in prompt
    assert 'data-testid="scene-<lowercase-scene-id>"' in prompt
    assert "scene-S05` is invalid" in prompt
    assert "390x844" in prompt


def test_builder_authored_demo_jobs_must_match_portrait_episode_canvas(tmp_path: Path):
    store = ProjectStore(tmp_path / "projects")
    store.create(EpisodeBrief(
        episode_id="bad-capture", title="Bad capture",
        pain_point="The capture contract must preserve the reel canvas.", industry="Test", role="Owner",
    ))
    project = store.project_dir("bad-capture")
    plan = MockAgent({"episode_id": "bad-capture"}).run(
        stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path,
    )
    write_json(project / "03_director/director_plan.approved.json", plan)
    (project / "04_prototype/index.html").write_text(
        '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><main data-testid="demo"></main>',
        encoding="utf-8",
    )
    bundle = ensure_demo_jobs(store, "bad-capture")
    payload = bundle.model_dump(mode="json")
    payload["jobs"][0]["viewport_width"] = 720
    write_json(project / "05_asset_jobs/demo_jobs.json", payload)

    with pytest.raises(RuntimeError, match="viewport must match the 1080x1920 portrait episode canvas"):
        ensure_demo_jobs(store, "bad-capture")


def test_sandbox_local_demo_jobs_are_staged_into_the_episode_contract_folder(tmp_path: Path):
    project = tmp_path / "stage-capture"
    prototype = project / "04_prototype"
    bundle = DemoJobBundle(episode_id="stage-capture", jobs=[DemoJob(
        job_id="demo-s02", scene_id="S02", url="http://127.0.0.1:4173/index.html#S02",
        output_path="06_recordings/s02.webm", actions=[DemoAction(action="goto", value="http://127.0.0.1:4173/index.html#S02")],
    )])
    write_json(prototype / "asset_jobs/demo_jobs.json", bundle)

    staged = _stage_builder_demo_jobs(project, prototype)

    assert staged == bundle
    assert (project / "05_asset_jobs/demo_jobs.json").is_file()
    assert (project / "05_asset_jobs/demo-s02.json").is_file()

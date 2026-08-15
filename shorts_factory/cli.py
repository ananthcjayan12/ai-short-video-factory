from __future__ import annotations

import json
from pathlib import Path

import typer

from .demo import bootstrap_pain001
from .io import load_model
from .models import DirectorPlan, EpisodeBrief, Narration, ProjectSettings
from .orchestrator import PROVIDERS, provider_health
from .pipeline import (
    align_voice, approve_director, bootstrap_reference_demo, generate_director_plan, generate_narration,
    generate_graphics_plan, generate_story_plan, import_talking_head, import_voice, mock_voice, prepare_timeline_preview,
    record_demos, render_preview, run_prototype_builder,
    write_prototype_builder_prompt,
)
from .project import ProjectStore

app = typer.Typer(no_args_is_help=True, help="AI Short Video Factory")


def store(root: str) -> ProjectStore:
    return ProjectStore(root)


@app.command("talking-head-policy")
def talking_head_policy(
    mode: str = typer.Argument(..., help="Use 'allowed' or 'disabled' for the whole project."),
    root: str = typer.Option("projects"),
):
    normalized = mode.strip().lower()
    if normalized not in {"allowed", "disabled"}:
        raise typer.BadParameter("Mode must be 'allowed' or 'disabled'")
    settings = store(root).save_settings(ProjectSettings(include_talking_head=normalized == "allowed"))
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command("init")
def init_episode(
    episode_id: str, title: str = typer.Option(...), pain: str = typer.Option(...),
    industry: str = typer.Option("Small Business"), role: str = typer.Option("Owner"),
    root: str = typer.Option("projects"), overwrite: bool = False,
):
    s = store(root)
    brief = EpisodeBrief(episode_id=episode_id, title=title, pain_point=pain, industry=industry, role=role)
    typer.echo(s.create(brief, overwrite=overwrite))


@app.command("demo")
def demo(episode_id: str = typer.Argument("pain-001"), root: str = typer.Option("projects")):
    s = store(root)
    brief = EpisodeBrief(
        episode_id=episode_id, title="Context-aware receipt-to-job matcher",
        pain_point="Materials from multiple suppliers end up charged to the wrong job.",
        industry="Contractor / Handyman", role="Owner / GC",
        backend_summary=[
            "Vision AI reads vendor, date, items and total from the receipt.",
            "A reasoning step checks crew member, today's work schedule, supplier, purchased items and recent job history.",
            "Deterministic rules accept only strong matches; ambiguous purchases become one short review question.",
        ],
        viewer_diy=[
            "Active Jobs sheet", "Receipt sent through WhatsApp/Telegram", "n8n + vision AI extracts fields",
            "Write Job + Confidence + Reason to a results sheet", "Low confidence goes to REVIEW",
        ],
    )
    s.create(brief, overwrite=True)
    generate_narration(s, episode_id, agent_kind="mock")
    mock_voice(s, episode_id, seconds=58)
    generate_director_plan(s, episode_id, agent_kind="mock")
    approve_director(s, episode_id)
    bootstrap_reference_demo(s, episode_id)
    typer.echo(f"Created reference episode at {s.project_dir(episode_id)}")


@app.command("narrate")
def narrate(
    episode_id: str, agent: str = typer.Option(None),
    consume_response: bool = typer.Option(False, help="Validate and consume existing manual response JSON files."),
    root: str = typer.Option("projects"),
):
    n = generate_narration(store(root), episode_id, agent_kind=agent, consume_response=consume_response)
    typer.echo(n.text)


@app.command("story")
def story(
    episode_id: str, agent: str = typer.Option(None),
    consume_response: bool = typer.Option(False, help="Validate and consume an existing manual response JSON file."),
    root: str = typer.Option("projects"),
):
    plan = generate_story_plan(store(root), episode_id, agent_kind=agent, consume_response=consume_response)
    typer.echo(json.dumps(plan.model_dump(mode="json"), indent=2))


@app.command("mock-voice")
def voice_mock(episode_id: str, seconds: float = 58.0, root: str = typer.Option("projects")):
    typer.echo(mock_voice(store(root), episode_id, seconds=seconds).audio_path)


@app.command("import-voice")
def voice_import(episode_id: str, path: Path, root: str = typer.Option("projects")):
    typer.echo(import_voice(store(root), episode_id, path).audio_path)


@app.command("align-voice")
def align_voice_cmd(
    episode_id: str,
    force: bool = typer.Option(False, help="Ignore a matching cached Whisper alignment."),
    root: str = typer.Option("projects"),
):
    timing = align_voice(store(root), episode_id, force=force)
    typer.echo(json.dumps(timing.model_dump(mode="json"), indent=2))


@app.command("direct")
def direct(
    episode_id: str, agent: str = typer.Option(None),
    consume_response: bool = typer.Option(False, help="Validate and consume an existing manual response JSON file."),
    root: str = typer.Option("projects"),
):
    plan = generate_director_plan(store(root), episode_id, agent_kind=agent, consume_response=consume_response)
    typer.echo(json.dumps(plan.model_dump(mode="json"), indent=2))


@app.command("approve-director")
def approve_dir(episode_id: str, root: str = typer.Option("projects")):
    plan = approve_director(store(root), episode_id)
    typer.echo(f"Approved {len(plan.scenes)} scenes")


@app.command("prototype-prompt")
def prototype_prompt_cmd(episode_id: str, root: str = typer.Option("projects")):
    typer.echo(write_prototype_builder_prompt(store(root), episode_id))


@app.command("build-prototype")
def build_prototype_cmd(episode_id: str, root: str = typer.Option("projects")):
    typer.echo(run_prototype_builder(store(root), episode_id))


@app.command("bootstrap-pain001")
def bootstrap_pain001_cmd(episode_id: str = typer.Argument("pain-001"), root: str = typer.Option("projects")):
    bootstrap_pain001(store(root).project_dir(episode_id))
    typer.echo("Prototype + Playwright jobs created")


@app.command("record-demos")
def record_demo_cmd(episode_id: str, root: str = typer.Option("projects")):
    paths = record_demos(store(root), episode_id)
    for path in paths: typer.echo(path)


@app.command("generate-graphics")
def generate_graphics_cmd(
    episode_id: str,
    agent: str = typer.Option(None, help="Use 'mock' for a deterministic offline graphics plan."),
    consume_response: bool = typer.Option(False, help="Validate and consume an existing manual response JSON file."),
    root: str = typer.Option("projects"),
):
    plan = generate_graphics_plan(
        store(root), episode_id, agent_kind=agent, consume_response=consume_response,
    )
    typer.echo(json.dumps(plan.model_dump(mode="json"), indent=2))


@app.command("import-head")
def import_head_cmd(episode_id: str, scene_id: str, path: Path, root: str = typer.Option("projects")):
    typer.echo(import_talking_head(store(root), episode_id, scene_id, path))


@app.command("render-preview")
def render_preview_cmd(episode_id: str, root: str = typer.Option("projects")):
    typer.echo(json.dumps(render_preview(store(root), episode_id), indent=2))


@app.command("prepare-preview")
def prepare_preview_cmd(episode_id: str, root: str = typer.Option("projects")):
    """Build the interactive full timeline without rendering an MP4."""
    typer.echo(json.dumps(prepare_timeline_preview(store(root), episode_id), indent=2))


@app.command("status")
def status(episode_id: str, root: str = typer.Option("projects")):
    s = store(root)
    typer.echo(json.dumps(s.state(episode_id).model_dump(mode="json"), indent=2))


@app.command("doctor")
def doctor():
    for provider_id in PROVIDERS:
        h = provider_health(provider_id)
        typer.echo(f"{provider_id:22} {h['status']:12} {h['detail']}")


@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", help="Interface to bind to."),
    port: int = typer.Option(8787, min=1, max=65535, help="Port for the Factory Desk."),
    reload: bool = typer.Option(False, help="Reload automatically while developing the UI."),
):
    """Open the local Factory Desk web interface."""
    import uvicorn

    typer.echo(f"Factory Desk: http://{host}:{port}")
    uvicorn.run("shorts_factory.ui.server:app", host=host, port=port, reload=reload)

@app.command("render-final")
def render_final_cmd(episode_id: str, root: str = typer.Option("projects")):
    from .pipeline import render_final
    typer.echo(json.dumps(render_final(store(root), episode_id), indent=2))


@app.command("approve-final")
def approve_final_cmd(episode_id: str, root: str = typer.Option("projects")):
    s = store(root)
    final_path = s.project_dir(episode_id) / "10_final/final.mp4"
    if not final_path.exists():
        raise typer.BadParameter("Render final.mp4 before approving it")
    typer.echo(json.dumps(s.approve_final(episode_id).model_dump(mode="json"), indent=2))


@app.command("qa")
def qa_cmd(episode_id: str, root: str = typer.Option("projects")):
    from .qa import episode_qa
    typer.echo(json.dumps(episode_qa(store(root).project_dir(episode_id)), indent=2))

@app.command("generate-voice")
def generate_voice_cmd(episode_id: str, root: str = typer.Option("projects")):
    from .pipeline import generate_voice
    typer.echo(generate_voice(store(root), episode_id).audio_path)


@app.command("generate-head")
def generate_head_cmd(episode_id: str, scene_id: str, reference: Path | None = None, root: str = typer.Option("projects")):
    from .pipeline import generate_talking_head
    typer.echo(generate_talking_head(store(root), episode_id, scene_id, reference=reference))

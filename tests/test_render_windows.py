from pathlib import Path
from shorts_factory.agents import MockAgent
from shorts_factory.models import DirectorPlan
from shorts_factory.rendering.hyperframes import chunk_windows


def test_render_chunks_align_to_scene_boundaries(tmp_path: Path):
    plan = MockAgent({"episode_id":"pain-001"}).run(stage="director", prompt="", output_model=DirectorPlan, request_dir=tmp_path)
    windows = chunk_windows(plan, max_seconds=30)
    assert windows[0][0] == 0
    assert windows[-1][1] == 58
    scene_edges = {0.0, 58.0} | {float(s.end) for s in plan.scenes}
    assert all(a in scene_edges and b in scene_edges for a,b in windows)

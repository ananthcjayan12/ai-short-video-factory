from pathlib import Path
from shorts_factory.demo import bootstrap_pain001


def test_pain001_demo_has_stable_jobs(tmp_path: Path):
    project = tmp_path / "pain-001"
    project.mkdir()
    bundle = bootstrap_pain001(project)
    assert len(bundle.jobs) == 3
    html = (project / "04_prototype/index.html").read_text()
    assert 'data-testid="find-job"' in html
    assert '94% confidence' in html
    assert (project / "05_asset_jobs/demo-match.json").exists()

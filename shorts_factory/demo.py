from __future__ import annotations

from pathlib import Path

from .io import write_json
from .models import DemoAction, DemoJob, DemoJobBundle


PAIN001_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Receipt Job Matcher</title>
<style>
:root{--bg:#07111c;--panel:#0f1f2e;--ink:#f5f9fc;--muted:#9eb1c3;--teal:#61e6c1;--amber:#ffd166;--red:#ff7a90}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
.shell{width:100vw;height:100vh;padding:70px 54px;display:flex;flex-direction:column;gap:26px;background:radial-gradient(circle at 75% 10%,#14344a 0,#07111c 48%)}
.kicker{font-size:22px;letter-spacing:.12em;text-transform:uppercase;color:var(--teal);font-weight:800}.title{font-size:52px;line-height:1.02;font-weight:900;max-width:880px}
.sub{font-size:25px;color:var(--muted);line-height:1.35}.grid{display:grid;grid-template-columns:1fr;gap:22px;flex:1}.card{background:rgba(15,31,46,.92);border:1px solid rgba(255,255,255,.09);border-radius:28px;padding:30px;box-shadow:0 28px 80px rgba(0,0,0,.28)}
.receipt{display:grid;grid-template-columns:150px 1fr;gap:20px;align-items:center}.paper{height:190px;border-radius:18px;background:#f8f3e8;color:#222;padding:18px;font-family:ui-monospace,monospace;font-size:13px;transform:rotate(-2deg);box-shadow:0 15px 30px rgba(0,0,0,.28)}
.row{display:flex;justify-content:space-between;gap:18px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.07);font-size:22px}.label{color:var(--muted)}.value{font-weight:750;text-align:right}.actions{display:flex;gap:14px;flex-wrap:wrap}.btn{border:0;border-radius:999px;padding:17px 24px;font-size:21px;font-weight:850;cursor:pointer;background:var(--teal);color:#05241b}.btn.secondary{background:#20364a;color:var(--ink)}
.hidden{display:none!important}.result{padding:28px;border-radius:24px;background:rgba(97,230,193,.09);border:1px solid rgba(97,230,193,.32)}.result.review{background:rgba(255,209,102,.09);border-color:rgba(255,209,102,.45)}
.score{font-size:48px;font-weight:950}.score small{font-size:24px;color:var(--muted)}.chips{display:flex;gap:10px;flex-wrap:wrap;margin-top:15px}.chip{padding:9px 13px;border-radius:999px;background:#183044;color:#cbe0ee;font-size:17px}.question{font-size:27px;font-weight:850;margin-top:12px}.foot{font-size:17px;color:var(--muted)}
</style>
</head>
<body>
<div class="shell">
  <div><div class="kicker">Context-aware job costing</div><div class="title">Which job does this receipt belong to?</div><div class="sub">AI reads the messy receipt. Business context decides whether the match is safe.</div></div>
  <div class="grid">
    <section class="card receipt">
      <div class="paper">HARBOR PLUMBING<br><br>PVC fittings&nbsp;&nbsp;84.20<br>Bathroom mixer&nbsp;249.00<br>Copper pipe&nbsp;&nbsp;150.47<br><br><b>TOTAL $483.67</b><br><br>14 AUG 2026</div>
      <div>
        <div class="row"><span class="label">Crew member</span><span class="value">Mike</span></div>
        <div class="row"><span class="label">Today’s schedule</span><span class="value">Riverside Villa</span></div>
        <div class="row"><span class="label">Supplier</span><span class="value">Harbor Plumbing</span></div>
        <div id="extracted" class="hidden">
          <div class="row"><span class="label">AI extracted</span><span class="value">Plumbing · $483.67</span></div>
          <div class="row"><span class="label">Recent history</span><span class="value">4 Riverside purchases</span></div>
        </div>
        <div class="actions" style="margin-top:22px">
          <button class="btn" data-testid="receive-receipt">Read receipt</button>
          <button class="btn secondary hidden" data-testid="find-job">Find job</button>
          <button class="btn secondary hidden" data-testid="try-ambiguous">Try ambiguous receipt</button>
        </div>
      </div>
    </section>
    <section id="match-result" class="result hidden" data-testid="match-result">
      <div class="label">Suggested job</div><div class="score">Riverside Villa <small>94% confidence</small></div>
      <div class="chips"><span class="chip">Mike scheduled here</span><span class="chip">Plumbing items fit scope</span><span class="chip">Supplier history matches</span></div>
    </section>
    <section id="review-result" class="result review hidden" data-testid="review-result">
      <div class="label">Human review required</div><div class="score">REVIEW <small>61% confidence</small></div>
      <div class="question">Was this purchase for Riverside Villa or Downtown Office?</div>
      <div class="chips"><span class="chip">Mike visited both jobs</span><span class="chip">Generic hardware items</span><span class="chip">No strong supplier history</span></div>
    </section>
  </div>
  <div class="foot">Synthetic demo data · the system never auto-posts an ambiguous purchase.</div>
</div>
<script>
const read=document.querySelector('[data-testid="receive-receipt"]');
const find=document.querySelector('[data-testid="find-job"]');
const amb=document.querySelector('[data-testid="try-ambiguous"]');
read.addEventListener('click',()=>{document.getElementById('extracted').classList.remove('hidden');find.classList.remove('hidden');});
find.addEventListener('click',()=>{document.getElementById('match-result').classList.remove('hidden');amb.classList.remove('hidden');document.getElementById('review-result').classList.add('hidden');});
amb.addEventListener('click',()=>{document.getElementById('match-result').classList.add('hidden');document.getElementById('review-result').classList.remove('hidden');});
</script>
</body></html>'''


def bootstrap_pain001(project_dir: Path, *, base_url: str = "http://127.0.0.1:4173/index.html") -> DemoJobBundle:
    prototype = project_dir / "04_prototype"
    prototype.mkdir(parents=True, exist_ok=True)
    (prototype / "index.html").write_text(PAIN001_HTML, encoding="utf-8")

    jobs = [
        DemoJob(
            job_id="demo-extract", scene_id="S03", url=base_url,
            output_path="06_recordings/S03-extract.webm",
            actions=[
                DemoAction(action="click", selector='[data-testid="receive-receipt"]'),
                DemoAction(action="wait", milliseconds=1700),
                DemoAction(action="assert_text", selector="#extracted", value="AI extracted"),
                DemoAction(action="wait", milliseconds=1200),
            ],
        ),
        DemoJob(
            job_id="demo-match", scene_id="S06", url=base_url,
            output_path="06_recordings/S06-match.webm",
            actions=[
                DemoAction(action="click", selector='[data-testid="receive-receipt"]'),
                DemoAction(action="wait", milliseconds=500),
                DemoAction(action="click", selector='[data-testid="find-job"]'),
                DemoAction(action="wait", milliseconds=1500),
                DemoAction(action="assert_text", selector='[data-testid="match-result"]', value="94% confidence"),
                DemoAction(action="wait", milliseconds=1800),
            ],
        ),
        DemoJob(
            job_id="demo-review", scene_id="S08", url=base_url,
            output_path="06_recordings/S08-review.webm",
            actions=[
                DemoAction(action="click", selector='[data-testid="receive-receipt"]'),
                DemoAction(action="click", selector='[data-testid="find-job"]'),
                DemoAction(action="wait", milliseconds=500),
                DemoAction(action="click", selector='[data-testid="try-ambiguous"]'),
                DemoAction(action="wait", milliseconds=1200),
                DemoAction(action="assert_text", selector='[data-testid="review-result"]', value="61% confidence"),
                DemoAction(action="wait", milliseconds=1800),
            ],
        ),
    ]
    bundle = DemoJobBundle(episode_id=project_dir.name, jobs=jobs)
    write_json(project_dir / "05_asset_jobs/demo_jobs.json", bundle)
    for job in jobs:
        write_json(project_dir / f"05_asset_jobs/{job.job_id}.json", job)
    return bundle

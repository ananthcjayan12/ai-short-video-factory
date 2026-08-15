import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { chromium } from 'playwright';

const jobPath = process.argv[2];
const projectDir = process.argv[3];
if (!jobPath || !projectDir) {
  console.error('Usage: node scripts/record_demo.mjs JOB_JSON PROJECT_DIR');
  process.exit(2);
}

const job = JSON.parse(fs.readFileSync(jobPath, 'utf8'));
const out = path.resolve(projectDir, job.output_path);
fs.mkdirSync(path.dirname(out), { recursive: true });
const tmp = path.join(path.dirname(out), `.pw-${job.job_id}-${Date.now()}`);
fs.mkdirSync(tmp, { recursive: true });

const browser = await chromium.launch({ headless: true });

// Warm the static prototype without recording so the captured page can paint its
// time-zero state quickly. The recorded file is trimmed again after capture.
const warmContext = await browser.newContext({
  viewport: { width: job.viewport_width, height: job.viewport_height },
});
const warmPage = await warmContext.newPage();
await warmPage.goto(job.url, { waitUntil: 'networkidle' });
await warmContext.close();

const context = await browser.newContext({
  viewport: { width: job.viewport_width, height: job.viewport_height },
  recordVideo: { dir: tmp, size: { width: job.viewport_width, height: job.viewport_height } },
});
const pageCreatedAt = performance.now();
const page = await context.newPage();
await page.goto(job.url, { waitUntil: 'networkidle' });

async function runAction(action) {
  if (action.action === 'goto') await page.goto(action.value, { waitUntil: 'networkidle' });
  if (action.action === 'click') await page.locator(action.selector).click();
  if (action.action === 'upload') await page.locator(action.selector).setInputFiles(action.value);
  if (action.action === 'wait') await page.waitForTimeout(action.milliseconds ?? 500);
  if (action.action === 'screenshot') {
    await page.screenshot({ path: path.resolve(projectDir, action.value), fullPage: true });
  }
  if (action.action === 'assert_text') {
    const text = await page.locator(action.selector).innerText();
    const normalizedText = text.replace(/\s+/g, ' ').trim().toLocaleLowerCase();
    const normalizedExpected = String(action.value ?? '').replace(/\s+/g, ' ').trim().toLocaleLowerCase();
    if (!normalizedText.includes(normalizedExpected)) {
      throw new Error(`Expected ${action.selector} to contain ${action.value}, got: ${text}`);
    }
  }
}

const cues = job.timeline_cues ?? [];
const duration = Number(job.duration_seconds ?? 0);
const usesNarrationTimeline = cues.length > 0 && duration > 0;

if (usesNarrationTimeline) {
  const defaultsToFinalState = (action) => ['assert_text', 'screenshot'].includes(action.action)
    && Number(action.at_seconds ?? 0) <= 0;
  for (const action of job.actions) {
    if (Number(action.at_seconds ?? 0) <= 0 && !defaultsToFinalState(action)) await runAction(action);
  }
  await page.waitForFunction(() => window.__svfReady === true, null, { timeout: 10000 });
  const hasTimeline = await page.evaluate(() => typeof window.__svfSetTime === 'function');
  if (!hasTimeline) {
    throw new Error('Timed demo requires window.__svfSetTime(localSeconds, timelineCues)');
  }
  for (const cue of cues) {
    const count = await page.getByTestId(cue.target_testid).count();
    if (count < 1) throw new Error(`Cue ${cue.cue_id} targets missing data-testid=${cue.target_testid}`);
  }

  await page.evaluate(({ timelineCues }) => {
    window.__svfSetTime(0, timelineCues);
  }, { timelineCues: cues });
  const captureStartedAt = performance.now();
  const pending = job.actions
    .filter((action) => Number(action.at_seconds ?? 0) > 0 || defaultsToFinalState(action))
    .map((action) => ({
      action,
      scheduledAt: defaultsToFinalState(action) ? duration : Number(action.at_seconds),
    }))
    .sort((left, right) => left.scheduledAt - right.scheduledAt);

  let actionIndex = 0;
  while (true) {
    const localSeconds = Math.min(duration, (performance.now() - captureStartedAt) / 1000);
    await page.evaluate(({ time, timelineCues }) => {
      window.__svfSetTime(time, timelineCues);
    }, { time: localSeconds, timelineCues: cues });
    while (actionIndex < pending.length && pending[actionIndex].scheduledAt <= localSeconds + 0.02) {
      await runAction(pending[actionIndex].action);
      actionIndex += 1;
    }
    if (localSeconds >= duration) break;
    await page.waitForTimeout(1000 / 30);
  }
  await page.waitForTimeout(120);

  const video = page.video();
  await context.close();
  if (!video) throw new Error('Playwright did not create a video');
  const rawOut = path.join(tmp, `raw-${job.job_id}.webm`);
  await video.saveAs(rawOut);

  const preRollSeconds = Math.max(0, (captureStartedAt - pageCreatedAt) / 1000);
  const outputIsMp4 = path.extname(out).toLowerCase() === '.mp4';
  const codecArgs = outputIsMp4
    ? ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p']
    : ['-c:v', 'libvpx-vp9', '-deadline', 'good', '-cpu-used', '3', '-crf', '24', '-b:v', '0', '-pix_fmt', 'yuv420p'];
  const trim = spawnSync('ffmpeg', [
    '-y', '-hide_banner', '-loglevel', 'error', '-i', rawOut,
    '-ss', preRollSeconds.toFixed(3), '-t', duration.toFixed(3), '-an', ...codecArgs, out,
  ], { encoding: 'utf8' });
  if (trim.status !== 0) {
    throw new Error(`Failed to trim narration-timed demo: ${trim.stderr || trim.stdout}`);
  }
} else {
  for (const action of job.actions) await runAction(action);
  await page.waitForTimeout(350);
  const video = page.video();
  await context.close();
  if (!video) throw new Error('Playwright did not create a video');
  await video.saveAs(out);
}

await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });
console.log(out);

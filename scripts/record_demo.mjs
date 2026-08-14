import fs from 'node:fs';
import path from 'node:path';
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
const context = await browser.newContext({
  viewport: { width: job.viewport_width, height: job.viewport_height },
  recordVideo: { dir: tmp, size: { width: job.viewport_width, height: job.viewport_height } },
});
const page = await context.newPage();
await page.goto(job.url, { waitUntil: 'networkidle' });
for (const action of job.actions) {
  if (action.action === 'goto') await page.goto(action.value, { waitUntil: 'networkidle' });
  if (action.action === 'click') await page.locator(action.selector).click();
  if (action.action === 'upload') await page.locator(action.selector).setInputFiles(action.value);
  if (action.action === 'wait') await page.waitForTimeout(action.milliseconds ?? 500);
  if (action.action === 'screenshot') await page.screenshot({ path: path.resolve(projectDir, action.value), fullPage: true });
  if (action.action === 'assert_text') {
    const text = await page.locator(action.selector).innerText();
    if (!text.includes(action.value)) throw new Error(`Expected ${action.selector} to contain ${action.value}, got: ${text}`);
  }
}
await page.waitForTimeout(350);
const video = page.video();
await context.close();
if (!video) throw new Error('Playwright did not create a video');
await video.saveAs(out);
await browser.close();
fs.rmSync(tmp, { recursive: true, force: true });
console.log(out);

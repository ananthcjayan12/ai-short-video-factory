import fs from 'node:fs';
import { chromium } from 'playwright';

const baseUrl = process.argv[2];
const jobsPath = process.argv[3];
const sceneIds = process.argv.slice(4);
if (!baseUrl || !jobsPath || !sceneIds.length) {
  console.error('Usage: node scripts/validate_prototype.mjs BASE_URL DEMO_JOBS_JSON SCENE_ID...');
  process.exit(2);
}
const jobsPayload = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
const jobs = new Map((jobsPayload.jobs ?? []).map((job) => [job.scene_id, job]));

const viewports = [
  { name: 'capture', width: 1080, height: 1920, minFont: 12, minCoverage: 0.50 },
  { name: 'phone', width: 390, height: 844, minFont: 11, minCoverage: 0.38 },
];
const browser = await chromium.launch({ headless: true });
const findings = [];

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
    const page = await context.newPage();
    for (const sceneId of sceneIds) {
      const job = jobs.get(sceneId);
      if (!job) {
        findings.push({ scene_id: sceneId, viewport: viewport.name, moment: 'contract', issues: ['missing DemoJob'] });
        continue;
      }
      await page.goto(`${baseUrl}#${sceneId}`, { waitUntil: 'networkidle' });
      const hasTimeline = await page.evaluate(() => typeof window.__svfSetTime === 'function');
      if (!hasTimeline) {
        findings.push({ scene_id: sceneId, viewport: viewport.name, moment: 'contract', issues: ['missing window.__svfSetTime'] });
        continue;
      }
      const moments = [
        { label: 'start', time: 0, target_testid: null },
        ...(job.timeline_cues ?? []).map((cue) => ({
          label: `${cue.cue_id} @ ${Number(cue.at_seconds).toFixed(3)}s`,
          time: Math.min(Number(job.duration_seconds), Number(cue.at_seconds) + 0.08),
          target_testid: cue.target_testid,
        })),
        { label: 'end', time: Number(job.duration_seconds), target_testid: null },
      ];
      for (const moment of moments) {
        await page.evaluate(({ time, timelineCues }) => {
          window.__svfSetTime(time, timelineCues);
        }, { time: moment.time, timelineCues: job.timeline_cues ?? [] });
        const report = await page.evaluate(({ sceneId, viewport, targetTestid }) => {
        const visible = (element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0.02 && rect.width > 0 && rect.height > 0;
        };
        const roots = [
          `[data-testid="scene-${sceneId.toLowerCase()}"]`,
          `[data-scene-id="${sceneId}"]`,
          `[data-scene="${sceneId}"]`,
        ];
        const root = roots.map((selector) => document.querySelector(selector)).find((candidate) => candidate && visible(candidate));
        const issues = [];
        const html = document.documentElement;
        if (html.scrollWidth > innerWidth + 3) issues.push(`horizontal overflow: ${html.scrollWidth}px > ${innerWidth}px`);
        if (!root) return { issues: [...issues, 'missing visible scene root with a scene-specific data attribute'] };
        if (targetTestid) {
          const target = root.querySelector(`[data-testid="${CSS.escape(targetTestid)}"]`)
            || document.querySelector(`[data-testid="${CSS.escape(targetTestid)}"]`);
          if (!target) issues.push(`cue target data-testid=${targetTestid} is missing`);
          else if (!visible(target)) issues.push(`cue target data-testid=${targetTestid} is not visible after its spoken anchor`);
        }
        const rect = root.getBoundingClientRect();
        if (rect.height < innerHeight * viewport.minCoverage) {
          issues.push(`scene proof uses only ${Math.round((rect.height / innerHeight) * 100)}% of the vertical frame`);
        }
        if (viewport.name === 'capture' && html.scrollHeight > innerHeight + 6) {
          issues.push(`capture requires vertical scrolling: ${html.scrollHeight}px > ${innerHeight}px`);
        }
        const heading = [...root.querySelectorAll('h1,h2,[role="heading"]')].find(visible);
        if (!heading) issues.push('scene has no visible primary heading');
        const identify = (element) => {
          const testid = element.getAttribute('data-testid');
          if (testid) return `[data-testid="${testid}"]`;
          if (element.id) return `#${element.id}`;
          const classes = [...element.classList].slice(0, 3).join('.');
          return `${element.tagName.toLowerCase()}${classes ? `.${classes}` : ''}`;
        };
        const tiny = [...root.querySelectorAll('h1,h2,h3,p,span,strong,small,label,button,td,th')]
          .filter((element) => visible(element) && (element.textContent || '').trim())
          .map((element) => ({
            selector: identify(element),
            text: element.textContent.trim().replace(/\s+/g, ' ').slice(0, 70),
            size: parseFloat(getComputedStyle(element).fontSize),
          }))
          .filter((item) => item.size < viewport.minFont);
        if (tiny.length) issues.push(`text below ${viewport.minFont}px (${tiny.length} elements): ${tiny.map((item) => `${item.size}px ${item.selector} “${item.text}”`).join('; ')}`);
        const smallTargets = [...root.querySelectorAll('button,a,input,select,[role="button"]')]
          .filter(visible)
          .map((element) => ({ selector: identify(element), label: (element.textContent || element.getAttribute('aria-label') || element.tagName).trim().slice(0, 50), rect: element.getBoundingClientRect() }))
          .filter((item) => item.rect.height < 40 || item.rect.width < 40);
        if (smallTargets.length) issues.push(`touch targets below 40px (${smallTargets.length} elements): ${smallTargets.map((item) => `${item.selector} “${item.label}”`).join(', ')}`);
        const clipped = [...root.querySelectorAll('*')].filter(visible).filter((element) => {
          const item = element.getBoundingClientRect();
          return item.left < -2 || item.right > innerWidth + 2;
        });
        if (clipped.length) issues.push(`visible elements leave the viewport (${clipped.length} elements): ${clipped.map(identify).join(', ')}`);
        return { issues, sceneHeight: Math.round(rect.height), scrollHeight: html.scrollHeight };
        }, { sceneId, viewport, targetTestid: moment.target_testid });
        findings.push({ scene_id: sceneId, viewport: viewport.name, moment: moment.label, ...report });
      }
    }
    await context.close();
  }
} finally {
  await browser.close();
}

const failed = findings.filter((item) => item.issues.length);
console.log(JSON.stringify({ ok: !failed.length, findings }, null, 2));
if (failed.length) process.exit(1);

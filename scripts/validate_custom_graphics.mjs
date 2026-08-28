import fs from 'node:fs';
import { chromium } from 'playwright';

const [baseUrl, packagePath, rawFps, rawWidth, rawHeight] = process.argv.slice(2);
if (!baseUrl || !packagePath || !rawFps || !rawWidth || !rawHeight) {
  console.error('Usage: node scripts/validate_custom_graphics.mjs URL CUSTOM_PACKAGE FPS WIDTH HEIGHT');
  process.exit(2);
}

const customPackage = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
const fps = Number(rawFps);
const width = Number(rawWidth);
const height = Number(rawHeight);
const frameSeconds = 1 / fps;
const findings = [];
const browser = await chromium.launch({headless: true});

const seek = async (page, time) => {
  await page.evaluate((nextTime) => window.dispatchEvent(new CustomEvent('hf-seek', {detail: {time: nextTime}})), time);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
};

const stateOf = async (page, sceneId, targetId) => page.evaluate(({sceneId, targetId}) => {
  const scene = document.querySelector(`[data-custom-scene="${CSS.escape(sceneId)}"]`);
  const target = scene?.querySelector(`#${CSS.escape(targetId)}`);
  if (!target) return null;
  const rect = target.getBoundingClientRect();
  const style = getComputedStyle(target);
  const descendants = [...target.querySelectorAll('path,line,polyline,polygon')]
    .map((item) => `${item.style.strokeDashoffset}|${item.style.opacity}|${item.getAttribute('d') ?? ''}`)
    .join(';');
  return JSON.stringify({
    left: Math.round(rect.left * 10) / 10,
    top: Math.round(rect.top * 10) / 10,
    width: Math.round(rect.width * 10) / 10,
    height: Math.round(rect.height * 10) / 10,
    opacity: Math.round(Number(style.opacity) * 1000) / 1000,
    transform: style.transform,
    text: target.textContent?.replace(/\s+/g, ' ').trim(),
    descendants,
  });
}, {sceneId, targetId});

try {
  const context = await browser.newContext({viewport: {width, height}});
  const page = await context.newPage();
  const runtimeErrors = [];
  page.on('pageerror', (error) => runtimeErrors.push(String(error)));
  page.on('console', (message) => {
    if (message.type() === 'error') runtimeErrors.push(message.text());
  });
  const renderUrl = new URL(baseUrl);
  renderUrl.searchParams.set('render', '1');
  await page.goto(renderUrl.href, {waitUntil: 'networkidle'});
  await page.waitForFunction(() => window.__hf_ready__ === true);

  for (const bundle of customPackage.scenes ?? []) {
    const layout = bundle.layout;
    const duration = Number(layout.end) - Number(layout.start);
    const openingTime = Math.min(frameSeconds, Math.max(0, duration - frameSeconds));
    await seek(page, Number(layout.start) + openingTime);
    const openingIssues = await page.evaluate(({sceneId, elements, actions, localTime}) => {
      const scene = document.querySelector(`[data-custom-scene="${CSS.escape(sceneId)}"]`);
      if (!scene) return ['missing custom scene root'];
      const problems = [];
      let visibleOpening = 0;
      for (const planned of elements) {
        const element = scene.querySelector(`#${CSS.escape(planned.element_id)}`);
        if (!element) {
          problems.push(`missing element ${planned.element_id}`);
          continue;
        }
        const style = getComputedStyle(element);
        const opacity = Number(style.opacity);
        if (planned.initially_visible) {
          if (opacity <= 0.2 || style.visibility === 'hidden' || style.display === 'none') {
            problems.push(`${planned.element_id} is missing from the opening frame`);
          }
          else visibleOpening += 1;
        } else {
          const reveal = actions.find((action) => action.target_id === planned.element_id && action.action === 'reveal');
          if ((!reveal || Number(reveal.at_seconds) > localTime + 1e-6) && opacity > 0.05) {
            problems.push(`${planned.element_id} leaks into the opening frame before reveal`);
          }
        }
      }
      if (!visibleOpening) problems.push('opening frame has no declared visible element');
      return [...new Set(problems)];
    }, {sceneId: layout.scene_id, elements: layout.elements, actions: layout.actions, localTime: openingTime});
    findings.push({
      scene_id: layout.scene_id,
      moment: 'opening frame',
      time_seconds: Number((Number(layout.start) + openingTime).toFixed(6)),
      frame: Math.ceil((Number(layout.start) + openingTime) * fps - 1e-9),
      issues: openingIssues,
    });

    for (const checkpoint of layout.review_checkpoints ?? []) {
      const localTime = Math.max(0, Math.min(duration - frameSeconds, Number(checkpoint)));
      await seek(page, Number(layout.start) + localTime);
      const issues = await page.evaluate(({sceneId, elements}) => {
        const scene = document.querySelector(`[data-custom-scene="${CSS.escape(sceneId)}"]`);
        if (!scene) return ['missing custom scene root'];
        const stageRect = scene.getBoundingClientRect();
        const visible = elements.map((planned) => {
          const element = scene.querySelector(`#${CSS.escape(planned.element_id)}`);
          if (!element) return null;
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return {planned, element, rect, opacity: Number(style.opacity)};
        }).filter((item) => item && item.opacity > 0.2 && item.rect.width > 2 && item.rect.height > 2);
        const problems = [];
        for (const item of visible) {
          const {planned, element, rect} = item;
          if (rect.left < stageRect.left - 2 || rect.right > stageRect.right + 2 || rect.top < stageRect.top - 2 || rect.bottom > stageRect.bottom + 2) {
            problems.push(`${planned.element_id} leaves the portrait stage`);
          }
          const clippedText = element instanceof HTMLElement && [...element.querySelectorAll('*')].some((child) => {
            if (!(child instanceof HTMLElement) || child.clientWidth <= 2 || child.clientHeight <= 2) return false;
            const hasDirectText = [...child.childNodes].some(
              (node) => node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim()),
            );
            if (!hasDirectText) return false;
            const childStyle = getComputedStyle(child);
            const clipsX = ['hidden', 'clip', 'auto', 'scroll'].includes(childStyle.overflowX);
            const clipsY = ['hidden', 'clip', 'auto', 'scroll'].includes(childStyle.overflowY);
            return (clipsX && child.scrollWidth > child.clientWidth + 3)
              || (clipsY && child.scrollHeight > child.clientHeight + 3);
          });
          if (planned.role !== 'background' && clippedText) {
            problems.push(`${planned.element_id} clips or overflows its reserved frame`);
          }
        }
        for (let first = 0; first < visible.length; first += 1) {
          for (let second = first + 1; second < visible.length; second += 1) {
            const a = visible[first], b = visible[second];
            if (a.planned.role === 'background' || b.planned.role === 'background') continue;
            const overlapX = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
            const overlapY = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
            if (overlapX > 5 && overlapY > 5) problems.push(`${a.planned.element_id} overlaps ${b.planned.element_id}`);
          }
        }
        return [...new Set(problems)];
      }, {sceneId: layout.scene_id, elements: layout.elements});
      findings.push({
        scene_id: layout.scene_id,
        moment: `checkpoint ${localTime.toFixed(3)}s`,
        time_seconds: Number((Number(layout.start) + localTime).toFixed(6)),
        frame: Math.ceil((Number(layout.start) + localTime) * fps - 1e-9),
        issues,
      });
    }

    for (const action of layout.actions ?? []) {
      if (action.action === 'hold') continue;
      const at = Number(action.at_seconds);
      // A cue at local 0 must be sampled inside the active scene. Sampling at
      // the exact global boundary can leave the scene renderer inactive (the
      // compiled start is frame-snapped), which compares stale state and
      // creates an impossible false-positive repair loop.
      const before = Math.max(frameSeconds, at - frameSeconds);
      const after = Math.min(duration - frameSeconds, at + Math.max(Number(action.duration_seconds), frameSeconds * 2));
      if (after <= before + frameSeconds) continue;
      await seek(page, Number(layout.start) + before);
      const stateBefore = await stateOf(page, layout.scene_id, action.target_id);
      await seek(page, Number(layout.start) + after);
      const stateAfter = await stateOf(page, layout.scene_id, action.target_id);
      const issues = [];
      if (!stateBefore || !stateAfter) issues.push(`motion target ${action.target_id} is missing`);
      else if (stateBefore === stateAfter) issues.push(`${action.action} does not produce an observable frame change on ${action.target_id}`);
      findings.push({
        scene_id: layout.scene_id,
        moment: `action ${action.cue_id} ${action.action}`,
        time_seconds: Number((Number(layout.start) + at).toFixed(6)),
        frame: Math.ceil((Number(layout.start) + at) * fps - 1e-9),
        issues,
      });
    }
  }

  if (runtimeErrors.length) {
    findings.push({
      scene_id: 'package', moment: 'runtime', time_seconds: 0, frame: 0,
      issues: [...new Set(runtimeErrors)].slice(0, 12),
    });
  }
  await context.close();
} finally {
  await browser.close();
}

const failed = findings.some((finding) => finding.issues.length);
console.log(JSON.stringify({ok: !failed, fps, findings}, null, 2));
if (failed) process.exit(1);

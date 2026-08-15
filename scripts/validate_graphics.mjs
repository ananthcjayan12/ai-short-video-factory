import fs from 'node:fs';
import { chromium } from 'playwright';

const [baseUrl, planPath, rawFps, rawWidth, rawHeight] = process.argv.slice(2);
if (!baseUrl || !planPath || !rawFps || !rawWidth || !rawHeight) {
  console.error('Usage: node scripts/validate_graphics.mjs URL GRAPHICS_PLAN FPS WIDTH HEIGHT');
  process.exit(2);
}

const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const fps = Number(rawFps);
const width = Number(rawWidth);
const height = Number(rawHeight);
const frameSeconds = 1 / fps;
const findings = [];
const browser = await chromium.launch({headless: true});

const seek = async (page, time) => {
  await page.evaluate((nextTime) => {
    window.dispatchEvent(new CustomEvent('hf-seek', {detail: {time: nextTime}}));
  }, time);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
};

const visualState = async (page, sceneId, targetId) => page.evaluate(({sceneId, targetId}) => {
  const scene = document.querySelector(`[data-scene-id="${CSS.escape(sceneId)}"]`);
  const target = scene?.querySelector(`[data-object-id="${CSS.escape(targetId)}"]`);
  if (!scene || !target) return null;
  const rect = target.getBoundingClientRect();
  const style = getComputedStyle(target);
  const lines = [...scene.querySelectorAll('.graphics-connection')]
    .filter((line) => line.dataset.target === targetId || line.dataset.source === targetId)
    .map((line) => `${line.style.opacity}|${line.style.strokeDashoffset}`)
    .join(';');
  return JSON.stringify({
    left: Math.round(rect.left * 10) / 10,
    top: Math.round(rect.top * 10) / 10,
    width: Math.round(rect.width * 10) / 10,
    height: Math.round(rect.height * 10) / 10,
    opacity: Math.round(Number(style.opacity) * 1000) / 1000,
    transform: style.transform,
    classes: target.className,
    text: target.textContent?.replace(/\s+/g, ' ').trim(),
    lines,
  });
}, {sceneId, targetId});

try {
  const context = await browser.newContext({viewport: {width, height}});
  const page = await context.newPage();
  const renderUrl = new URL(baseUrl);
  renderUrl.searchParams.set('render', '1');
  await page.goto(renderUrl.href, {waitUntil: 'networkidle'});
  await page.waitForFunction(() => window.__hf_ready__ === true);

  for (const scene of plan.scenes ?? []) {
    const duration = Number(scene.end) - Number(scene.start);
    const openingTime = Math.min(frameSeconds, Math.max(0, duration - frameSeconds));
    await seek(page, Number(scene.start) + openingTime);
    const openingIssues = await page.evaluate(({sceneId, objects, actions, localTime}) => {
      const root = document.querySelector(`[data-scene-id="${CSS.escape(sceneId)}"]`);
      if (!root) return ['missing generated scene root'];
      const problems = [];
      let visibleOpeningObjects = 0;
      for (const planned of objects) {
        const object = root.querySelector(`[data-object-id="${CSS.escape(planned.object_id)}"]`);
        if (!object) {
          problems.push(`missing object ${planned.object_id}`);
          continue;
        }
        const opacity = Number(getComputedStyle(object).opacity);
        if (planned.initially_visible) {
          if (opacity < 0.95) problems.push(`${planned.object_id} is missing from the opening frame`);
          else visibleOpeningObjects += 1;
        } else {
          const reveal = actions.find((action) => action.target === planned.object_id && action.action === 'reveal');
          if ((!reveal || Number(reveal.at_seconds) > localTime + 1e-6) && opacity > 0.05) {
            problems.push(`${planned.object_id} leaks into the opening frame before reveal`);
          }
        }
      }
      if (!visibleOpeningObjects) problems.push('opening frame has no declared visible object');
      return [...new Set(problems)];
    }, {sceneId: scene.scene_id, objects: scene.objects ?? [], actions: scene.actions ?? [], localTime: openingTime});
    findings.push({
      scene_id: scene.scene_id,
      moment: 'opening frame',
      time_seconds: Number((Number(scene.start) + openingTime).toFixed(6)),
      frame: Math.ceil((Number(scene.start) + openingTime) * fps - 1e-9),
      issues: openingIssues,
    });
    const checkpoints = scene.review_checkpoints?.length
      ? scene.review_checkpoints
      : [Math.max(0, duration - frameSeconds)];

    for (const checkpoint of checkpoints) {
      const localTime = Math.max(0, Math.min(duration - frameSeconds, Number(checkpoint)));
      const time = Number(scene.start) + localTime;
      await seek(page, time);
      const issues = await page.evaluate(({sceneId, plannedObjects}) => {
        const scene = document.querySelector(`[data-scene-id="${CSS.escape(sceneId)}"]`);
        if (!scene) return ['missing generated scene root'];
        const stage = scene.querySelector('.graphics-stage');
        if (!stage) return ['missing graphics stage'];
        const stageRect = stage.getBoundingClientRect();
        const objects = [...scene.querySelectorAll('.graphics-object')]
          .filter((object) => {
            const style = getComputedStyle(object);
            const rect = object.getBoundingClientRect();
            return Number(style.opacity) > 0.2 && rect.width > 2 && rect.height > 2;
          })
          .map((object) => ({
            id: object.dataset.objectId,
            depth: object.dataset.depth,
            rect: object.getBoundingClientRect(),
            collisionRect: (object.querySelector('.object-copy') ?? object).getBoundingClientRect(),
          }));
        const problems = [];
        const plannedById = new Map(plannedObjects.map((object) => [object.object_id, object]));
        for (const object of objects) {
          const rect = object.rect;
          if (rect.left < stageRect.left - 2 || rect.right > stageRect.right + 2 || rect.top < stageRect.top - 2 || rect.bottom > stageRect.bottom + 2) {
            problems.push(`${object.id} leaves the graphics safe stage`);
          }
          const element = scene.querySelector(`[data-object-id="${CSS.escape(object.id)}"]`);
          const planned = plannedById.get(object.id);
          if (element?.dataset.choreoHidden === 'true') problems.push(`${object.id} was hidden by runtime layout repair`);
          if (Math.abs(Number(element?.dataset.choreoScale ?? 1) - 1) > 0.001) problems.push(`${object.id} was resized by runtime layout repair`);
          if (planned?.frame && element) {
            const expectedWidth = stage.clientWidth * Number(planned.frame.width) / 100;
            const expectedHeight = stage.clientHeight * Number(planned.frame.height) / 100;
            if (Math.abs(element.offsetWidth - expectedWidth) > 1.5 || Math.abs(element.offsetHeight - expectedHeight) > 1.5) {
              problems.push(`${object.id} does not preserve its authored frame size`);
            }
          }
        }
        for (let first = 0; first < objects.length; first += 1) {
          for (let second = first + 1; second < objects.length; second += 1) {
            const a = objects[first];
            const b = objects[second];
            if (a.depth === 'background' || b.depth === 'background') continue;
            const overlapX = Math.min(a.collisionRect.right, b.collisionRect.right) - Math.max(a.collisionRect.left, b.collisionRect.left);
            const overlapY = Math.min(a.collisionRect.bottom, b.collisionRect.bottom) - Math.max(a.collisionRect.top, b.collisionRect.top);
            if (overlapX > 4 && overlapY > 4) problems.push(`${a.id} overlaps ${b.id}`);
          }
        }
        return [...new Set(problems)];
      }, {sceneId: scene.scene_id, plannedObjects: scene.objects ?? []});
      findings.push({
        scene_id: scene.scene_id,
        moment: `checkpoint ${localTime.toFixed(3)}s`,
        time_seconds: Number(time.toFixed(6)),
        frame: Math.ceil(time * fps - 1e-9),
        issues,
      });
    }

    for (const [index, action] of (scene.actions ?? []).entries()) {
      if (action.action === 'hold') continue;
      const at = Number(action.at_seconds);
      const end = Math.min(duration - frameSeconds, at + Math.max(Number(action.duration_seconds ?? 0.65), frameSeconds * 2));
      if (end <= at + frameSeconds * 0.5) continue;
      const before = Math.max(0, at - frameSeconds);
      await seek(page, Number(scene.start) + before);
      const stateBefore = await visualState(page, scene.scene_id, action.target);
      await seek(page, Number(scene.start) + end);
      const stateAfter = await visualState(page, scene.scene_id, action.target);
      const issues = [];
      if (!stateBefore || !stateAfter) issues.push(`motion target ${action.target} is missing`);
      else if (stateBefore === stateAfter) issues.push(`${action.action} does not produce an observable frame change on ${action.target}`);
      findings.push({
        scene_id: scene.scene_id,
        moment: `action ${index + 1} ${action.action}`,
        time_seconds: Number((Number(scene.start) + at).toFixed(6)),
        frame: Math.ceil((Number(scene.start) + at) * fps - 1e-9),
        issues,
      });
    }
  }
  await context.close();
} finally {
  await browser.close();
}

const failed = findings.some((finding) => finding.issues.length);
console.log(JSON.stringify({ok: !failed, fps, findings}, null, 2));
if (failed) process.exit(1);

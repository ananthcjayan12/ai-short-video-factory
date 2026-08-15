const state = {
  dashboard: null,
  selectedId: null,
  detail: null,
  models: null,
  prompts: null,
  logs: [],
  activeJob: null,
  headScene: null,
  filledQuery: "",
  voiceCatalogs: {},
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function label(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
  } catch {
    return "Recently";
  }
}

function durationLabel(value) {
  const seconds = Math.round(Number(value) || 0);
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes}:${String(remainder).padStart(2, "0")}` : `${seconds}s`;
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, cache: "no-store" });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join("; ")
      : detail || body || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body;
}

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 4200);
}

function showLoading() {
  $("#loading-view").classList.remove("hidden");
  $("#empty-view").classList.add("hidden");
  $("#workspace-view").classList.add("hidden");
}

function renderSidebar() {
  const allEpisodes = state.dashboard?.episodes || [];
  const episodes = allEpisodes.filter((episode) => !episode.is_filled_episode);
  const filledEpisodes = state.dashboard?.filled_episodes || [];
  const query = state.filledQuery.trim().toLowerCase();
  const visibleFilled = query
    ? filledEpisodes.filter((episode) => `${episode.source_id} ${episode.title} ${episode.industry}`.toLowerCase().includes(query))
    : filledEpisodes;
  $("#episode-count").textContent = episodes.length;
  $("#episode-list").innerHTML = episodes.length
    ? episodes.map((episode) => `
      <button class="episode-nav-item ${episode.episode_id === state.selectedId ? "active" : ""}"
              data-episode="${escapeHtml(episode.episode_id)}" type="button">
        <strong>${escapeHtml(episode.title)}</strong>
        <span class="episode-nav-meta">
          <span>${escapeHtml(label(episode.stage))}</span>
          <span class="mini-progress"><i style="width:${episode.progress}%"></i></span>
        </span>
      </button>
    `).join("")
    : `<div class="sidebar-empty">No standalone episodes yet.</div>`;

  $("#filled-episode-count").textContent = filledEpisodes.length;
  $("#filled-episode-list").innerHTML = visibleFilled.length
    ? visibleFilled.map((episode) => `
      <button class="episode-nav-item filled-nav-item ${episode.episode_id === state.selectedId ? "active" : ""}"
              data-filled-episode="${escapeHtml(episode.source_id)}" type="button">
        <strong>${escapeHtml(episode.title)}</strong>
        <span class="episode-nav-meta">
          <span>${escapeHtml(episode.source_id)} · ${escapeHtml(episode.industry)}</span>
          <span class="filled-status ${episode.imported ? "imported" : ""}">${episode.imported ? `${episode.progress}%` : "Ready"}</span>
        </span>
      </button>
    `).join("")
    : `<div class="sidebar-empty">No matching stories.</div>`;

  $$("[data-episode]").forEach((button) => {
    button.addEventListener("click", () => selectEpisode(button.dataset.episode));
  });
  $$("[data-filled-episode]").forEach((button) => {
    button.addEventListener("click", () => openFilledEpisode(button.dataset.filledEpisode));
  });
}

function renderHealth() {
  const providers = state.dashboard?.providers || [];
  $("#health-content").innerHTML = providers.map((provider) => `
    <div class="health-item ${provider.healthy ? "healthy" : ""}">
      <i aria-hidden="true"></i>
      <div>
        <strong>${escapeHtml(provider.label)}</strong>
        <span>${escapeHtml(label(provider.status))} · ${escapeHtml(provider.detail)}</span>
      </div>
    </div>
  `).join("");
}

function pipelineHtml(detail) {
  const done = new Set(detail.completed_steps);
  const stages = [
    ["brief", "Brief"],
    ["narration", "Narration"],
    ["voice", "Master voice"],
    ["timing", "Word timing"],
    ["direction", "Direction"],
    ["recordings", "Assets"],
    ["graphics", "Graphics"],
    ["preview", "Review"],
  ];
  return stages.map(([key, name], index) => `
    <div class="pipeline-step ${done.has(key) ? "done" : ""}">
      <i>${done.has(key) ? "✓" : index + 1}</i><span>${name}</span>
    </div>
  `).join("");
}

function narrationCard(detail) {
  const narration = detail.narration;
  const quality = detail.narration_quality;
  return `
    <article class="card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">01</span><div><h2>Narration</h2><p class="card-subtitle">The story and the master creative constraint.</p></div></div>
        <div class="card-actions">
          <button class="button button-quiet button-small" data-action="narrate-mock" type="button">Offline draft</button>
          <button class="button button-dark button-small" data-action="narrate" type="button">${narration ? "Regenerate" : "Generate"}</button>
        </div>
      </div>
      ${narration ? `
        <div class="narration-hook">“${escapeHtml(narration.hook)}”</div>
        <p class="narration-copy">${escapeHtml(narration.text)}</p>
        <div class="copy-meta"><span><b>${narration.word_count}</b> words</span><span><b>${narration.target_seconds}s</b> target</span><span>${quality?.passed ? "✓ Client-story gate" : "Quality report unavailable"}</span>${quality ? `<span><b>${Math.round(Number(quality.pain_word_ratio) * 100)}%</b> hook + problem</span>` : ""}</div>
        ${quality?.warnings?.length ? `<ul class="issue-list">${quality.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : ""}
      ` : `<div class="empty-card"><strong>No narration yet</strong>Generate a real agent draft, or use the deterministic offline draft to explore the workflow.</div>`}
    </article>
  `;
}

function voiceCard(detail) {
  const voice = detail.voice;
  const aligned = new Set(detail.completed_steps).has("timing");
  const artifact = detail.artifacts.find((item) => item.kind === "audio");
  return `
    <article class="card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">02</span><div><h2>Master voice</h2><p class="card-subtitle">Final narration audio owns every timing decision.</p></div></div>
        <div class="card-actions">
          <button class="button button-quiet button-small" data-upload-voice type="button">Import audio</button>
          <button class="button button-dark button-small" data-action="mock-voice" ${detail.narration && (!voice || voice.source === "mock") ? "" : "disabled"} type="button">Timing track</button>
          <button class="button button-primary button-small" data-action="generate-voice" ${detail.narration ? "" : "disabled"} type="button">Generate voice</button>
          <button class="button button-dark button-small" data-action="align-voice" ${voice && voice.source !== "mock" ? "" : "disabled"} type="button">${aligned ? "Realign" : "Align with Whisper"}</button>
        </div>
      </div>
      ${voice && artifact ? `
        <audio class="audio-player" controls preload="metadata" src="${escapeHtml(artifact.url)}"></audio>
        <div class="voice-meta"><span>${escapeHtml(label(voice.source))} source · ${aligned ? "word-aligned" : "alignment required"}${voice.voice_id ? ` · ${escapeHtml(voice.provider)} / ${escapeHtml(voice.voice_id)}${voice.chunk_count ? ` · ${Number(voice.chunk_count)} batches` : ""}` : ""}</span><strong>${Number(voice.duration_seconds).toFixed(1)} seconds</strong></div>
      ` : `
        <div class="upload-zone"><p>Import your final voice, or create a silent timing track while developing.</p><button class="button button-quiet button-small" data-upload-voice type="button">Choose audio file</button></div>
      `}
    </article>
  `;
}

function directionCard(detail) {
  const director = detail.director;
  const approved = detail.state.approved_director;
  const maxDuration = director?.duration_seconds || 58;
  const aligned = new Set(detail.completed_steps).has("timing");
  const talkingHeadAllowed = state.dashboard?.settings?.include_talking_head !== false;
  return `
    <article class="card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">03</span><div><h2>Director timeline</h2><p class="card-subtitle">Budget-normalized scenes aligned to the voice track.</p></div></div>
        <div class="card-actions">
          ${director && !approved ? `<button class="button button-primary button-small" data-action="approve-director" type="button">Approve plan</button>` : ""}
          <button class="button button-quiet button-small" data-action="direct-mock" ${detail.narration ? "" : "disabled"} type="button">Offline plan</button>
          <button class="button button-dark button-small" data-action="direct" ${detail.narration && aligned ? "" : "disabled"} type="button">${director ? "Regenerate" : "Direct"}</button>
        </div>
      </div>
      ${director ? `
        <div class="timeline">
          ${director.scenes.map((scene) => {
            const width = Math.max(28, Math.round(((scene.end - scene.start) / maxDuration) * 270));
            const presenter = ["talking_head", "cta"].includes(scene.type);
            return `
              <div class="scene" data-type="${escapeHtml(scene.type)}">
                <span class="scene-id">${escapeHtml(scene.scene_id)}</span>
                <span class="scene-bar" style="width:${width}px;max-width:100%" title="${Number(scene.end - scene.start).toFixed(1)} seconds"></span>
                <span class="scene-copy"><strong>${escapeHtml(scene.purpose)}</strong><span>${escapeHtml(label(scene.type))} · ${escapeHtml(scene.renderer)}</span></span>
                <span class="scene-time">${Number(scene.start).toFixed(0)}–${Number(scene.end).toFixed(0)}s ${presenter && talkingHeadAllowed ? `<button class="scene-upload" data-upload-head="${escapeHtml(scene.scene_id)}" type="button">Attach clip</button>` : ""}</span>
              </div>
            `;
          }).join("")}
        </div>
        <div class="timeline-legend"><span><i style="background:var(--coral)"></i>Presenter</span><span><i style="background:var(--mint)"></i>Screen demo</span><span><i style="background:var(--violet)"></i>Graphics</span><span>${director.scenes.length} scenes · ${director.duration_seconds}s</span></div>
        ${director.warnings?.length ? `<ul class="issue-list">${director.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : ""}
      ` : `<div class="empty-card"><strong>No director plan yet</strong>Finish narration first. Voice audio is recommended before direction so timing stays honest.</div>`}
    </article>
  `;
}

function assetsCard(detail) {
  const approved = detail.state.approved_director;
  const prototype = detail.artifacts.find((item) => item.kind === "prototype");
  const graphics = detail.artifacts.find((item) => item.kind === "graphics");
  const media = detail.artifacts.filter((item) => ["audio", "video"].includes(item.kind));
  const graphicsTheme = detail.brief.graphics_theme || "editorial";
  return `
    <article class="card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">04</span><div><h2>Visual assets</h2><p class="card-subtitle">Synthetic demos, presenter clips and deterministic media.</p></div></div>
        <div class="card-actions">
          ${prototype ? `<a class="button button-quiet button-small" href="${escapeHtml(prototype.url)}" target="_blank" rel="noreferrer">Open prototype</a>` : ""}
          ${graphics ? `<a class="button button-quiet button-small" href="${escapeHtml(graphics.url)}" target="_blank" rel="noreferrer">Open graphics</a>` : ""}
          <button class="button button-dark button-small" data-action="record-demos" ${prototype && approved ? "" : "disabled"} type="button">Record demos</button>
          <button class="button button-primary button-small" data-action="generate-graphics" ${approved ? "" : "disabled"} type="button">${graphics ? "Regenerate graphics" : "Generate graphics"}</button>
        </div>
      </div>
      <div class="card-actions" style="justify-content:flex-start;margin-bottom:14px">
        <button class="button button-quiet button-small" data-action="prototype-prompt" ${approved ? "" : "disabled"} type="button">Prepare build brief</button>
        <button class="button button-quiet button-small" data-action="build-prototype" ${approved ? "" : "disabled"} type="button">Build prototype</button>
        <button class="button button-quiet button-small" data-action="repair-prototype" ${prototype && approved ? "" : "disabled"} type="button">Validate & repair</button>
      </div>
      <div class="graphics-theme-control">
        <label for="graphics-theme-select"><span>Graphics theme</span>
          <select id="graphics-theme-select" ${approved ? "" : "disabled"}>
            <option value="editorial" ${graphicsTheme === "editorial" ? "selected" : ""}>Editorial documentary</option>
            <option value="whiteboard" ${graphicsTheme === "whiteboard" ? "selected" : ""}>Whiteboard explainer</option>
          </select>
        </label>
        <p>The selected theme is used consistently across the whole graphics package and is saved when you generate or regenerate.</p>
      </div>
      ${graphics ? `<div class="empty-card"><strong>Graphics package ready</strong>Inspectable scene contracts, individual HTML previews, and a master composition are ready for QA and rendering.</div>` : `<div class="empty-card"><strong>Graphics package not generated</strong>Create the scene outline, choreography, object/action contracts, and inspectable HTML previews before rendering.</div>`}
      ${media.length ? `<div class="asset-list">${media.map((item) => `
        <div class="asset"><div class="asset-info"><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.path)}</span></div><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">Inspect ↗</a></div>
      `).join("")}</div>` : `<div class="empty-card"><strong>No generated media attached</strong>Graphics can fail soft to deterministic scenes. Presenter clips can be attached per scene above.</div>`}
    </article>
  `;
}

function qaCard(detail) {
  const qa = detail.qa;
  const issues = [...(qa?.issues || []), ...(qa?.warnings || [])];
  const finalArtifact = detail.artifacts.find((item) => item.path === "10_final/final.mp4");
  const previewArtifact = detail.artifacts.find((item) => item.path === "10_final/preview.mp4");
  const timelinePreview = detail.artifacts.find((item) => item.kind === "composition");
  const watch = finalArtifact || previewArtifact;
  const approvedDirector = detail.state.approved_director;
  return `
    <article class="card card-dark">
      <div class="card-head">
        <div class="card-title"><span class="section-number">05</span><div><h2>Timeline preview & render</h2><p class="card-subtitle">Play and scrub the complete voice-timed edit before rendering frames.</p></div></div>
        <button class="button button-quiet button-small" data-action="run-qa" ${approvedDirector ? "" : "disabled"} type="button">Run QA</button>
      </div>
      ${qa ? `
        <div class="qa-status ${qa.ok ? "" : "bad"}"><span class="qa-mark">${qa.ok ? "✓" : "!"}</span><div><strong>${qa.ok ? "Production rules pass" : "Action required"}</strong><span>${issues.length} ${issues.length === 1 ? "note" : "notes"} · ${qa.scene_count || detail.director?.scenes?.length || 0} scenes</span></div></div>
        ${issues.length ? `<ul class="issue-list">${issues.map((issue) => `<li>${escapeHtml(issue)}</li>`).join("")}</ul>` : ""}
      ` : `<div class="empty-card"><strong>QA waits for direction approval</strong>The check covers timing budgets, presenter beats and missing scene media.</div>`}
      ${timelinePreview ? `<div class="empty-card"><strong>Interactive timeline ready</strong>Voice, recordings, graphics, captions and exact scene timing are assembled in the browser. This is the fast approval view before MP4 rendering.</div>` : `<div class="empty-card"><strong>Build the timeline preview first</strong>This assembles the complete edit in the browser without rendering an MP4.</div>`}
      <div class="render-actions">
        <button class="button button-primary" data-action="prepare-preview" ${approvedDirector ? "" : "disabled"} type="button">${timelinePreview ? "Refresh timeline preview" : "Build timeline preview"}</button>
        ${timelinePreview ? `<a class="button button-dark" href="${escapeHtml(timelinePreview.url)}" target="_blank" rel="noreferrer">Open timeline preview</a>` : ""}
        <button class="button button-quiet" data-action="render-preview" ${approvedDirector && timelinePreview ? "" : "disabled"} type="button">Render MP4 preview</button>
        <button class="button button-quiet" data-action="render-final" ${approvedDirector && timelinePreview ? "" : "disabled"} type="button">Render final</button>
      </div>
      ${finalArtifact && !detail.state.approved_final ? `<button class="button button-primary" style="width:100%;margin-top:8px" data-action="approve-final" type="button">Approve final video</button>` : ""}
      ${watch ? `<div class="final-preview"><video controls preload="metadata" src="${escapeHtml(watch.url)}"></video></div>` : ""}
    </article>
  `;
}

function briefCard(detail) {
  const brief = detail.brief;
  const durationEditable = detail.state.stage === "input";
  return `
    <article class="card">
      <div class="card-head"><div class="card-title"><span class="section-number">00</span><div><h2>Production brief</h2><p class="card-subtitle">Case facts with synthetic demo data by default.</p></div></div></div>
      <div class="brief-grid">
        <div class="brief-field"><span>Industry</span><p>${escapeHtml(brief.industry)}</p></div>
        <div class="brief-field"><span>Viewer</span><p>${escapeHtml(brief.role)}</p></div>
        <div class="brief-field wide"><span>Target duration</span><div class="duration-editor"><div class="input-suffix"><input id="episode-duration" type="number" min="15" max="480" step="1" value="${Number(brief.target_seconds)}" ${durationEditable ? "" : "disabled"} /><b>sec</b></div><button class="button button-dark button-small" id="save-episode-duration" type="button" ${durationEditable ? "" : "disabled"}>Save duration</button></div><small>${durationEditable ? `Currently ${durationLabel(brief.target_seconds)} · choose 15 seconds to 8 minutes.` : "Archive from Narration before changing the master timeline."}</small></div>
        <div class="brief-field wide"><span>Pain point</span><p>${escapeHtml(brief.pain_point)}</p></div>
        ${brief.backend_summary?.length ? `<div class="brief-field wide"><span>Backend idea</span><ul class="brief-list">${brief.backend_summary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
        ${brief.viewer_diy?.length ? `<div class="brief-field wide"><span>Viewer DIY</span>${brief.suggested_stack ? `<p><strong>Stack:</strong> ${escapeHtml(brief.suggested_stack)}</p>` : ""}<ol class="brief-list">${brief.viewer_diy.map((item) => `<li>${escapeHtml(item.replace(/^\d+\.\s*/, ""))}</li>`).join("")}</ol></div>` : ""}
        ${brief.source_narration ? `<div class="brief-field wide source-field"><span>Supplied narration source</span><p class="source-reference">${escapeHtml(brief.source_reference || "Operator-supplied source")}</p><p class="source-narration">${escapeHtml(brief.source_narration)}</p></div>` : ""}
        <div class="brief-field"><span>Format</span><p>${brief.width} × ${brief.height} · ${brief.fps} fps</p></div>
        <div class="brief-field"><span>Case type</span><p>${escapeHtml(label(brief.case_nature || "synthetic_demo"))}</p></div>
        <div class="brief-field"><span>Demo data policy</span><p>${brief.synthetic_data_only ? "Synthetic data only" : "Operator supplied"}</p></div>
      </div>
    </article>
  `;
}

function projectPolicyCard() {
  const enabled = state.dashboard?.settings?.include_talking_head !== false;
  return `
    <article class="card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">P</span><div><h2>Project visual policy</h2><p class="card-subtitle">One presenter policy shared by every episode in this project.</p></div></div>
        <button class="button button-dark button-small" id="save-project-policy" type="button">Save policy</button>
      </div>
      <div class="brief-grid">
        <label class="brief-field wide"><span>Talking head</span>
          <select id="talking-head-policy">
            <option value="include" ${enabled ? "selected" : ""}>Allowed — Director may use presenter scenes</option>
            <option value="exclude" ${enabled ? "" : "selected"}>Disabled — visual-only videos across the project</option>
          </select>
        </label>
      </div>
      <p class="card-subtitle" style="margin-top:12px">Changing this policy affects every future Director run. Existing conflicting plans must be regenerated before approval or rendering.</p>
    </article>`;
}

function orchestrationCard() {
  const mapping = state.models;
  if (!mapping) return "";
  const taskRows = Object.entries(mapping.tasks).map(([taskId, route]) => {
    const providers = Object.entries(mapping.providers).filter(([, provider]) => provider.capabilities.includes(route.capability));
    const currentProvider = mapping.providers[route.provider] || {};
    const models = currentProvider.models_by_capability?.[route.capability] || currentProvider.models || [route.model];
    const efforts = currentProvider.reasoning_efforts || [];
    const isAudio = route.capability === "audio";
    return `
      <div class="model-row" data-model-task="${escapeHtml(taskId)}">
        <div><strong>${escapeHtml(label(taskId))}</strong><span>${escapeHtml(route.group)} · ${escapeHtml(route.capability)}</span></div>
        <select data-provider-select aria-label="Provider for ${escapeHtml(taskId)}">
          ${providers.map(([providerId, provider]) => `<option value="${escapeHtml(providerId)}" ${providerId === route.provider ? "selected" : ""}>${escapeHtml(provider.label)}</option>`).join("")}
        </select>
        <select data-model-select aria-label="Model for ${escapeHtml(taskId)}">
          ${models.map((model) => `<option value="${escapeHtml(model)}" ${model === route.model ? "selected" : ""}>${escapeHtml(model)}</option>`).join("")}
        </select>
        <select data-reasoning-select aria-label="Reasoning effort for ${escapeHtml(taskId)}" ${efforts.length ? "" : "disabled"}>
          ${(efforts.length ? efforts : ["n/a"]).map((effort) => `<option value="${escapeHtml(effort)}" ${effort === route.reasoning_effort ? "selected" : ""}>${escapeHtml(effort)} reasoning</option>`).join("")}
        </select>
        <select data-voice-select aria-label="Voice for ${escapeHtml(taskId)}" ${isAudio ? "" : "disabled"}>
          ${isAudio
            ? `<option value="${escapeHtml(route.voice_id || "")}" selected>${escapeHtml(route.voice_id || "Choose a voice")}</option>`
            : `<option value="">No voice</option>`}
        </select>
      </div>`;
  }).join("");
  return `
    <article class="card orchestration-card">
      <div class="card-head">
        <div class="card-title"><span class="section-number">AI</span><div><h2>Model orchestration</h2><p class="card-subtitle">Each task is routed only to a compatible provider. TTS model and voice are saved per episode.</p></div></div>
        <button class="button button-dark button-small" id="save-model-map" type="button">Save routing</button>
      </div>
      <div class="model-list">${taskRows}</div>
    </article>`;
}

function promptInspectorCard() {
  const records = state.prompts?.records || [];
  const usage = state.prompts?.usage || {};
  return `
    <article class="card">
      <div class="card-head"><div class="card-title"><span class="section-number">{ }</span><div><h2>Prompt inspector</h2><p class="card-subtitle">Exact prompts, schemas and validated responses retained for every run. ${Number(usage.invocations || 0)} invocations · ~${Number(usage.estimated_input_tokens || 0).toLocaleString()} input tokens.</p></div></div></div>
      ${records.length ? `<div class="prompt-list">${records.map((record) => {
        const invocation = record.invocation;
        return `<details class="prompt-record"><summary><span><strong>${escapeHtml(label(invocation.task))}</strong><small>${escapeHtml(invocation.provider)} · ${escapeHtml(invocation.model)} · ${escapeHtml(invocation.status)}</small></span><b>Inspect</b></summary>
          <div class="prompt-tabs"><h3>Prompt</h3><pre>${escapeHtml(record.prompt || "Not retained")}</pre><h3>Schema</h3><pre>${escapeHtml(record.schema || "Not retained")}</pre><h3>Response</h3><pre>${escapeHtml(record.response || "No response yet")}</pre></div>
        </details>`;
      }).join("")}</div>` : `<div class="empty-card"><strong>No invocations yet</strong>Run a story, narration or director task and the complete request contract appears here.</div>`}
    </article>`;
}

function recoveryCard() {
  return `
    <article class="card recovery-card">
      <div class="card-head"><div class="card-title"><span class="section-number">↺</span><div><h2>Recovery & versions</h2><p class="card-subtitle">Archive a stage and everything downstream, then rebuild without losing previous work.</p></div></div></div>
      <div class="recovery-controls">
        <select id="reset-stage" aria-label="Stage to reset from">
          <option value="render">Render only</option><option value="assets">Assets and render</option><option value="direction">Direction onward</option><option value="voice">Voice onward</option><option value="narration">Narration onward</option>
        </select>
        <button class="button button-danger button-small" id="reset-episode" type="button">Archive & reset</button>
      </div>
    </article>`;
}

function renderWorkspace() {
  const detail = state.detail;
  if (!detail) return;
  $("#loading-view").classList.add("hidden");
  $("#empty-view").classList.add("hidden");
  $("#workspace-view").classList.remove("hidden");
  $("#breadcrumb-title").textContent = detail.brief.title;
  const scenes = detail.director?.scenes?.length || 0;
  const presenterScenes = detail.director?.scenes?.filter((scene) => ["talking_head", "cta"].includes(scene.type)).length || 0;
  const screenScenes = detail.director?.scenes?.filter((scene) => scene.type === "screen_recording").length || 0;
  const duration = detail.voice?.duration_seconds || detail.director?.duration_seconds || detail.brief.target_seconds;
  $("#workspace-view").innerHTML = `
    <div class="workspace-head">
      <div><p class="eyebrow">${escapeHtml(detail.brief.industry)} · ${escapeHtml(detail.brief.role)}</p><h1>${escapeHtml(detail.brief.title)}</h1></div>
      <div class="workspace-head-actions"><span class="episode-code">${escapeHtml(detail.brief.episode_id)}</span><span class="stage-pill">${escapeHtml(label(detail.state.stage))}</span></div>
    </div>
    <section class="progress-panel">
      <div class="progress-summary"><strong>Production progress</strong><span>${detail.summary.progress}% · updated ${shortDate(detail.summary.updated_at)}</span></div>
      <div class="progress-track"><i style="width:${detail.summary.progress}%"></i></div>
      <div class="pipeline-steps">${pipelineHtml(detail)}</div>
    </section>
    <section class="metric-row">
      <div class="metric"><div class="metric-label"><span>Master runtime</span><b>VOICE</b></div><div class="metric-value">${Number(duration).toFixed(1)}s</div><div class="metric-note">Target ${detail.brief.target_seconds}s</div></div>
      <div class="metric"><div class="metric-label"><span>Scene plan</span><b>DIRECTION</b></div><div class="metric-value">${scenes || "—"}</div><div class="metric-note">Budget-normalized moments</div></div>
      <div class="metric"><div class="metric-label"><span>Presenter beats</span><b>POLICY</b></div><div class="metric-value">${state.dashboard?.settings?.include_talking_head === false ? "Off" : (presenterScenes || "—")}</div><div class="metric-note">${state.dashboard?.settings?.include_talking_head === false ? "Visual-only project" : "Hook, insight and close"}</div></div>
      <div class="metric"><div class="metric-label"><span>Screen demos</span><b>PROOF</b></div><div class="metric-value">${screenScenes || "—"}</div><div class="metric-note">Deterministic captures</div></div>
    </section>
    <section class="production-grid">
      <div class="column">${narrationCard(detail)}${directionCard(detail)}${assetsCard(detail)}${promptInspectorCard()}</div>
      <div class="column">${projectPolicyCard()}${briefCard(detail)}${voiceCard(detail)}${qaCard(detail)}${orchestrationCard()}${recoveryCard()}</div>
    </section>
  `;
  bindWorkspaceEvents();
}

function bindWorkspaceEvents() {
  $$("[data-action]", $("#workspace-view")).forEach((button) => {
    button.addEventListener("click", () => startAction(button.dataset.action));
  });
  $$("[data-upload-voice]", $("#workspace-view")).forEach((button) => {
    button.addEventListener("click", () => $("#voice-upload").click());
  });
  $$("[data-upload-head]", $("#workspace-view")).forEach((button) => {
    button.addEventListener("click", () => {
      state.headScene = button.dataset.uploadHead;
      $("#head-upload").click();
    });
  });
  $$("[data-provider-select]", $("#workspace-view")).forEach((select) => {
    select.addEventListener("change", async () => {
      const row = select.closest("[data-model-task]");
      const modelSelect = $("[data-model-select]", row);
      const reasoningSelect = $("[data-reasoning-select]", row);
      const capability = state.models.tasks[row.dataset.modelTask].capability;
      const provider = state.models.providers[select.value] || {};
      const models = provider.models_by_capability?.[capability] || provider.models || [];
      modelSelect.innerHTML = models.map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`).join("");
      const efforts = provider.reasoning_efforts || [];
      reasoningSelect.disabled = !efforts.length;
      reasoningSelect.innerHTML = (efforts.length ? efforts : ["n/a"]).map((effort) => `<option value="${escapeHtml(effort)}">${escapeHtml(effort)} reasoning</option>`).join("");
      if (capability === "audio") {
        await refreshVoiceSelect(row, select.value, provider.default_voice_id || "");
      }
    });
  });
  $$('[data-model-task]', $('#workspace-view')).forEach((row) => {
    const route = state.models.tasks[row.dataset.modelTask];
    if (route?.capability === "audio") refreshVoiceSelect(row, route.provider, route.voice_id || "");
  });
  $("#save-project-policy")?.addEventListener("click", saveProjectPolicy);
  $("#save-episode-duration")?.addEventListener("click", saveEpisodeDuration);
  $("#save-model-map")?.addEventListener("click", saveModelMap);
  $("#reset-episode")?.addEventListener("click", resetEpisode);
}

async function loadVoiceCatalog(providerId) {
  if (!state.models.providers[providerId]?.supports_voice_catalog) return [];
  if (!state.voiceCatalogs[providerId]) {
    state.voiceCatalogs[providerId] = api(`/api/tts/voices/${encodeURIComponent(providerId)}`)
      .then((result) => result.voices || [])
      .catch((error) => ({ error: error.message }));
  }
  return state.voiceCatalogs[providerId];
}

async function refreshVoiceSelect(row, providerId, selectedVoiceId = "") {
  const select = $("[data-voice-select]", row);
  if (!select) return;
  const provider = state.models.providers[providerId] || {};
  if (!provider.supports_voice_catalog) {
    select.disabled = true;
    select.innerHTML = `<option value="">${provider.mode === "manual" ? "External voice" : "Provider-managed voice"}</option>`;
    return;
  }
  select.disabled = true;
  select.innerHTML = `<option value="${escapeHtml(selectedVoiceId)}">Loading voices…</option>`;
  const catalog = await loadVoiceCatalog(providerId);
  if (catalog?.error) {
    select.innerHTML = `<option value="${escapeHtml(selectedVoiceId)}">${escapeHtml(selectedVoiceId || catalog.error)}</option>`;
    select.title = catalog.error;
    select.disabled = !selectedVoiceId;
    return;
  }
  const known = new Set(catalog.map((voice) => voice.voice_id));
  const options = [];
  if (!selectedVoiceId) options.push(`<option value="" selected disabled>Choose a voice</option>`);
  if (selectedVoiceId && !known.has(selectedVoiceId)) {
    options.push(`<option value="${escapeHtml(selectedVoiceId)}" selected>${escapeHtml(selectedVoiceId)} (configured)</option>`);
  }
  options.push(...catalog.map((voice) => {
    const detail = voice.description ? ` — ${voice.description}` : "";
    return `<option value="${escapeHtml(voice.voice_id)}" ${voice.voice_id === selectedVoiceId ? "selected" : ""}>${escapeHtml(voice.name + detail)}</option>`;
  }));
  select.innerHTML = options.join("");
  select.disabled = false;
  select.title = `${catalog.length} voices available`;
}

async function loadDashboard(selectFirst = true) {
  state.dashboard = await api("/api/dashboard");
  renderSidebar();
  renderHealth();
  const episodes = state.dashboard.episodes;
  if (!episodes.length) {
    state.selectedId = null;
    state.detail = null;
    $("#loading-view").classList.add("hidden");
    $("#workspace-view").classList.add("hidden");
    $("#empty-view").classList.remove("hidden");
    $("#breadcrumb-title").textContent = "Overview";
    return;
  }
  if (selectFirst && (!state.selectedId || !episodes.some((item) => item.episode_id === state.selectedId))) {
    state.selectedId = episodes[0].episode_id;
  }
  if (state.selectedId) await loadEpisode(state.selectedId);
}

async function loadEpisode(episodeId) {
  state.selectedId = episodeId;
  renderSidebar();
  try {
    [state.detail, state.models, state.prompts] = await Promise.all([
      api(`/api/episodes/${encodeURIComponent(episodeId)}`),
      api(`/api/episodes/${encodeURIComponent(episodeId)}/models`),
      api(`/api/episodes/${encodeURIComponent(episodeId)}/prompts`),
    ]);
    renderWorkspace();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function selectEpisode(episodeId) {
  $(".sidebar").classList.remove("open");
  showLoading();
  await loadEpisode(episodeId);
}

async function openFilledEpisode(sourceId) {
  const source = state.dashboard?.filled_episodes?.find((episode) => episode.source_id === sourceId);
  if (!source) return;
  $(".sidebar").classList.remove("open");
  showLoading();
  try {
    if (source.imported) {
      await loadEpisode(source.episode_id);
      return;
    }
    const detail = await api(`/api/filled-episodes/${encodeURIComponent(sourceId)}/create`, { method: "POST" });
    state.selectedId = detail.brief.episode_id;
    showToast(`${sourceId} initialized`);
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
    await loadDashboard(false);
  }
}

async function importAllFilledEpisodes() {
  const button = $("#import-filled-episodes");
  button.disabled = true;
  button.textContent = "Adding…";
  try {
    const result = await api("/api/filled-episodes/import", { method: "POST" });
    showToast(`${result.created.length} initialized; ${result.existing.length} already available`);
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Add all";
  }
}

function renderJob(job) {
  state.activeJob = job;
  const tray = $("#job-tray");
  const failed = ["failed", "stopped", "interrupted"].includes(job.status);
  tray.className = `job-tray ${failed ? "failed" : job.status === "succeeded" ? "done" : ""}`;
  tray.innerHTML = `
    <div class="job-row">
      <span class="job-spinner">${job.status === "succeeded" ? "✓" : ""}</span>
      <div class="job-copy"><strong>${escapeHtml(job.label)}</strong><span>${escapeHtml(job.message)}</span></div>
      <span class="job-capability">${escapeHtml(job.capability)}</span>
    </div>
    <div class="job-progress"><i style="width:${Number(job.progress || 0)}%"></i></div>
    <div class="job-foot"><span>${Math.round(Number(job.progress || 0))}% · ${escapeHtml(label(job.status))}</span>${["queued", "running"].includes(job.status) ? `<button class="terminate-job-button" id="stop-job" type="button">Terminate job</button>` : ""}</div>
    ${state.logs.length ? `<pre class="job-log">${escapeHtml(state.logs.slice(-8).map(formatJobLog).join("\n"))}</pre>` : ""}
  `;
  $("#stop-job")?.addEventListener("click", () => stopJob(job.job_id));
  $("#worker-status").className = `worker-status ${["queued", "running"].includes(job.status) ? "busy" : job.status === "failed" ? "failed" : ""}`;
  $("#worker-status span").textContent = ["queued", "running"].includes(job.status) ? "Worker busy" : "Worker ready";
}

function formatJobLog(line) {
  const value = String(line || "");
  if (!value.startsWith("SVF_PROGRESS ")) return value;
  try {
    const progress = JSON.parse(value.slice("SVF_PROGRESS ".length));
    return `${Math.round(Number(progress.percent || 0))}%  ${progress.message || "Working"}`;
  } catch {
    return value;
  }
}

async function stopJob(jobId) {
  if (!confirm("Terminate this production job? Completed chunks and artifacts will be preserved.")) return;
  const button = $("#stop-job");
  if (button) {
    button.disabled = true;
    button.textContent = "Terminating…";
  }
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}/stop`, { method: "POST" });
    renderJob(job);
    showToast(job.message);
  } catch (error) {
    showToast(error.message, true);
    if (button) {
      button.disabled = false;
      button.textContent = "Terminate job";
    }
  }
}

async function startAction(action) {
  if (!state.selectedId || state.activeJob && ["queued", "running"].includes(state.activeJob.status)) {
    showToast("A production job is already running.", true);
    return;
  }
  let body = {};
  if (action === "mock-voice") body.seconds = state.detail?.brief?.target_seconds || 58;
  try {
    if (action === "generate-graphics") {
      const selectedTheme = $("#graphics-theme-select")?.value || "editorial";
      if (selectedTheme !== state.detail?.brief?.graphics_theme) {
        state.detail = await api(`/api/episodes/${encodeURIComponent(state.selectedId)}/graphics-theme`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ graphics_theme: selectedTheme }),
        });
      }
    }
    const job = await api(`/api/episodes/${encodeURIComponent(state.selectedId)}/actions/${encodeURIComponent(action)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    renderJob(job);
    pollJob(job.job_id);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function pollJob(jobId) {
  try {
    const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    const logs = await api(`/api/jobs/${encodeURIComponent(jobId)}/logs?limit=40`)
      .catch(() => ({ lines: [job.message] }));
    state.logs = logs.lines || [];
    renderJob(job);
    if (["queued", "running"].includes(job.status)) {
      setTimeout(() => pollJob(jobId), 1100);
      return;
    }
    if (job.status === "succeeded") {
      showToast(job.message);
      await loadDashboard(false);
      setTimeout(() => $("#job-tray").classList.add("hidden"), 3200);
    } else {
      showToast(job.message, true);
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

async function resumeRunningJob() {
  const jobs = await api("/api/jobs");
  const running = jobs.find((job) => ["queued", "running"].includes(job.status));
  if (!running) return;
  state.selectedId = running.episode_id;
  if (!state.detail || state.detail.brief.episode_id !== running.episode_id) {
    await loadEpisode(running.episode_id);
  }
  renderJob(running);
  pollJob(running.job_id);
}

async function uploadFile(kind, file) {
  if (!file || !state.selectedId) return;
  const form = new FormData();
  form.append("file", file);
  const path = kind === "voice"
    ? `/api/episodes/${encodeURIComponent(state.selectedId)}/voice`
    : `/api/episodes/${encodeURIComponent(state.selectedId)}/talking-head/${encodeURIComponent(state.headScene)}`;
  try {
    $("#worker-status").className = "worker-status busy";
    $("#worker-status span").textContent = "Importing media";
    const result = await api(path, { method: "POST", body: form });
    showToast(result.message);
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    $("#worker-status").className = "worker-status";
    $("#worker-status span").textContent = "Worker ready";
  }
}

async function saveProjectPolicy() {
  const includeTalkingHead = $("#talking-head-policy")?.value !== "exclude";
  try {
    const settings = await api("/api/project/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ include_talking_head: includeTalkingHead }),
    });
    state.dashboard.settings = settings;
    showToast(includeTalkingHead
      ? "Talking head is now allowed project-wide"
      : "Talking head disabled project-wide; regenerate conflicting Director plans");
    renderWorkspace();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function saveEpisodeDuration() {
  const input = $("#episode-duration");
  const targetSeconds = Number(input?.value);
  if (!Number.isFinite(targetSeconds) || targetSeconds < 15 || targetSeconds > 480) {
    showToast("Choose a duration between 15 and 480 seconds.", true);
    input?.focus();
    return;
  }
  const button = $("#save-episode-duration");
  button.disabled = true;
  button.textContent = "Saving…";
  try {
    state.detail = await api(`/api/episodes/${encodeURIComponent(state.selectedId)}/duration`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_seconds: targetSeconds }),
    });
    showToast(`Target duration set to ${durationLabel(targetSeconds)}`);
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
    button.disabled = false;
    button.textContent = "Save duration";
  }
}

async function saveModelMap() {
  const tasks = {};
  $$("[data-model-task]", $("#workspace-view")).forEach((row) => {
    const reasoning = $("[data-reasoning-select]", row);
    tasks[row.dataset.modelTask] = {
      provider: $("[data-provider-select]", row).value,
      model: $("[data-model-select]", row).value,
      ...(reasoning && !reasoning.disabled ? { reasoning_effort: reasoning.value } : {}),
      ...($("[data-voice-select]", row) && !$("[data-voice-select]", row).disabled && $("[data-voice-select]", row).value
        ? { voice_id: $("[data-voice-select]", row).value } : {}),
    };
  });
  try {
    state.models = await api(`/api/episodes/${encodeURIComponent(state.selectedId)}/models`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tasks }),
    });
    showToast("Episode model routing saved");
    renderWorkspace();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function resetEpisode() {
  const fromStage = $("#reset-stage")?.value;
  if (!fromStage || !confirm(`Archive ${label(fromStage)} and every downstream stage? Existing files remain recoverable.`)) return;
  try {
    const result = await api(`/api/episodes/${encodeURIComponent(state.selectedId)}/reset`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_stage: fromStage, confirm: true }),
    });
    showToast(result.message);
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
  }
}

async function createEpisode() {
  const form = $("#create-form");
  if (!form.reportValidity()) return;
  const data = new FormData(form);
  const payload = Object.fromEntries(data.entries());
  payload.target_seconds = Number(payload.target_seconds || 58);
  payload.backend_summary = String(payload.backend_summary || "").split("\n").map((line) => line.trim()).filter(Boolean);
  payload.viewer_diy = String(payload.viewer_diy || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const submit = $("#create-submit");
  submit.disabled = true;
  submit.textContent = "Creating…";
  try {
    const detail = await api("/api/episodes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.selectedId = detail.brief.episode_id;
    $("#create-dialog").close();
    form.reset();
    showToast("Production created");
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
    submit.textContent = "Create production";
  }
}

async function openReferenceDemo() {
  try {
    const detail = await api("/api/episodes/reference-demo", { method: "POST" });
    state.selectedId = detail.brief.episode_id;
    await loadDashboard(false);
  } catch (error) {
    showToast(error.message, true);
  }
}

function openCreateDialog() {
  $("#create-dialog").showModal();
  setTimeout(() => $("#create-form input[name=episode_id]").focus(), 0);
}

$("#new-episode-button").addEventListener("click", openCreateDialog);
$("#filled-episode-search").addEventListener("input", (event) => {
  state.filledQuery = event.target.value;
  renderSidebar();
});
$("#import-filled-episodes").addEventListener("click", importAllFilledEpisodes);
$$('[data-open-create]').forEach((button) => button.addEventListener("click", openCreateDialog));
$("#create-submit").addEventListener("click", createEpisode);
$("#reference-demo-button").addEventListener("click", openReferenceDemo);
$("#refresh-button").addEventListener("click", () => loadDashboard(false).catch((error) => showToast(error.message, true)));
$("#health-button").addEventListener("click", () => $("#health-dialog").showModal());
$("#health-close").addEventListener("click", () => $("#health-dialog").close());
$("#mobile-menu").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
$("#voice-upload").addEventListener("change", (event) => {
  uploadFile("voice", event.target.files[0]);
  event.target.value = "";
});
$("#head-upload").addEventListener("change", (event) => {
  uploadFile("head", event.target.files[0]);
  event.target.value = "";
});

showLoading();
loadDashboard().then(resumeRunningJob).catch((error) => {
  $("#loading-view").classList.add("hidden");
  $("#empty-view").classList.remove("hidden");
  showToast(error.message, true);
});

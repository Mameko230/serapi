// Serapi Web Workspace v2 — synthetic prototype data, no network.
let segments = [];
let contextLines = [];
let qaIssues = [];
let hits = [];
let projectInfo = {};
let workspaceSource = "synthetic";

const statusLabels = {
  confirmed: "已确认", edited: "编辑", reviewer1: "R1", reviewer2: "R2",
  rejected: "拒绝", untranslated: "未译", draft: "草稿"
};
const statusClass = { confirmed: "confirmed", edited: "edited", reviewer1: "r1", reviewer2: "r2", rejected: "rejected", untranslated: "untranslated", draft: "edited" };

function applySnapshot(snapshot) {
  if (!snapshot || !Array.isArray(snapshot.segments) || !snapshot.segments.length) return false;
  segments = snapshot.segments;
  contextLines = Array.isArray(snapshot.contextLines) ? snapshot.contextLines : [];
  qaIssues = Array.isArray(snapshot.qa) ? snapshot.qa : [];
  hits = Array.isArray(snapshot.hits) ? snapshot.hits : [];
  projectInfo = snapshot.project || {};
  workspaceSource = snapshot.source || (snapshot.synthetic ? "synthetic" : "engine-listRows");
  state.current = Math.max(0, Math.min(segments.length - 1, Number(snapshot.current) || 0));
  state.currentLine = Math.max(0, Number(snapshot.currentLine) || 0);
  state.selectedHit = 0;
  if (projectInfo.name) document.querySelector(".crumb-project").textContent = projectInfo.name;
  if ("file" in projectInfo) document.querySelector(".crumb-file").textContent = projectInfo.file || "—";
  if ("languages" in projectInfo) document.querySelector(".lang").textContent = projectInfo.languages || "—";
  if (projectInfo.progress) {
    const p = projectInfo.progress;
    $("#progressText").textContent = `${Number(p.done || 0).toLocaleString()} / ${Number(p.total || 0).toLocaleString()}`;
    const bar = document.querySelector(".mini-progress i");
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, Number(p.percent) || 0))}%`;
    document.querySelector("#statusProgress").textContent =
      `${Number(p.done || 0).toLocaleString()} / ${Number(p.total || 0).toLocaleString()} · ${Number(p.percent || 0).toFixed(1)}%`;
  } else {
    document.querySelector("#statusProgress").textContent = "—";
  }
  document.querySelector("#contextPanel").hidden = contextLines.length === 0;
  const dictionary = snapshot.dictionary || null;
  document.querySelector("#dictSection").hidden = !dictionary;
  if (dictionary) {
    document.querySelector("#dictTerm").textContent = dictionary.term || "";
    document.querySelector("#dictReading").textContent = dictionary.reading || "";
    document.querySelector("#dictMeaning").textContent = dictionary.meaning || "";
    document.querySelector(".dict-source").textContent = dictionary.source || "个人库";
  }
  return true;
}

async function loadEngineSnapshot() {
  const host = window.serapiHost;
  if (!host || !host.invokeEngineApi || !host.sidecar) return false;
  // The engine page may still be loading when the workspace boots. Retry
  // briefly before falling back to the synthetic snapshot.
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const listed = await host.invokeEngineApi("listRows", []);
      if (listed && listed.ok && listed.value && listed.value.ok) {
        const rows = listed.value.rows;
        if (Array.isArray(rows) && rows.length) {
          const normalized = await host.sidecar.call("workspace.normalize", {
            rows,
            project: { name: "memoQ", file: "", languages: "", progress: null },
          });
          if (normalized && normalized.ok && normalized.result) {
            return applySnapshot(normalized.result);
          }
        }
      }
    } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 180));
  }
  return false;
}

async function loadSyntheticSnapshot() {
  if (!window.serapiHost || !window.serapiHost.sidecar) return false;
  try {
    const reply = await window.serapiHost.sidecar.call("workspace.snapshot", {});
    if (!reply || !reply.ok || !reply.result) return false;
    return applySnapshot(reply.result);
  } catch (_) {
    return false;
  }
}

async function loadWorkspaceSnapshot() {
  if (await loadEngineSnapshot()) return true;
  return loadSyntheticSnapshot();
}

const state = { current: 2, currentLine: 3, filter: "all", hitFilter: "all", selectedHit: 0, contextCollapsed: false };
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function visibleSegments() {
  if (state.filter === "all") return segments;
  if (state.filter === "attention") return segments.filter((s) => s.qa > 0);
  if (state.filter === "review") return segments.filter((s) => ["reviewer1", "reviewer2"].includes(s.status));
  if (state.filter === "done") return segments.filter((s) => ["confirmed", "reviewer1", "reviewer2"].includes(s.status));
  return segments;
}

function renderSegmentList() {
  $("#segList").innerHTML = visibleSegments().map((s) => {
    const active = segments[state.current].no === s.no;
    const rate = s.rate === null ? "—" : s.rate + "%";
    const qa = s.qa ? `<span class="seg-qas">● ${s.qa}</span>` : "";
    return `<div class="seg ${active ? "active" : ""}" data-no="${s.no}" data-status="${s.status}">
      <div class="seg-no">${s.no}</div><div class="seg-indicator"></div>
      <div class="seg-txt"><div class="seg-src">${esc(s.src)}</div><div class="seg-tgt">${esc(s.tgt)}</div>
        <div class="seg-meta"><span class="badge ${statusClass[s.status]}">${statusLabels[s.status]}</span>${qa}<span class="seg-rate">${rate}</span></div>
      </div></div>`;
  }).join("");
  $("#segCount").textContent = visibleSegments().length;
  $$("#segList .seg").forEach((el) => el.addEventListener("click", () => selectSegment(Number(el.dataset.no))));
}

function renderContext() {
  const seg = segments[state.current];
  $("#ctxSpeaker").textContent = seg.speaker || "—";
  $("#contextTrack").innerHTML = contextLines.map(([label, text], i) => `<div class="ctx-item ${i === 2 ? "current" : ""}">
    <div class="ctx-no">${i === 2 ? '<span class="ctx-current-mark"></span>' : ""}${label}</div>
    <div class="ctx-src">${esc(text)}</div></div>`).join("");
}

function codeRows(seg, qaLine = -1) {
  const count = Math.max(seg.srcLines.length, seg.tgtLines.length);
  const rows = [];
  for (let i = 0; i < count; i++) {
    const classes = ["code-row"];
    if (i === state.currentLine) classes.push("current");
    if (i === qaLine) classes.push("qa-row");
    const src = seg.srcLines[i] === undefined ? "" : seg.srcLines[i];
    const tgt = seg.tgtLines[i] === undefined ? "" : seg.tgtLines[i];
    rows.push(`<div class="${classes.join(" ")}" data-line="${i}">
      <div class="line-no">${String(i + 1).padStart(2, "0")}</div>
      <div class="line-text source-text">${esc(src)}</div>
      <div class="row-divider"></div>
      <div class="line-no">${String(i + 1).padStart(2, "0")}</div>
      <div class="line-text target-text" contenteditable="true" spellcheck="false">${esc(tgt)}</div>
    </div>`);
  }
  return rows.join("");
}

function renderEditor(seg) {
  $("#editorRow").textContent = "第 " + seg.no + " 段";
  $("#editorKey").textContent = seg.key;
  const srcChars = (seg.src || "").length;
  const tgtChars = (seg.tgt || "").length;
  $("#editorStat").textContent = `${seg.srcLines.length} 行 · ${srcChars} / ${tgtChars} 字`;
  $("#codePane").innerHTML = codeRows(seg, qaIssues[0] ? qaIssues[0].line : -1);
  const qaLine = qaIssues.find((q) => q.severity === "error");
  if (qaLine) {
    const row = $("#codePane").querySelector(`.code-row[data-line="${qaLine.line}"]`);
    const text = row && row.querySelector(".target-text");
    if (text && text.textContent.includes(qaLine.match)) {
      text.innerHTML = esc(text.textContent).replace(qaLine.match, `<span class="qa-mark">${qaLine.match}</span>`);
    }
  }
  $$("#codePane .target-text").forEach((el) => el.addEventListener("input", () => {
    $("#statusNote").textContent = "草稿 · 有未保存修改";
    $("#targetState").textContent = "草稿";
  }));
  $$("#codePane .code-row").forEach((row) => {
    row.addEventListener("click", () => {
      state.currentLine = Number(row.dataset.line);
      $$("#codePane .code-row.current").forEach((r) => r.classList.remove("current"));
      row.classList.add("current");
    });
  });
  $("#targetState").textContent = statusLabels[seg.status];
  $("#infoSpeaker").textContent = seg.speaker || "—";
  $("#infoContext").textContent = seg.contextId || "—";
  $("#infoComments").textContent = Number.isFinite(seg.comments) ? seg.comments : "—";
  $("#infoLocked").textContent = seg.locked ? "是" : "—";
  document.querySelector("#statusCurrent").textContent =
    `${seg.no} / ${segments.length ? segments[segments.length - 1].no : seg.no}`;
  document.querySelector("#railId").textContent = "#" + seg.no;
}

function renderQA() {
  const errors = qaIssues.filter((q) => q.severity === "error").length;
  const warnings = qaIssues.filter((q) => q.severity === "warn").length;
  $("#qaCount").textContent = qaIssues.length;
  const severity = $("#qaSeverity");
  severity.innerHTML = qaIssues.length
    ? `${errors ? '<i class="dot error"></i>' + errors + " 错误 " : ""}${warnings ? '<i class="dot warn"></i>' + warnings + " 警告" : ""}`
    : "无问题";
  $("#qaList").innerHTML = qaIssues.length ? qaIssues.map((q, i) => `<div class="qa-item ${q.severity}" data-index="${i}" tabindex="0">
    <div class="qa-icon">!</div><div class="qa-line">${q.line + 1}</div>
    <div><div class="qa-rule">${q.rule}</div><div class="qa-msg">${esc(q.msg)}</div></div></div>`).join("") : '<div class="rail-empty">当前段没有质量问题</div>';
  $$("#qaList .qa-item").forEach((el) => {
    el.addEventListener("click", () => focusQA(Number(el.dataset.index)));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusQA(Number(el.dataset.index)); } });
  });
}

function visibleHits() { return state.hitFilter === "all" ? hits : hits.filter((h) => h.type === state.hitFilter); }

function renderHits() {
  const list = visibleHits();
  $("#hitCount").textContent = list.length;
  $("#hitList").innerHTML = list.length ? list.map((h, i) => {
    const idx = hits.indexOf(h);
    return `<div class="hit ${idx === state.selectedHit ? "selected" : ""}" data-index="${idx}" tabindex="0">
      <div class="hit-rate ${h.type === "TB" ? "tb" : ""}">${h.type === "TB" ? "TB" : h.rate}</div>
      <div><div class="hit-src">${esc(h.src)}</div><div class="hit-tgt">${esc(h.tgt)}</div></div></div>`;
  }).join("") : '<div class="rail-empty">当前段没有记忆或术语命中</div>';
  $$("#hitList .hit").forEach((el) => {
    const choose = () => selectHit(Number(el.dataset.index));
    el.addEventListener("click", choose);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(); } });
  });
  renderHitDetail();
}

function selectHit(index) {
  state.selectedHit = index;
  renderHits();
}
function renderHitDetail() {
  const h = hits[state.selectedHit];
  if (!h) { $("#hitDetail").innerHTML = ""; return; }
  $("#hitDetail").innerHTML = `<div class="detail-title"><span class="detail-rate">${h.type === "TB" ? "TB" : h.rate}</span><span>${h.type === "TB" ? "术语库命中" : "TM 命中"}</span></div>
    <div class="detail-meta">${esc(h.meta)}</div>
    <div class="detail-segments"><div><span>原文</span><p>${esc(h.src)}</p></div><div><span>译文</span><p>${esc(h.tgt)}</p></div></div>
    <div class="detail-actions"><b>双击插入</b><span>·</span><span>Ctrl+数字快捷插入</span></div>`;
}

function focusQA(index) {
  const q = qaIssues[index]; if (!q) return;
  const row = $("#codePane").querySelector(`.code-row[data-line="${q.line}"]`);
  if (row) {
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    const text = row.querySelector(".target-text");
    if (text) {
      text.innerHTML = esc(text.textContent).replace(q.match, `<span class="qa-mark">${q.match}</span>`);
      text.querySelector(".qa-mark")?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }
  $("#statusNote").textContent = `QA · ${q.rule} · 第 ${segments[state.current].no} 段`;
}

async function loadSegmentDetail(index) {
  if (workspaceSource !== "engine-listRows") return;
  const host = window.serapiHost;
  const seg = segments[index];
  if (!host || !host.invokeEngineApi || !host.sidecar || !seg || seg._detailLoaded) return;
  seg._detailLoaded = true;
  try {
    const raw = await host.invokeEngineApi("readSegment", [seg.key]);
    if (!raw || !raw.ok || !raw.value) return;
    const normalized = await host.sidecar.call("workspace.normalize_segment", { segment: raw.value });
    if (!normalized || !normalized.ok || !normalized.result || !normalized.result.ok) return;
    Object.assign(seg, normalized.result.segment);
    if (segments[state.current] !== seg) return;
    renderSegmentList();
    renderEditor(seg);
    $("#statusNote").textContent = `第 ${seg.no} 段 · 已载入译文`;
  } catch (_) {
    seg._detailLoaded = false;
  }
}

function selectSegment(no) {
  const idx = segments.findIndex((s) => s.no === no); if (idx < 0) return;
  state.current = idx;
  renderSegmentList(); renderContext(); renderEditor(segments[idx]);
  $("#statusNote").textContent = `第 ${segments[idx].no} 段 · ${statusLabels[segments[idx].status]}`;
  document.querySelector(`#segList .seg[data-no="${no}"]`)?.scrollIntoView({ block: "nearest" });
  loadSegmentDetail(idx);
}

$$("#filters .filter").forEach((btn) => btn.addEventListener("click", () => {
  $$("#filters .filter").forEach((b) => b.classList.toggle("active", b === btn));
  state.filter = btn.dataset.filter; renderSegmentList();
}));
$$("#hitFilters .mini-filter").forEach((btn) => btn.addEventListener("click", () => {
  $$("#hitFilters .mini-filter").forEach((b) => b.classList.toggle("active", b === btn));
  state.hitFilter = btn.dataset.type; renderHits();
}));
$("#ctxToggle").addEventListener("click", () => {
  state.contextCollapsed = !state.contextCollapsed;
  $("#contextPanel").classList.toggle("collapsed", state.contextCollapsed);
  $("#ctxToggle").textContent = state.contextCollapsed ? "展开" : "收起";
});
$("#themeToggle").addEventListener("click", () => document.body.classList.toggle("dark"));
$("#moreBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  const open = $("#moreMenu").classList.toggle("open");
  $("#moreBtn").setAttribute("aria-expanded", String(open));
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#moreMenu") && !e.target.closest("#moreBtn")) $("#moreMenu").classList.remove("open");
});
$$("[data-action]").forEach((el) => el.addEventListener("click", () => {
  if (el.dataset.action === "引擎" && window.serapiHost) {
    window.serapiHost.showEngine();
    toast("切换到 memoQ Engine WebView");
  } else if (el.dataset.action === "账号" && window.serapiHost) {
    const welcome = document.querySelector("#welcome");
    if (welcome) welcome.hidden = false;
  } else {
    toast(`${el.dataset.action} · 原型入口`);
  }
  $("#moreMenu").classList.remove("open");
}));
$("#openDict").addEventListener("click", () => toast("打开完整词典浮层 · 原型入口"));
$("#commandBtn").addEventListener("click", () => toast("命令面板 · 原型入口"));

function toast(text) {
  const el = $("#toast"); el.textContent = text; el.classList.add("show");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), 1800);
}

$("#segList").addEventListener("keydown", (e) => {
  if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
  e.preventDefault();
  const next = Math.max(0, Math.min(segments.length - 1, state.current + (e.key === "ArrowDown" ? 1 : -1)));
  selectSegment(segments[next].no);
});

/* column splitter: one handle, CSS variables, persisted ratio */
const split = { value: 40 };
try { const saved = Number(localStorage.getItem("serapi:split")); if (saved >= 28 && saved <= 65) split.value = saved; } catch (_) {}

function applySplit(value) {
  split.value = Math.max(28, Math.min(65, value));
  const body = document.querySelector(".editor-body");
  if (body) {
    body.style.setProperty("--src-fr", split.value + "fr");
    body.style.setProperty("--tgt-fr", (100 - split.value) + "fr");
  }
  requestAnimationFrame(updateSplitHandle);
}
function updateSplitHandle() {
  const handle = document.querySelector("#colResizer");
  const pane = document.querySelector("#codePane");
  const first = pane && pane.querySelector(".code-row");
  if (!handle || !first) return;
  const body = document.querySelector(".editor-body");
  const bodyRect = body.getBoundingClientRect();
  const source = first.querySelector(".source-text");
  if (!source) return;
  handle.style.left = (source.getBoundingClientRect().right - bodyRect.left + 3) + "px";
}
function initSplitter() {
  const handle = document.querySelector("#colResizer");
  const body = document.querySelector(".editor-body");
  if (!handle || !body) return;
  applySplit(split.value);

  let dragging = false;
  const onMove = (e) => {
    if (!dragging) return;
    const pane = document.querySelector("#codePane");
    const first = pane && pane.querySelector(".code-row");
    if (!first) return;
    const bodyRect = body.getBoundingClientRect();
    const source = first.querySelector(".source-text");
    if (!source) return;
    const left = bodyRect.left + 30 + 7;
    const right = bodyRect.right - 16 - 30 - 7;
    const pct = ((e.clientX - left) / Math.max(1, right - left)) * 100;
    applySplit(pct);
  };
  const stop = () => {
    dragging = false;
    handle.classList.remove("dragging");
    try { localStorage.setItem("serapi:split", String(Math.round(split.value))); } catch (_) {}
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", stop);
  };
  handle.addEventListener("pointerdown", (e) => {
    dragging = true;
    handle.classList.add("dragging");
    handle.setPointerCapture?.(e.pointerId);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", stop);
  });
  handle.addEventListener("dblclick", () => applySplit(40));
  handle.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    applySplit(split.value + (e.key === "ArrowLeft" ? -2 : 2));
    try { localStorage.setItem("serapi:split", String(Math.round(split.value))); } catch (_) {}
  });
  window.addEventListener("resize", updateSplitHandle);
  updateSplitHandle();
}

/* Web welcome / account surface (step 4 skeleton). */
async function initWelcome() {
  const el = document.querySelector("#welcome");
  const host = window.serapiHost;
  if (!el) return;
  if (!host || !host.sidecar) return;
  let config = null;
  try {
    const reply = await host.sidecar.call("config.get", {});
    config = reply && reply.ok ? reply.result : null;
  } catch (_) {}
  const query = new URLSearchParams(location.search);
  if (query.has("workspace")) return;
  const force = query.has("welcome") || location.hash === "#welcome";
  if (!force && config && config.memoq_url) return;
  const input = document.querySelector("#serverInput");
  const history = document.querySelector("#serverHistory");
  if (config && config.memoq_url) input.value = config.memoq_url;
  if (config && Array.isArray(config.server_history)) {
    const names = config.server_names || {};
    history.innerHTML = config.server_history.filter(Boolean).slice(0, 4).map((url) => {
      const name = names[url] || "";
      let label = name || url;
      try { label = name || new URL(url).host; } catch (_) {}
      return `<button class="quick-server" data-url="${esc(url)}" title="${esc(url)}">${esc(label)}</button>`;
    }).join("");
    history.querySelectorAll(".quick-server").forEach((btn) => {
      btn.addEventListener("click", () => { input.value = btn.dataset.url; input.focus(); });
    });
  }
  el.hidden = false;
  input.focus();
  input.select();

  const error = document.querySelector("#welcomeError");
  const connect = async () => {
    const raw = String(input.value || "").trim();
    if (!/^https?:\/\/[^\s]+$/i.test(raw)) {
      error.textContent = "请输入完整的 http(s) 服务器地址。";
      input.focus();
      return;
    }
    error.textContent = "";
    const btn = document.querySelector("#connectBtn");
    btn.disabled = true;
    btn.textContent = "连接中…";
    try {
      const saved = await host.sidecar.call("config.remember_server", { url: raw });
      if (!saved || !saved.ok || !saved.result || !saved.result.ok) {
        error.textContent = "服务器地址保存失败，请检查配置权限。";
        return;
      }
      const loaded = await host.loadEngine(raw);
      if (!loaded || !loaded.ok) {
        error.textContent = "无法打开 memoQ： " + ((loaded && loaded.error) || "unknown");
        return;
      }
      el.hidden = true;
      toast("memoQ 登录页已打开；登录完成后按 Ctrl+Shift+W 返回工作区");
    } catch (err) {
      error.textContent = "连接失败： " + String(err && err.message || err);
    } finally {
      btn.disabled = false;
      btn.textContent = "连接";
    }
  };
  document.querySelector("#connectBtn").addEventListener("click", connect);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
  document.querySelector("#demoBtn").addEventListener("click", () => { el.hidden = true; });
}

if (location.hash === "#dark") document.body.classList.add("dark");

async function bootWorkspace() {
  await loadWorkspaceSnapshot();
  if (!segments.length) {
    $("#segList").innerHTML = '<div class="empty-workspace">未收到工作区数据<br><span>请检查 Python sidecar</span></div>';
    return;
  }
  renderSegmentList();
  renderContext();
  renderEditor(segments[state.current]);
  renderQA();
  renderHits();
  initSplitter();
  initWelcome();
  loadSegmentDetail(state.current);
}
bootWorkspace();

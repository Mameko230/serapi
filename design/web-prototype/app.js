// Serapi Web Workspace v2 — synthetic prototype data, no network.
const segments = [
  { no: 1, key: "ev_0010_guard", speaker: "衛兵", status: "confirmed", rate: 100, qa: 0,
    src: "装備画面を開きます。", tgt: "打开装备界面。",
    srcLines: ["装備画面を開きます。"], tgtLines: ["打开装备界面。"] },
  { no: 2, key: "ev_0020_guard", speaker: "旅人", status: "edited", rate: 96, qa: 1,
    src: "よし、行くぞ！", tgt: "好，出发吧！",
    srcLines: ["よし、行くぞ！"], tgtLines: ["好，出发吧！"] },
  { no: 3, key: "ev_0030_alice", speaker: "アリス", status: "reviewer1", rate: 88, qa: 3,
    src: "アリスは Ancient Ruins の入口に立ち、古い石扉に刻まれた紋章を見つめた。",
    tgt: "爱丽丝站在 Ancient Ruins 的入口，凝视着刻在古老石门上的纹章。",
    srcLines: [
      "アリスは Ancient Ruins の入口に立ち、",
      "古い石扉に刻まれた紋章を見つめた。",
      "「この封印は、まだ生きている……」",
      "風が吹くたび、青白い光が",
      "紋章の縁をゆっくりと伝っていく。",
      "「本当に開けるつもりか？」",
      "後ろからロウが低い声で尋ねた。",
      "「開けなければ、先へは進めない」",
      "アリスは短く答え、",
      "指先を石扉に触れさせる。",
      "その瞬間、空気が震え、",
      "遠くで何かが目を覚ました。"
    ],
    tgtLines: [
      "爱丽丝站在 Ancient Ruins 的入口，",
      "凝视着刻在古老石门上的纹章。",
      "“这道封印，还活着……”",
      "每当风吹过，苍白的微光",
      "便沿着纹章边缘缓缓游走。",
      "“真的打算打开它吗？”",
      "罗从身后低声问道。",
      "“不开的话，就无法继续前进。”",
      "爱丽丝简短地回答，",
      "将指尖触上石门。",
      "那一瞬间，空气震动，",
      "远处有什么东西醒了过来。"
    ] },
  { no: 4, key: "ev_0040_item", speaker: "アリス", status: "reviewer2", rate: 91, qa: 1,
    src: "回復薬を3つ使いますか？", tgt: "要使用 3 个恢复药吗？",
    srcLines: ["回復薬を3つ使いますか？"], tgtLines: ["要使用 3 个恢复药吗？"] },
  { no: 5, key: "ev_0050_save", speaker: "システム", status: "untranslated", rate: null, qa: 0,
    src: "セーブデータを上書きします。", tgt: "将覆盖存档数据。",
    srcLines: ["セーブデータを上書きします。"], tgtLines: ["将覆盖存档数据。"] },
  { no: 6, key: "ev_0060_warn", speaker: "ナレーション", status: "edited", rate: 73, qa: 0,
    src: "この先は危険です。", tgt: "前方危险。",
    srcLines: ["この先は危険です。"], tgtLines: ["前方危险。"] },
  { no: 7, key: "ev_0070_town", speaker: "ナレーション", status: "confirmed", rate: 100, qa: 0,
    src: "町へ戻りましょう。", tgt: "回城吧。",
    srcLines: ["町へ戻りましょう。"], tgtLines: ["回城吧。"] },
  { no: 8, key: "ev_0080_level", speaker: "システム", status: "draft", rate: 68, qa: 1,
    src: "レベルが上がりました！", tgt: "等级提升了！",
    srcLines: ["レベルが上がりました！"], tgtLines: ["等级提升了！"] },
  { no: 9, key: "ev_0090_menu", speaker: "システム", status: "edited", rate: 84, qa: 0,
    src: "設定画面に移動します。", tgt: "前往设置画面。",
    srcLines: ["設定画面に移動します。"], tgtLines: ["前往设置画面。"] },
  { no: 10, key: "ev_0100_continue", speaker: "システム", status: "rejected", rate: 77, qa: 0,
    src: "コンティニューしますか？", tgt: "要继续吗？",
    srcLines: ["コンティニューしますか？"], tgtLines: ["要继续吗？"] }
];

const statusLabels = {
  confirmed: "已确认", edited: "编辑", reviewer1: "R1", reviewer2: "R2",
  rejected: "拒绝", untranslated: "未译", draft: "草稿"
};
const statusClass = { confirmed: "confirmed", edited: "edited", reviewer1: "r1", reviewer2: "r2", rejected: "rejected", untranslated: "untranslated", draft: "edited" };

const contextLines = [
  ["前 · 2", "旅人: ここで待っていてくれ。"],
  ["前 · 1", "「本当に開けるつもりか？」"],
  ["当前", "アリスは Ancient Ruins の入口に立ち、"],
  ["后 · 1", "「この封印は、まだ生きている……」"],
  ["后 · 2", "風が吹くたび、青白い光が"]
];

const qaIssues = [
  { severity: "error", rule: "数字一致性", msg: "原文没有数字，译文多出「3」。", line: 3, match: "苍白" },
  { severity: "warn", rule: "术语", msg: "「封印」应统一为「封印」，不要混用。", line: 2, match: "封印" },
  { severity: "warn", rule: "全半角", msg: "日中混排行检测到半角数字。", line: 3, match: "苍白" }
];

const hits = [];
for (let i = 1; i <= 12; i++) {
  hits.push({ type: "TM", rate: Math.max(72, 101 - i * 2) + "%", src: "アリスは古代遺跡の入口に立ち、封印を見つめた。", tgt: "爱丽丝站在古代遗迹入口，凝视着封印。", meta: `DEMO_TM · reviewer ${i} · 2026-11-${String(12 - (i % 8)).padStart(2, "0")}` });
}
for (let i = 1; i <= 8; i++) {
  hits.push({ type: "TB", rate: "术语", src: ["封印", "紋章", "石扉", " Ancient Ruins", "青白い", "ロウ", "入口", "空気"][i - 1], tgt: ["封印", "纹章", "石门", "Ancient Ruins", "苍白", "罗", "入口", "空气"][i - 1], meta: `Game Terms · read-only · entry ${i}` });
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
  $("#ctxSpeaker").textContent = segments[state.current].speaker;
  $("#contextTrack").innerHTML = contextLines.map(([label, text], i) => `<div class="ctx-item ${i === 2 ? "current" : ""}">
    <div class="ctx-no">${i === 2 ? '<span class="ctx-current-mark"></span>' : ""}${label}</div>
    <div class="ctx-src">${esc(text)}</div></div>`).join("");
}

function codeLines(lines, editable, qaLine = -1) {
  return lines.map((line, i) => {
    const classes = ["code-line", editable ? "target" : "source"];
    if (i === state.currentLine) classes.push("current");
    if (i === qaLine) classes.push("qa-row");
    return `<div class="${classes.join(" ")}" data-line="${i}">
      <div class="line-no">${String(i + 1).padStart(2, "0")}</div>
      <div class="line-text" ${editable ? 'contenteditable="true" spellcheck="false"' : ""}>${line}</div>
    </div>`;
  }).join("");
}

function renderEditor(seg) {
  $("#editorRow").textContent = "第 " + seg.no + " 段";
  $("#editorKey").textContent = seg.key;
  $("#editorStat").textContent = `${seg.srcLines.length} 行 · 28 / 42 字`;
  $("#sourceScroll").innerHTML = codeLines(seg.srcLines, false, qaIssues[0].line);
  $("#targetScroll").innerHTML = codeLines(seg.tgtLines, true, qaIssues[0].line);
  const qaLine = qaIssues.find((q) => q.severity === "error");
  if (qaLine) {
    const targetLine = $("#targetScroll").children[qaLine.line];
    if (targetLine) {
      const text = targetLine.querySelector(".line-text");
      if (text && text.textContent.includes(qaLine.match)) {
        text.innerHTML = esc(text.textContent).replace(qaLine.match, `<span class="qa-mark">${qaLine.match}</span>`);
      }
    }
  }
  $$("#targetScroll .line-text").forEach((el) => el.addEventListener("input", () => {
    $("#statusNote").textContent = "草稿 · 有未保存修改";
    $("#targetState").textContent = "草稿";
  }));
  $$("#sourceScroll .code-line, #targetScroll .code-line").forEach((line) => {
    const n = line.dataset.line;
    line.addEventListener("mouseenter", () => {
      $$(`.code-line[data-line="${n}"]`).forEach((row) => row.classList.add("hover"));
    });
    line.addEventListener("mouseleave", () => {
      $$(`.code-line[data-line="${n}"]`).forEach((row) => row.classList.remove("hover"));
    });
    line.addEventListener("click", () => {
      state.currentLine = Number(n);
      $$(".code-line.current").forEach((row) => row.classList.remove("current"));
      $$(`.code-line[data-line="${n}"]`).forEach((row) => row.classList.add("current"));
    });
  });
  $("#targetState").textContent = statusLabels[seg.status];
}

function renderQA() {
  $("#qaList").innerHTML = qaIssues.map((q, i) => `<div class="qa-item ${q.severity}" data-index="${i}" tabindex="0">
    <div class="qa-icon">!</div><div class="qa-line">${q.line + 1}</div>
    <div><div class="qa-rule">${q.rule}</div><div class="qa-msg">${esc(q.msg)}</div></div></div>`).join("");
  $$("#qaList .qa-item").forEach((el) => {
    el.addEventListener("click", () => focusQA(Number(el.dataset.index)));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusQA(Number(el.dataset.index)); } });
  });
}

function visibleHits() { return state.hitFilter === "all" ? hits : hits.filter((h) => h.type === state.hitFilter); }

function renderHits() {
  const list = visibleHits();
  $("#hitCount").textContent = list.length;
  $("#hitList").innerHTML = list.map((h, i) => {
    const idx = hits.indexOf(h);
    return `<div class="hit ${idx === state.selectedHit ? "selected" : ""}" data-index="${idx}" tabindex="0">
      <div class="hit-rate ${h.type === "TB" ? "tb" : ""}">${h.type === "TB" ? "TB" : h.rate}</div>
      <div><div class="hit-src">${esc(h.src)}</div><div class="hit-tgt">${esc(h.tgt)}</div></div></div>`;
  }).join("");
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
  $("#targetScroll").querySelectorAll(".qa-mark").forEach((m) => m.classList.remove("warn"));
  const line = $("#targetScroll").children[q.line];
  if (line) {
    line.scrollIntoView({ block: "center", behavior: "smooth" });
    const text = line.querySelector(".line-text");
    if (text) {
      text.innerHTML = esc(text.textContent).replace(q.match, `<span class="qa-mark">${q.match}</span>`);
      text.querySelector(".qa-mark")?.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }
  $("#statusNote").textContent = `QA · ${q.rule} · 第 ${segments[state.current].no} 段`;
}

function selectSegment(no) {
  const idx = segments.findIndex((s) => s.no === no); if (idx < 0) return;
  state.current = idx;
  renderSegmentList(); renderContext(); renderEditor(segments[idx]);
  $("#statusNote").textContent = `第 ${segments[idx].no} 段 · ${statusLabels[segments[idx].status]}`;
  document.querySelector(`#segList .seg[data-no="${no}"]`)?.scrollIntoView({ block: "nearest" });
}

/* sync scroll between source/target by ratio (v1: equal line counts in most rows) */
let syncing = false;
function syncScroll(from, to) {
  from.addEventListener("scroll", () => {
    if (syncing) return;
    syncing = true;
    const max = Math.max(1, from.scrollHeight - from.clientHeight);
    const ratio = from.scrollTop / max;
    to.scrollTop = ratio * Math.max(0, to.scrollHeight - to.clientHeight);
    requestAnimationFrame(() => { syncing = false; });
  });
}
syncScroll($("#sourceScroll"), $("#targetScroll"));
syncScroll($("#targetScroll"), $("#sourceScroll"));

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
  toast(`${el.dataset.action} · 原型入口`);
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

if (location.hash === "#dark") document.body.classList.add("dark");
renderSegmentList(); renderContext(); renderEditor(segments[state.current]); renderQA(); renderHits();

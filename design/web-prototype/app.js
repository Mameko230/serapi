// Synthetic prototype data only. No external requests, no real project text.
const segments = [
  { no: 1, key: "ev_0010_guard", speaker: "衛兵", status: "confirmed", rate: 100,
    src: "装備画面を開きます。", tgt: "打开装备界面。", qa: 0,
    sourceHtml: "装備画面を開きます。", targetHtml: "打开装备界面。",
    context: ["旅人: ここで待っていてくれ。", "旅人: 支度ができたら声をかける。", "装備画面を開きます。", "よし、行くぞ！", "アリスの攻撃力が上がった！"] },
  { no: 2, key: "ev_0020_guard", speaker: "旅人", status: "edited", rate: 96,
    src: "よし、行くぞ！", tgt: "好，出发吧！", qa: 1,
    sourceHtml: "よし、行くぞ！", targetHtml: "好，出发吧！",
    context: ["旅人: 支度ができたら声をかける。", "装備画面を開きます。", "よし、行くぞ！", "アリスの攻撃力が上がった！", "回復薬を3つ使いますか？"] },
  { no: 3, key: "ev_0030_alice", speaker: "アリス", status: "reviewer1", rate: 88,
    src: "アリスの攻撃力が上がった！", tgt: "爱丽丝的攻击力提升了！\n攻击力提高了 3 点，战斗会轻松些。",
    qa: 3,
    sourceHtml: 'アリスの攻撃力が <span class="tag">#12 12</span> 上がった！',
    targetHtml: '爱丽丝的攻击力提升了<span class="tag">#12 12</span>！<br><span class="qa-mark">攻击力提高了 3 点</span>，战斗会轻松些。',
    context: ["よし、行くぞ！", "アリスの攻撃力が上がった！", "回復薬を3つ使いますか？", "セーブデータを上書きします。", "この先は危険です。"] },
  { no: 4, key: "ev_0040_item", speaker: "アリス", status: "reviewer2", rate: 91,
    src: "回復薬を3つ使いますか？", tgt: "要使用 3 个恢复药吗？", qa: 1,
    sourceHtml: "回復薬を3つ使いますか？", targetHtml: "要使用 3 个恢复药吗？",
    context: ["アリスの攻撃力が上がった！", "回復薬を3つ使いますか？", "セーブデータを上書きします。", "この先は危険です。", "町へ戻りましょう。"] },
  { no: 5, key: "ev_0050_save", speaker: "システム", status: "untranslated", rate: null,
    src: "セーブデータを上書きします。", tgt: "将覆盖存档数据。", qa: 0,
    sourceHtml: "セーブデータを上書きします。", targetHtml: "将覆盖存档数据。",
    context: ["回復薬を3つ使いますか？", "セーブデータを上書きします。", "この先は危険です。", "町へ戻りましょう。", "レベルが上がりました！"] },
  { no: 6, key: "ev_0060_warn", speaker: "ナレーション", status: "edited", rate: 73,
    src: "この先は危険です。", tgt: "前方危险。", qa: 0,
    sourceHtml: "この先は危険です。", targetHtml: "前方危险。",
    context: ["セーブデータを上書きします。", "この先は危険です。", "町へ戻りましょう。", "レベルが上がりました！", "所持金が不足しています。"] },
  { no: 7, key: "ev_0070_town", speaker: "ナレーション", status: "confirmed", rate: 100,
    src: "町へ戻りましょう。", tgt: "回城吧。", qa: 0,
    sourceHtml: "町へ戻りましょう。", targetHtml: "回城吧。",
    context: ["この先は危険です。", "町へ戻りましょう。", "レベルが上がりました！", "所持金が不足しています。", "設定画面に移動します。"] },
  { no: 8, key: "ev_0080_level", speaker: "システム", status: "draft", rate: 68,
    src: "レベルが上がりました！", tgt: "等级提升了！", qa: 1,
    sourceHtml: "レベルが上がりました！", targetHtml: "等级提升了！",
    context: ["町へ戻りましょう。", "レベルが上がりました！", "所持金が不足しています。", "設定画面に移動します。", "ダウンロード中……"] },
  { no: 9, key: "ev_0090_menu", speaker: "システム", status: "edited", rate: 84,
    src: "設定画面に移動します。", tgt: "前往设置画面。", qa: 0,
    sourceHtml: "設定画面に移動します。", targetHtml: "前往设置画面。",
    context: ["レベルが上がりました！", "設定画面に移動します。", "ダウンロード中……", "もう一度挑戦しますか？", "コンティニューしますか？"] },
  { no: 10, key: "ev_0100_continue", speaker: "システム", status: "rejected", rate: 77,
    src: "コンティニューしますか？", tgt: "要继续吗？", qa: 0,
    sourceHtml: "コンティニューしますか？", targetHtml: "要继续吗？",
    context: ["設定画面に移動します。", "コンティニューしますか？", "もう一度挑戦しますか？", "所持金が不足しています。", "町へ戻りましょう。"] }
];

const statusLabels = {
  confirmed: "已确认", edited: "编辑", reviewer1: "R1", reviewer2: "R2",
  rejected: "拒绝", untranslated: "未译", draft: "草稿"
};
const statusClass = {
  confirmed: "confirmed", edited: "edited", reviewer1: "r1", reviewer2: "r2",
  rejected: "rejected", untranslated: "untranslated", draft: "edited"
};

const qaIssues = [
  { severity: "error", rule: "数字", msg: "原文有 “12”，译文是 “3”，请核对数量。", line: 3, match: "3 点" },
  { severity: "warn", rule: "术语", msg: "攻撃力 应采用「攻击力」，不要写成「攻击力提升」。", line: 3, match: "攻击力提升了" },
  { severity: "warn", rule: "全半角", msg: "日中混排行里出现了半角数字。", line: 3, match: "3 点" }
];

const hits = [
  { type: "TM", rate: "100%", src: "アリスの攻撃力が上がった！", tgt: "爱丽丝的攻击力提升了！", meta: "DEMO_TM · reviewer A · 2026-11-12" },
  { type: "TM", rate: "88%", src: "攻撃力が上がった", tgt: "攻击力提升了", meta: "DEMO_TM · editor B · 2026-11-10" },
  { type: "TB", rate: "term", src: "攻撃力", tgt: "攻击力", meta: "Game Terms · read-only · double-click to insert" },
  { type: "TB", rate: "term", src: "回復薬", tgt: "恢复药", meta: "Game Items · read-only" }
];

const state = { current: 2, filter: "all", contextCollapsed: false, railCollapsed: false };
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function visibleSegments() {
  if (state.filter === "all") return segments;
  if (state.filter === "attention") return segments.filter((s) => s.qa > 0);
  if (state.filter === "review") return segments.filter((s) => ["reviewer1", "reviewer2"].includes(s.status));
  if (state.filter === "done") return segments.filter((s) => ["confirmed", "reviewer1", "reviewer2"].includes(s.status));
  return segments;
}

function renderSegmentList() {
  const list = $("#segList");
  const rows = visibleSegments();
  list.innerHTML = rows.map((s) => {
    const active = segments[state.current].no === s.no;
    const rate = s.rate === null ? "—" : s.rate + "%";
    const qa = s.qa ? `<span class="seg-qas">● ${s.qa}</span>` : "";
    return `<div class="seg ${active ? "active" : ""}" data-no="${s.no}" data-status="${s.status}" tabindex="-1">
      <div class="seg-no">${s.no}</div>
      <div class="seg-indicator"></div>
      <div class="seg-txt">
        <div class="seg-src">${esc(s.src)}</div>
        <div class="seg-tgt">${esc(s.tgt.split("\n")[0])}</div>
        <div class="seg-meta">
          <span class="badge ${statusClass[s.status]}">${statusLabels[s.status]}</span>
          ${qa}
          <span class="seg-rate">${rate}</span>
        </div>
      </div>
    </div>`;
  }).join("");
  $("#segCount").textContent = visibleSegments().length;
  $$("#segList .seg").forEach((el) => el.addEventListener("click", () => selectSegment(Number(el.dataset.no))));
}

function renderContext(seg) {
  const names = ["前 · 2", "前 · 1", "当前", "后 · 1", "后 · 2"];
  $("#ctxSpeaker").textContent = seg.speaker;
  $("#contextTrack").innerHTML = seg.context.map((line, i) => {
    const cur = i === 2;
    return `<div class="ctx-item ${cur ? "current" : ""}">
      <div class="ctx-top">${cur ? '<span class="marker">●</span>' : ""}<span>${names[i]}</span></div>
      <div class="ctx-src">${esc(line)}</div>
      <div class="ctx-tgt">${esc(cur ? seg.tgt : segments[Math.max(0, state.current - 2 + i)]?.tgt || "")}</div>
    </div>`;
  }).join("");
}

function renderEditor(seg) {
  $("#editorRow").textContent = "第 " + seg.no + " 段";
  $("#editorKey").textContent = seg.key;
  $("#editorStat").textContent = "28 / 42";
  $("#sourceText").innerHTML = seg.sourceHtml;
  $("#targetText").innerHTML = seg.targetHtml;
  $("#editorStatus").textContent = statusLabels[seg.status];
  $("#infoSpeaker").textContent = seg.speaker;
}

function renderQA() {
  $("#qaList").innerHTML = qaIssues.map((q, i) => `<div class="qa-item ${q.severity}" data-index="${i}" tabindex="0">
    <div class="qa-icon">!</div>
    <div class="qa-line">${q.line}</div>
    <div class="qa-copy"><div class="qa-rule">${q.rule}</div><div class="qa-msg">${esc(q.msg)}</div></div>
  </div>`).join("");
  $$("#qaList .qa-item").forEach((el) => {
    el.addEventListener("click", () => focusQA(Number(el.dataset.index)));
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusQA(Number(el.dataset.index)); } });
  });
}

function renderHits() {
  $("#hitList").innerHTML = hits.map((h, i) => `<div class="hit" data-index="${i}" tabindex="0">
    <div class="hit-rate ${h.type === "TB" ? "tb" : ""}">${h.type === "TB" ? "术语" : h.rate}</div>
    <div><div class="hit-src">${esc(h.src)}</div><div class="hit-tgt">${esc(h.tgt)}</div>
      <div class="hit-detail">${esc(h.meta)}</div></div>
  </div>`).join("");
  $$("#hitList .hit").forEach((el) => {
    const toggle = () => el.classList.toggle("open");
    el.addEventListener("click", toggle);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
}

function focusQA(index) {
  const q = qaIssues[index];
  if (!q) return;
  const target = $("#targetText");
  target.focus();
  const text = target.textContent || "";
  const idx = text.indexOf(q.match);
  if (idx >= 0) {
    const range = document.createRange();
    const node = findTextNode(target, idx);
    if (node) {
      range.setStart(node, idx - node.start);
      range.setEnd(node, idx - node.start + q.match.length);
      const sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(range);
    }
  } else {
    const mark = target.querySelector(".qa-mark");
    if (mark) mark.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  $("#statusNote").textContent = `QA · ${q.rule} · 第 ${segments[state.current].no} 段`;
}

function findTextNode(root, offset) {
  let acc = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (acc + node.textContent.length >= offset) return { node, start: acc };
    acc += node.textContent.length;
  }
  return null;
}

function selectSegment(no) {
  const idx = segments.findIndex((s) => s.no === no);
  if (idx < 0) return;
  state.current = idx;
  const seg = segments[idx];
  renderSegmentList();
  renderContext(seg);
  renderEditor(seg);
  $("#statusNote").textContent = `第 ${seg.no} 段 · ${statusLabels[seg.status]}`;
  document.querySelector(`#segList .seg[data-no="${seg.no}"]`)?.scrollIntoView({ block: "nearest" });
}

$$("#filters .filter").forEach((btn) => btn.addEventListener("click", () => {
  $$("#filters .filter").forEach((b) => b.classList.toggle("active", b === btn));
  state.filter = btn.dataset.filter;
  renderSegmentList();
}));

$("#ctxToggle").addEventListener("click", () => {
  state.contextCollapsed = !state.contextCollapsed;
  $("#contextPanel").classList.toggle("collapsed", state.contextCollapsed);
  $("#ctxToggle").textContent = state.contextCollapsed ? "Show context" : "Hide context";
});

$("#rail").addEventListener("click", (e) => {
  if (e.target.closest("#collapseRail")) {
    state.railCollapsed = !state.railCollapsed;
    document.querySelector(".workspace").classList.toggle("rail-collapsed", state.railCollapsed);
    $("#collapseRail").textContent = state.railCollapsed ? "Expand" : "Collapse";
  }
});

$("#themeToggle").addEventListener("click", () => document.body.classList.toggle("dark"));

$("#segList").addEventListener("keydown", (e) => {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  e.preventDefault();
  const next = Math.max(0, Math.min(segments.length - 1, state.current + (e.key === "ArrowDown" ? 1 : -1)));
  selectSegment(segments[next].no);
});

$("#targetText").addEventListener("input", () => {
  $("#statusNote").textContent = "草稿 · 有未保存修改";
  $("#editorStatus").textContent = "草稿";
});

// initial
if (new URLSearchParams(location.search).get("theme") === "dark" || location.hash === "#dark") document.body.classList.add("dark");
renderSegmentList();
renderContext(segments[state.current]);
renderEditor(segments[state.current]);
renderQA();
renderHits();

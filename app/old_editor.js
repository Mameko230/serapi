/* 旧版编辑器适配：活动 editor、DOM token 提取、读段。 */
(function () {
  if (window.__mdOldEditor) return;

  function create(deps) {
    /* ================= 旧版编辑器（自绘 grid + 隐藏 input） ================= */
    function oldActiveEditor() {
      try {
        var EM = window.EditorModule;
        var c = EM && EM.getActiveEditorContainer && EM.getActiveEditorContainer();
        return c && (c.activeEditor || c.lastActiveEditor) || null;
      } catch (e) { return null; }
    }
    // 目标行校验。strict=true（测试/指定行流程）：活动编辑器必须在 focusSegment 预设的 _targetTd 内；
    // strict=false（用户直接点 memoQ 的流程）：从活动编辑器反推所属译文格。
    function oldActiveEditorForTarget(strict) {
      var ed = oldActiveEditor();
      if (!ed) return null;
      var root = oldEditorRoot(ed);
      if (!root) return null;
      var td = window.__md._targetTd;
      // strict 且已预设目标格：必须落在目标格内（合成点击路径）
      if (strict && td) return td.contains(root) ? ed : null;
      // strict 但无预设目标格（moveToRow 路径）：反推所属译文格，由 Qt 侧核对行号
      if (td && td.contains(root)) return ed;
      var p = deps.page();
      var tds = document.querySelectorAll((p && p.translatedCell) || 'td.translated-segment-grid');
      for (var i = 0; i < tds.length; i++) {
        if (tds[i].contains(root)) { window.__md._targetTd = tds[i]; return ed; }
      }
      return null;  // 活动编辑器不在任何译文格（原文格/未激活）→ 拒绝
    }
    function oldEditorRoot(ed) {
      var r = ed && ed.editorRenderer;
      var hosts = [r && r.$contentContainerSpan, r && r.$contentContainerWrapperDiv];
      for (var i = 0; i < hosts.length; i++) {
        var el = hosts[i] && (hosts[i][0] || hosts[i]);
        if (el && el.nodeType === 1) return el;
      }
      return null;
    }
    function oldResolveTag(ed, node) {
      try {
        var jq = window.jQuery || window.$;
        if (!jq) return null;
        if (!ed || !ed.tagManager || !ed.tagManager.findReferencedTagFromId) return null;
        var ref = ed.tagManager.findReferencedTagFromId(jq(node));
        if (ref && ref.tag) return { name: ref.tag.name || '', close: ref.tag.type === 1 };
      } catch (e) {}
      return null;
    }
    // DOM 令牌提取（与 memoweb-preview 的 extractTokens 同规则）
    function oldExtractTokens(root, ed) {
      var tokens = [];
      (function walk(node, inAsset) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (node.textContent) tokens.push({ t: 'text', v: node.textContent });
          return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        var cls = String(node.className || '');
        if (node.hasAttribute && node.hasAttribute('tag-name')) {
          var val = '';
          var raw = node.getAttribute('data-tag-val');
          if (raw) { try { val = (JSON.parse(raw).value) || ''; } catch (e) {} }
          tokens.push({ t: 'tag', name: node.getAttribute('tag-name') || '[tag]', display: node.getAttribute('tag-display-text') || '', tagType: node.getAttribute('tag-type') || '', val: val });
          return;
        }
        if (/\btag\b/.test(cls) && /editor-char/.test(cls)) {
          var inner = node.querySelector('.tag-content');
          var name = (inner ? inner.textContent : node.textContent).trim();
          name = name.replace(/(\s+(id|val)="[^"]*")+\s*$/, '').trim();
          var tid = inner && inner.getAttribute ? inner.getAttribute('data-tagid') : '';
          var tkind = /inline-close/.test(cls) ? 'close' : (/inline-empty/.test(cls) ? 'empty' : 'open');
          if (/^\d{1,3}$/.test(name) || !name) {
            var info = oldResolveTag(ed, node);
            if (info && info.name) name = info.close && !/^\[?\//.test(info.name) ? '[/' + info.name + ']' : info.name;
            else name = name || '[tag]';
          }
          tokens.push({ t: 'tag', name: name, display: '', tagType: '', val: '', id: tid, tagKind: tkind });
          return;
        }
        if (/editor-cursor/.test(cls)) return;
        if (/asset-container/.test(cls)) inAsset = true;
        if (inAsset && !/asset-container/.test(cls)) {
          var nm = (node.getAttribute('title') || node.getAttribute('alt') || node.textContent || '').trim();
          tokens.push({ t: 'tag', name: nm || '[asset]', display: '', tagType: '', val: '' });
          return;
        }
        if (node.tagName === 'IMG') {
          var nm2 = (node.getAttribute('title') || node.getAttribute('alt') || '').trim();
          if (nm2) { tokens.push({ t: 'tag', name: nm2, display: '', tagType: '', val: '' }); return; }
        }
        for (var ch = 0; ch < node.childNodes.length; ch++) walk(node.childNodes[ch], inAsset);
      })(root, false);
      return tokens;
    }
    function oldReadSegment(strict) {
      var ed = oldActiveEditorForTarget(strict);
      if (!ed) return { ok: false, err: '旧版编辑器实例未找到（目标行未激活）' };
      var root = oldEditorRoot(ed);
      if (!root) return { ok: false, err: '旧版编辑器根节点未找到' };
      var res = { ok: true, rowId: null, locked: false, tokens: oldExtractTokens(root, ed) };
      // tag 富化：DOM 里只有编号，display/val/规范名从行 ITaglist 补（胶囊可视化靠这个）
      try {
        var ctrl = deps.oldGridCtrl();
        var ar = ctrl && ctrl.getActiveRow && ctrl.getActiveRow();
        var rowHit = null;
        if (ctrl && ar) {
          var rows = deps.oldCachedRows(ctrl);
          for (var ri = 0; ri < rows.length; ri++) {
            if (rows[ri].id === ar.id) { rowHit = rows[ri]; break; }
          }
        }
        if (rowHit) {
          var both = deps.segTags(rowHit.targetWebSegment).concat(deps.segTags(rowHit.sourceWebSegment));
          var map = {};
          for (var k = 0; k < both.length; k++) {
            var key1 = both[k].id + '|' + both[k].kind;
            if (!map[key1]) map[key1] = both[k];
            if (!map[both[k].id]) map[both[k].id] = both[k];
          }
          for (var m = 0; m < res.tokens.length; m++) {
            var tk = res.tokens[m];
            if (tk.t !== 'tag' || tk.id === undefined || tk.id === '') continue;
            var hit = map[String(tk.id) + '|' + (tk.tagKind || '')] || map[String(tk.id)];
            if (hit) {
              if (!tk.display) tk.display = hit.display;
              if (!tk.val && hit.val) tk.val = hit.val;
              if (!tk.attrs) tk.attrs = hit.attrs;
              if (!tk.name || tk.name === '[tag]' || /^\d{1,3}$/.test(tk.name)) tk.name = hit.name;
            }
          }
        }
      } catch (e) {}
      try {
        var tr = window.__md._targetTd && window.__md._targetTd.closest && window.__md._targetTd.closest('tr');
        var orderTd = tr && tr.querySelector && tr.querySelector('td.order');
        res.rowNo = orderTd ? orderTd.textContent.trim() : null;
        res.trCls = tr ? String(tr.className).slice(0, 40) : null;
      } catch (e) {}
      // 原文 tokens（桌面端左原文栏对照用）：同行原文格 DOM 提取，与译文同规则
      // 原文格 class = original-segment-grid（译文格 = translated-segment-grid，同一 tr）
      try {
        var trS = window.__md._targetTd && window.__md._targetTd.closest && window.__md._targetTd.closest('tr');
        var srcTd = trS && trS.querySelector && trS.querySelector('td.original-segment-grid');
        var srcRoot = srcTd && (srcTd.querySelector('.content-container') || srcTd.querySelector('.editor-cell'));
        if (srcRoot) res.srcTokens = oldExtractTokens(srcRoot, ed);
      } catch (e) {}
      return res;
    }


    return { oldActiveEditor, oldActiveEditorForTarget, oldEditorRoot,
             oldResolveTag, oldExtractTokens, oldReadSegment };
  }

  window.__mdOldEditor = { create: create };
})();

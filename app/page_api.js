/* 页面诊断 API：readSource / debugState / selectorSnapshot / editorState。 */
(function () {
  if (window.__mdPageApi) return;
  function create(deps) {
    function readSource(rowIdx) {
      var kind = deps.detect();
      try {
        if (kind === 'old') {
          var p = deps.page();
          var rowEls = deps.pageEditorRows();
          var tr = rowEls[Math.max(1, rowIdx || 1) - 1];
          var td = tr && tr.querySelector((p && p.originalCell) || 'td.original-segment-grid');
          var root = td && td.querySelector((p && p.contentRoot) || '.content-container');
          if (!root) return { ok: false, err: '原文格未找到（行未渲染？）' };
          return { ok: true, tokens: deps.oldExtractTokens(root, null) };
        }
        return { ok: false, err: 'readSource 仅旧版支持' };
      } catch (e) { return { ok: false, err: 'readSource ERR ' + e.message }; }
    }

    // 诊断：返回编辑器内部状态（往返测试排障用）
    function debugState() {
      var kind = deps.detect();
      try {
        if (kind === 'old') {
          var ed = deps.oldActiveEditor();
          if (!ed) return { kind: kind, hasEd: false };
          return {
            kind: kind, hasEd: true,
            str: ed.getText ? ed.getText(true) : null,
            len: ed.getContentLength ? ed.getContentLength() : null,
            cursor: ed.getCursorPosition ? ed.getCursorPosition() : null,
            readOnly: !!(ed.settings && ed.settings.isReadOnly),
          }
        }
        if (kind === 'new') {
          var v = deps.activeView() || deps.anyView();
          if (!v) return { kind: kind, hasEd: false };
          return { kind: kind, hasEd: true, str: v.state.doc.toString(), rowId: v.state.doc.attrs.rowId };
        }
        return { kind: kind };
      } catch (e) { return { kind: kind, err: e.message }; }
    }

    function selectorSnapshot() {
      return JSON.parse(JSON.stringify(deps.pageRules));
    }

    function editorState() {
      var v = deps.activeView() || deps.anyView();
      var flags = deps.editFlags(v);
      var ref = { rowNo: null, rowId: flags.rowId };
      try {
        if (window.__mdState && window.__mdState.rowRef) ref = window.__mdState.rowRef(v);
      } catch (e) {}
      return { ok: !!v, rowNo: ref.rowNo, rowId: ref.rowId, flags: flags,
               writePolicy: { canWrite: !flags.tracking && !flags.readOnly && !flags.locked } };
    }

    return { readSource, debugState, selectorSnapshot, editorState };
  }
  window.__mdPageApi = { create: create };
})();

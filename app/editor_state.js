/* Serapi 页面编辑状态：跟踪修改/只读/锁定/作者/schema/rowRef。
 * 独立模块，便于单测；bridge.js 保留 fallback。 */
(function () {
  if (window.__mdState) return;

  function flags(view) {
    var out = {
      tracking: false, readOnly: false, locked: false, author: '',
      rowId: null, marks: [], plugins: [],
    };
    if (!view || !view.state) return out;
    try {
      var attrs = view.state.doc.attrs || {};
      out.readOnly = !!attrs.readOnly;
      out.locked = !!attrs.locked;
      out.rowId = attrs.rowId == null ? null : String(attrs.rowId);
      out.marks = Object.keys((view.state.schema && view.state.schema.marks) || {});
      var ps = view.state.plugins || [];
      for (var i = 0; i < ps.length; i++) {
        var key = String(ps[i].key || '');
        if (!/^trackChanges/.test(key)) continue;
        var st = ps[i].getState(view.state);
        out.tracking = !!(st && st.isTrackingChanges);
        out.author = st && st.currentAuthor ? String(st.currentAuthor) : '';
      }
    } catch (e) {}
    return out;
  }

  function rowRef(view) {
    var ref = { rowNo: null, rowId: null };
    if (!view || !view.state) return ref;
    try {
      ref.rowId = view.state.doc.attrs && view.state.doc.attrs.rowId != null
        ? String(view.state.doc.attrs.rowId) : null;
      var dom = view.dom;
      var row = dom && dom.closest ? dom.closest('.translation-row') : null;
      var roleRow = row && row.closest ? row.closest('[role="row"]') : null;
      var raw = roleRow && roleRow.getAttribute('aria-rowindex');
      var n = parseInt(raw, 10);
      if (n > 0) ref.rowNo = n;
    } catch (e) {}
    return ref;
  }

  window.__mdState = { flags: flags, rowRef: rowRef };
})();

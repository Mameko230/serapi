/* 编辑器类型/版本识别与编辑状态 flags。 */
(function () {
  if (window.__mdDetect) return;
    function fingerprintHash(value) {
      var h = 2166136261;
      for (var i = 0; i < value.length; i++) {
        h ^= value.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return (h >>> 0).toString(16);
    }

    /* 文档级编辑状态：跟踪修改/只读/锁定/作者/schema。写策略依赖它。 */
    function newEditFlags(view) {
      try {
        if (window.__mdState && window.__mdState.flags) return window.__mdState.flags(view);
      } catch (e) {}
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

    /* 从 Version-12.5-*.js 资源名提取编辑器版本；找不到返回空串。 */
    function newEditorVersion() {
      try {
        var ss = document.querySelectorAll('script[src]');
        for (var i = 0; i < ss.length; i++) {
          var src = String(ss[i].getAttribute('src') || ss[i].src || '');
          var m = /Version-([0-9.]+)-/.exec(src);
          if (m) return m[1];
        }
      } catch (e) {}
      return '';
    }

    /* ================= 编辑器类型识别 ================= */
    function detectEditor() {      var p = location.pathname || '';
      if (p.indexOf('/memoqweb/editor/') >= 0) return 'new';
      if (p.indexOf('Translation.aspx') >= 0) return 'old';
      return null;
    }

    /* ================= 能力探测（启动时一次性告知 Qt 侧） ================= */

  window.__mdDetect = {
    fingerprintHash: fingerprintHash,
    newEditFlags: newEditFlags,
    newEditorVersion: newEditorVersion,
    detectEditor: detectEditor,
  };
})();

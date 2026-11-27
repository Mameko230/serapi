/* 能力探测与结构指纹。 */
(function () {
  if (window.__mdCapabilities) return;

  function create(deps) {
    function capabilities() {
      var kind = deps.detect();
      var f = {
        listRows: false, tmHits: false, segmentInfo: false, terms: false,
        filter: false, concordance: false, confirm: false,
        readSegment: false, writeSegment: false, docStats: false, rowChanged: false,
      }
      var reasons = {};
      try {
        if (kind === 'old') {
          var p = deps.page();
          var ctrl = deps.oldGridCtrl();
          var gcm = ctrl && ctrl.gridContentManager;
          f.listRows = !!gcm;
          f.tmHits = f.listRows;
          f.segmentInfo = f.listRows;
          f.readSegment = true;
          f.writeSegment = true;
          f.rowChanged = true;
          f.docStats = !!(p && p.statusBar && document.querySelector(p.statusBar));
          f.confirm = !!deps.pageConfirmInput();
          f.reject = f.confirm;
          f.concordance = !!(window.WebTrans && WebTrans.Core);
          try {
            var core = deps.termCore();
            f.terms = !!(core && core.lastUsedTBGuid);
            f.termEdit = f.terms;
            f.termQuickAdd = !!core;
          } catch (e) {}
          try {
            var fe = deps.pageFilterInput('source');
            var fs = (fe && window.angular) ? angular.element(fe).scope() : null;
            f.filter = !!(fs && fs.ctrl
              && typeof fs.ctrl.filterForSourceOrTarget === 'function');
          } catch (e) {}
        } else if (kind === 'new') {
          f.rowChanged = true;
          f.docStats = true;
          f.version = deps.version();
          f.listRows = !!deps.rowsTable();
          // 命中走文档 API，不依赖右侧结果面板是否已渲染/打开。
          f.tmHits = !!deps.docBase();
          f.segmentInfo = !!deps.namespace('translation');
          // 过滤走原生 filter API（只改视图），不依赖旧版过滤面板。
          f.filter = !!deps.docBase();
          // 确认/拒绝用新版原生快捷键（Ctrl+Enter / Shift+Enter），跳转遵循 memoQ 设置。
          f.confirm = true;
          f.reject = true;
          // 新版文档已有 /terms/quick-add（Ctrl+Q/Ctrl+E 的主术语添加）；
          // 术语编辑仍复用旧 QTermService 的条目读取/更新。
          f.termEdit = !!deps.projectGuid();
          f.termQuickAdd = !!deps.projectGuid();
          f.terms = !!(deps.projectGuid() || deps.docBase());
          // 新版自带 concordance 文档接口：POST /concordance 建上下文，GET 取结果。
          f.concordance = !!deps.docBase();
          // 新版原生命令 findAndReplace 带热键；Serapi 打开引擎浮层后派发 Ctrl+F。
          f.findReplace = true;
          f.readSegment = false;
          try { f.readSegment = !!deps.anyView(); f.writeSegment = f.readSegment; } catch (e) {}
          try {
            f.endpoints = {
              rows: !!deps.docBase(),
              rowsMeta: !!deps.docBase(),
              hits: !!deps.docBase(),
              comments: !!deps.namespace('translation'),
              issues: !!deps.docBase(),
              lock: !!deps.docBase(),
              splitJoin: !!deps.docBase(),
              concordance: !!deps.docBase(),
              settings: !!deps.docBase(),
              deliver: !!deps.namespace('translation'),
            }
          } catch (e) { f.endpoints = {}; }
          try {
            var editView = null;
            try { editView = deps.activeView() || deps.anyView(); } catch (e) {}
            f.document = deps.editFlags(editView);
            f.writePolicy = {
              canWrite: !f.document.tracking && !f.document.readOnly && !f.document.locked,
              tracking: f.document.tracking,
              readOnly: f.document.readOnly,
              locked: f.document.locked,
              author: f.document.author,
            }
          } catch (e) {
            f.document = f.document || {};
            f.writePolicy = f.writePolicy || { canWrite: false };
          }
        }
      } catch (e) {
        reasons.error = String(e.message || e);
      }
      if (!f.listRows) {
        reasons.listRows = (kind === 'new')
          ? '新版编辑器：段列表尚未渲染（等待文档网格）'
          : '需要旧版编辑器（段列表）';
      }
      if (!f.tmHits) {
        reasons.tmHits = (kind === 'new')
          ? '新版编辑器：文档 API 尚未就绪'
          : '需要旧版编辑器（TM/TB 命中）';
      }
      if (!f.segmentInfo) {
        reasons.segmentInfo = (kind === 'new')
          ? '新版编辑器：注释接口尚未就绪'
          : '需要旧版编辑器（段信息）';
      }
      if (!f.terms) reasons.terms = '需要旧版编辑器与已加载术语库';
      if (!f.termEdit) reasons.termEdit = '需要旧版编辑器或新版文档项目（术语编辑）';
      if (!f.filter) {
        reasons.filter = (kind === 'new')
          ? '新版编辑器：过滤接口尚未就绪'
          : '需要旧版编辑器的原生过滤面板';
      }
      if (!f.concordance) reasons.concordance = '需要旧版编辑器或新版文档 API（语词检索）';
      if (!f.findReplace && deps.detect() === 'new') {
        reasons.findReplace = '需要新版编辑器（原生查找替换）';
      }
      if (!f.confirm) reasons.confirm = '需要旧版编辑器（原生确认）';
      if (!f.readSegment) reasons.readSegment = '当前段编辑器尚未就绪';
      return { ok: !!kind, editor: kind, features: f, reasons: reasons,
               fingerprint: pageFingerprint() };
    }

    /* 结构指纹：只返回选择器命中/数量，不读取任何页面文本。 */
    function pageFingerprint() {
      var kind = deps.detect();
      var p = deps.page();
      if (!p) {
        return { ok: false, editor: null, version: 0, signature: '',
                 markers: {}, missing: ['editor'] };
      }
      var markers = { version: p.version };
      var missing = [];
      try {
        if (kind === 'old') {
          var grid = deps.pageGridEl();
          var ctrl = deps.oldGridCtrl();
          var gcm = ctrl && ctrl.gridContentManager;
          markers.grid = !!grid;
          markers.gridContentManager = !!gcm;
          markers.editorRows = deps.pageEditorRows().length;
          markers.statusBar = !!document.querySelector(p.statusBar);
          markers.filterPane = !!deps.pageFilterInput('source');
          markers.confirm = !!deps.pageConfirmInput();
          markers.cachedRows = gcm ? deps.oldCachedRows(ctrl).length : 0;
          if (!markers.grid) missing.push('grid');
          if (!markers.gridContentManager) missing.push('gridContentManager');
        } else if (kind === 'new') {
          var pms = deps.pagePmList();
          markers.proseMirror = pms.length;
          markers.reactFiber = 0;
          for (var i = 0; i < pms.length; i++) {
            var host = pms[i].parentElement;
            if (host && Object.keys(host).some(function (k) {
              return k.indexOf('__reactFiber$') === 0;
            })) markers.reactFiber++;
          }
          markers.active = false;
          try { markers.active = !!deps.activeView(); } catch (e) {}
          markers.rowsTable = !!deps.rowsTable();
          markers.rowCount = deps.rowElements().length;
          markers.rowTotal = deps.rowTotal() || 0;
          markers.hitsPanel = !!deps.hitsPanel();
          if (!markers.proseMirror) missing.push('proseMirror');
          if (!markers.rowsTable) missing.push('rowsTable');
        }
      } catch (e) {
        missing.push('fingerprint-error');
        markers.error = String(e.message || e).slice(0, 120);
      }
      return {
        ok: missing.length === 0,
        editor: kind,
        version: p.version,
        signature: deps.hash(JSON.stringify(markers)),
        markers: markers,
        missing: missing,
      }
    }

    return { capabilities: capabilities, pageFingerprint: pageFingerprint };
  }

  window.__mdCapabilities = { create: create };
})();

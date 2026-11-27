// Serapi 桥接脚本：注入 memoQ 页面主世界，建立与 Qt 的 QWebChannel 通道
// 提供双编辑器统一的段读写 API（token 流格式与 memoweb-preview 油猴脚本一致）：
//   {t:'text', v:'字符串', marks:['bold',...]}   — 纯文本
//   {t:'tag',  name, display, tagType, val, attrs} — tag（新版 attrs 为 PM 节点完整 attrs）
(function () {
  if (window.__md) return;
  window.__md = { ready: false, api: {}, _cbs: {}, _lastRowKey: '' };

  function log(s) { try { console.log('[serapi] ' + s); } catch (e) {} }

  new QWebChannel(qt.webChannelTransport, function (channel) {
    var qt = channel.objects.mdBridge;
    window.__md.qt = qt;
    window.__md.push = function (type, data) {
      try {
        var d = data || {};
        if (!d.editor) d.editor = detectEditor();          // 页面身份（Qt 定位编辑器页用）
        if (!d.url) d.url = location.pathname;
        qt.push(JSON.stringify({ type: type, data: d }));
      } catch (e) { log('push ERR ' + e.message); }
    };
    window.__md.on = function (type, cb) { (window.__md._cbs[type] = window.__md._cbs[type] || []).push(cb); };
    window.__md.emit = function (type, data) {
      (window.__md._cbs[type] || []).forEach(function (cb) { try { cb(data); } catch (e) {} });
    };

    /* ================= 页面结构适配层 =================
       所有页面级选择器集中在这里；memoQ 改版时只需要改这一张表。
       注意：这里只描述结构，不读取/缓存任何原文、译文或项目数据。 */
    // 选择器规则包由 bridge.py 在启动时从 app/page_rules.json 注入。
    // 页面改版时可替换规则包，不必改 bridge.js。
    var PAGE = window.__mdPageHelpers.PAGE;
    function page() { return window.__mdPageHelpers.page(); }
    function pageGridEl() { return window.__mdPageHelpers.pageGridEl(); }
    function pageConfirmInput() { return window.__mdPageHelpers.pageConfirmInput(); }
    function pageFilterInput(direction) { return window.__mdPageHelpers.pageFilterInput(direction); }
    function pagePmList() { return window.__mdPageHelpers.pagePmList(); }

    /* ---- 新版（React/MUI）虚拟网格：行与单元格结构 ----
       行容器 = .translation-row，外层 [role=row] 带 aria-rowindex（1 起），
       aria-rowcount 是文档总行数；译文/原文编辑器在 [data-segment-type] 里。 */
    var __newRowsDom = null;
    function newNewRowsDom() {
      if (!__newRowsDom) __newRowsDom = window.__mdNewRowsDom.create({ page: page });
      return __newRowsDom;
    }
    function newRowsTable() { return newNewRowsDom().newRowsTable.apply(null, arguments); }
    function newRowElements() { return newNewRowsDom().newRowElements.apply(null, arguments); }
    function newRowRoleOf() { return newNewRowsDom().newRowRoleOf.apply(null, arguments); }
    function newRowIndexOf() { return newNewRowsDom().newRowIndexOf.apply(null, arguments); }
    function newRowIdOf() { return newNewRowsDom().newRowIdOf.apply(null, arguments); }
    function newRowByIndex() { return newNewRowsDom().newRowByIndex.apply(null, arguments); }
    function newRowTotal() { return newNewRowsDom().newRowTotal.apply(null, arguments); }
    function newSegmentEl() { return newNewRowsDom().newSegmentEl.apply(null, arguments); }
    function newCleanText() { return newNewRowsDom().newCleanText.apply(null, arguments); }
    function newSegmentText() { return newNewRowsDom().newSegmentText.apply(null, arguments); }
    function newRowBadges() { return newNewRowsDom().newRowBadges.apply(null, arguments); }
    function newRowStatus() { return newNewRowsDom().newRowStatus.apply(null, arguments); }
    function newHitsPanel() { return newNewRowsDom().newHitsPanel.apply(null, arguments); }
    function newSegmentSymbols(seg) { return window.__mdSymbols.segmentSymbols(seg); }
    function newSymbolChar(value) { return window.__mdSymbols.char(value); }
    function newSymbolsText(seg) { return window.__mdSymbols.text(seg); }
    function newSymbolsPlainText(seg) { return window.__mdSymbols.plainText(seg); }
    function newSegText(seg) { return window.__mdSymbols.segText(seg); }
    // 新版命中符号 → token：文本按码点解码，type=2 是 tag（tagType/inlineTagType/name/display）。
    function newSymbolsTokens(seg) { return window.__mdSymbols.tokens(seg); }
    // 命中 tag 能否全部按名字映射到当前原文 tag（严格插入前置校验）。
    function newTagPlan(srcTokens, tgtTokens) { return window.__mdSymbols.tagPlan(srcTokens, tgtTokens); }
    function newCurrentSourceTokens() {
      try {
        var view = newActiveView() || newAnyView();
        var row = view ? newViewRow(view) : null;
        var seg = row ? newSegmentEl(row, 'source') : null;
        var pm = seg && seg.querySelector ? seg.querySelector('div.ProseMirror') : null;
        var srcView = pm ? newFindView(pm) : null;
        return srcView ? newSegmentTokens(srcView) : [];
      } catch (e) { return []; }
    }
    function newSymbolsHaveTags(seg) { return window.__mdSymbols.haveTags(seg); }
    /* ---- 新版段列表（行数据 API，按范围加载）----
       POST /api/editor/projects/<prj>/docs/<doc>/rows {rowIds:[...], scope:'entireRow'}
       绕开虚拟网格：缓存连续行号，加载更多时再取下一批，不会出现行号跳跃。 */
    var __rowsRuntime = null;
    function newRowsRuntime() {
      if (!__rowsRuntime) {
        __rowsRuntime = window.__mdRowsRuntime.create({
          rowTotal: newRowTotal, rowByIndex: newRowByIndex, rowIdOf: newRowIdOf,
          symbolsPlainText: newSymbolsPlainText,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __rowsRuntime;
    }
    function newRowsApiState() { return newRowsRuntime().newRowsApiState.apply(null, arguments); }
    function newRowStatusFromMeta() { return newRowsRuntime().newRowStatusFromMeta.apply(null, arguments); }
    function newRowApiEntry() { return newRowsRuntime().newRowApiEntry.apply(null, arguments); }
    function newRowsDeps() { return newRowsRuntime().newRowsDeps.apply(null, arguments); }
    function newRowsApiStart() { return newRowsRuntime().newRowsApiStart.apply(null, arguments); }
    function newRowsApiJump() { return newRowsRuntime().newRowsApiJump.apply(null, arguments); }
    function newRowsApiList() { return newRowsRuntime().newRowsApiList.apply(null, arguments); }
    function newRefreshRowCache() { return newRowsRuntime().newRefreshRowCache.apply(null, arguments); }
    function newRowsApiReset() { return newRowsRuntime().newRowsApiReset.apply(null, arguments); }
    function newFilterState() { return newRowsRuntime().newFilterState.apply(null, arguments); }
    function newFilterSet() { return newRowsRuntime().newFilterSet.apply(null, arguments); }
    function newFilterPost() { return newRowsRuntime().newFilterPost.apply(null, arguments); }
    function newDocApiBase() { return newRowsRuntime().newDocApiBase.apply(null, arguments); }
    function newApiNamespace() { return newRowsRuntime().newApiNamespace.apply(null, arguments); }
    function newRowIdFor() { return newRowsRuntime().newRowIdFor.apply(null, arguments); }
    function newRowIdForWrite() { return newRowsRuntime().newRowIdForWrite.apply(null, arguments); }
    function newApiFetch() { return newRowsRuntime().newApiFetch.apply(null, arguments); }
    function newApiHeaders() { return newRowsRuntime().newApiHeaders.apply(null, arguments); }
    function newCommentTexts(items) {
      return window.__mdComments.texts(items);
    }
    window.__md.api.commentRanges = function (items) {
      return window.__mdComments.ranges(items || []);
    };
    // 新版段信息：上下文/原始 ID 新版接口不暴露（行 meta 只有状态字段），
    // 注释由 TranslationDocument /comments 接口按 rowId 拉取（只读）。
    var __hitsApi = null;
    function newHitsApi() {
      if (!__hitsApi) {
        __hitsApi = window.__mdHitsApi.create({
          docBase: newDocApiBase, rowId: newRowIdFor, fetch: newApiFetch,
          activeView: newActiveView, anyView: newAnyView,
          currentSourceTokens: newCurrentSourceTokens,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __hitsApi;
    }
    function newFetchHitsApi(rowNo, onFail) { return newHitsApi().fetchHits(rowNo, onFail); }
    var __newRows = null;
    function newNewRows() {
      if (!__newRows) {
        __newRows = window.__mdNewRows.create({
          rowsState: newRowsApiState, rowsList: newRowsApiList, rowsStart: newRowsApiStart,
          filterState: newFilterState, rowElements: newRowElements, rowsTable: newRowsTable,
          rowIndex: newRowIndexOf, rowId: newRowIdOf, segmentText: newSegmentText,
          segmentEl: newSegmentEl, rowBadges: newRowBadges, rowStatus: newRowStatus,
          rowTotal: newRowTotal, rowByIndex: newRowByIndex,
        });
      }
      return __newRows;
    }
    function newListRows() { return newNewRows().newListRows(); }
    function newFocusRow(row, rowNo) { return newNewRows().newFocusRow(row, rowNo); }
    function newScrollTowardRow(rowNo) { return newNewRows().newScrollTowardRow(rowNo); }
    function newTryFocusPending() { return newNewRows().newTryFocusPending(); }

    function pageEditorRows() {
      var p = page();
      if (!p) return [];
      var out = [];
      var trs = document.querySelectorAll(p.rows);
      for (var i = 0; i < trs.length; i++) {
        if (trs[i].querySelector && trs[i].querySelector(p.editorCell)) out.push(trs[i]);
      }
      return out;
    }
    function fingerprintHash(v) { return window.__mdDetect.fingerprintHash(v); }
    function newEditFlags(view) { return window.__mdDetect.newEditFlags(view); }
    function newEditorVersion() { return window.__mdDetect.newEditorVersion(); }
    function detectEditor() { return window.__mdDetect.detectEditor(); }
    var __capabilities = null;
    function newCapabilities() {
      if (!__capabilities) {
        __capabilities = window.__mdCapabilities.create({
          detect: detectEditor, page: page, oldGridCtrl: oldGridCtrl,
          pageConfirmInput: pageConfirmInput, termCore: termCore,
          pageFilterInput: pageFilterInput, rowsTable: newRowsTable,
          docBase: newDocApiBase, namespace: newApiNamespace,
          projectGuid: newProjectGuidFromUrl, anyView: newAnyView,
          activeView: newActiveView, version: newEditorVersion,
          editFlags: newEditFlags, pageEditorRows: pageEditorRows,
          pagePmList: pagePmList, rowElements: newRowElements,
          rowTotal: newRowTotal, hitsPanel: newHitsPanel,
          oldCachedRows: oldCachedRows, pageGridEl: pageGridEl, hash: fingerprintHash,
        });
      }
      return __capabilities;
    }
    window.__md.api.capabilities = function () { return newCapabilities().capabilities(); };
    window.__md.api.fingerprint = function () { return newCapabilities().pageFingerprint(); };

    var __segmentView = null;
    function newSegmentView() {
      if (!__segmentView) {
        __segmentView = window.__mdSegmentView.create({
          pagePmList: pagePmList, page: page, rowIdOf: newRowIdOf,
          rowIndexOf: newRowIndexOf, segmentEl: newSegmentEl,
          docBase: newDocApiBase, headers: newApiHeaders,
        });
      }
      return __segmentView;
    }
    function newFindView() { return newSegmentView().newFindView.apply(null, arguments); }
    function newAnyView() { return newSegmentView().newAnyView.apply(null, arguments); }
    function newActiveView() { return newSegmentView().newActiveView.apply(null, arguments); }
    function newSegmentTokens() { return newSegmentView().newSegmentTokens.apply(null, arguments); }
    function newViewRow() { return newSegmentView().newViewRow.apply(null, arguments); }
    function newReadSegment() { return newSegmentView().newReadSegment.apply(null, arguments); }
    function newTokenSymbols() { return newSegmentView().newTokenSymbols.apply(null, arguments); }
    function newPutRowSync() { return newSegmentView().newPutRowSync.apply(null, arguments); }
    function newWriteSegment() { return newSegmentView().newWriteSegment.apply(null, arguments); }

    var __oldEditor = null;
    function newOldEditor() {
      if (!__oldEditor) {
        __oldEditor = window.__mdOldEditor.create({
          page: page, oldGridCtrl: oldGridCtrl, oldCachedRows: oldCachedRows,
          segTags: segTags,
        });
      }
      return __oldEditor;
    }
    function oldActiveEditor() { return newOldEditor().oldActiveEditor(); }
    function oldActiveEditorForTarget(strict) { return newOldEditor().oldActiveEditorForTarget(strict); }
    function oldEditorRoot(ed) { return newOldEditor().oldEditorRoot(ed); }
    function oldResolveTag(ed, node) { return newOldEditor().oldResolveTag(ed, node); }
    function oldExtractTokens(root, ed) { return newOldEditor().oldExtractTokens(root, ed); }
    function oldReadSegment(strict) { return newOldEditor().oldReadSegment(strict); }
    /* ================= 统一 API ================= */
    var __pageInfo = null;
    function newPageInfo() {
      if (!__pageInfo) __pageInfo = window.__mdPageInfo.create({ detect: detectEditor, page: page });
      return __pageInfo;
    }
    window.__md.api.ping = function () { return newPageInfo().ping(); };
    window.__md.api.detect = function () { return newPageInfo().detect(); };
    window.__md.api.documentStats = function () { return newPageInfo().documentStats(); };

    // 枚举全部缓存段行（gridContentManager 数据源：行号=id+1，带原文/译文编辑器字符串/锁定/字数上限）
    var __rowListOld = null;
    function newRowListOld() {
      if (!__rowListOld) {
        __rowListOld = window.__mdRowListOld.create({
          detect: detectEditor, newListRows: newListRows, oldGridCtrl: oldGridCtrl,
          oldCachedRows: oldCachedRows, page: page,
        });
      }
      return __rowListOld;
    }
    window.__md.api.listRows = function () { return newRowListOld().listRows(); };
    var __filterWorkflow = null;
    function newFilterWorkflow() {
      if (!__filterWorkflow) {
        __filterWorkflow = window.__mdFilterWorkflow.create({
          detect: detectEditor, filterState: newFilterState, filterSet: newFilterSet,
          filterPost: newFilterPost, rowsReset: newRowsApiReset,
          pageFilterInput: pageFilterInput,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __filterWorkflow;
    }
    window.__md.api.filterReq = function (direction, s, t, r) {
      return newFilterWorkflow().filterReq(direction, s, t, r);
    };
    window.__md.api.clearFilterReq = function () { return newFilterWorkflow().clearFilterReq(); };

    // 读指定行的原文（旧版：直接扫原文格 DOM，无需激活编辑器）
    var __pageApi = null;
    function newPageApi() {
      if (!__pageApi) {
        __pageApi = window.__mdPageApi.create({
          detect: detectEditor, page: page, pageEditorRows: pageEditorRows,
          oldExtractTokens: oldExtractTokens, oldActiveEditor: oldActiveEditor,
          activeView: newActiveView, anyView: newAnyView,
          editFlags: newEditFlags, pageRules: PAGE,
        });
      }
      return __pageApi;
    }
    window.__md.api.readSource = function (rowIdx) { return newPageApi().readSource(rowIdx); };
    window.__md.api.debugState = function () { return newPageApi().debugState(); };
    window.__md.api.selectorSnapshot = function () { return newPageApi().selectorSnapshot(); };
    window.__md.api.editorState = function () { return newPageApi().editorState(); };

    // 按 rowId 找译文段视图（自动化指定行用，不依赖焦点）
    var __rowFocus = null;
    function newRowFocus() {
      if (!__rowFocus) {
        __rowFocus = window.__mdRowFocus.create({
          detect: detectEditor, pagePmList: pagePmList, findView: newFindView,
          rowsState: newRowsApiState, rowsStart: newRowsApiStart, rowsTable: newRowsTable,
          rowTotal: newRowTotal, oldGridCtrl: oldGridCtrl, oldCachedRows: oldCachedRows,
          oldRowNoOf: oldRowNoOf, rowByIndex: newRowByIndex,
          scrollToward: newScrollTowardRow, focusRow: newFocusRow,
          pageEditorRows: pageEditorRows, page: page,
          oldActiveEditor: oldActiveEditor, oldEditorRoot: oldEditorRoot,
        });
      }
      return __rowFocus;
    }
    function newFindViewByRow(rowId) { return newRowFocus().newFindViewByRow(rowId); }
    function scrollGridDown(anchor) { return newRowFocus().scrollGridDown(anchor); }
    window.__md.api.expandRows = function () { return newRowFocus().expandRows(); };
    window.__md.api.activateRow = function (rowNo) { return newRowFocus().activateRow(rowNo); };
    window.__md.api.focusSegment = function (rowIdx) { return newRowFocus().focusSegment(rowIdx); };

    /* ---- 程序化行激活：gridCtrl.moveToRow（正式接口，替代不可靠的合成点击） ----
       行模型注意：getAllCachedRows 返回 Bridge.NET List（toArray 转数组）；
       行号可能藏在 r.row.rowNumber（数字）或需从 String(r.rowNumber) 提取，兜底用 id+1。 */
    var __oldRows = null;
    function newOldRows() {
      if (!__oldRows) __oldRows = window.__mdOldRows.create({ pageGridEl: pageGridEl });
      return __oldRows;
    }
    function oldGridCtrl() { return newOldRows().oldGridCtrl(); }
    function oldCachedRows(ctrl) { return newOldRows().oldCachedRows(ctrl); }
    function oldRowNoOf(r) { return newOldRows().oldRowNoOf(r); }
    function parseTagArr(arr) { return newOldRows().parseTagArr(arr); }
    function segTags(seg) { return newOldRows().segTags(seg); }
    function findRowByNo(ctrl, rowNo) { return newOldRows().findRowByNo(ctrl, rowNo); }

    // 行 tag 数据：tags=译文段已有（面板用）；sourceTags=原文段完整序列（F9 缺失判断的数据源）
    var __tagsApi = null;
    function newTagsApi() {
      if (!__tagsApi) {
        __tagsApi = window.__mdTagsApi.create({
          detect: detectEditor, oldGridCtrl: oldGridCtrl,
          findRowByNo: findRowByNo, segTags: segTags,
        });
      }
      return __tagsApi;
    }
    window.__md.api.listTags = function (rowNo) { return newTagsApi().listTags(rowNo); };

    // 自动点进指定行（1 起）的译文段（往返测试/自动化用；人工使用时无需调用）

    // 原生确认：向 memoQ 隐藏输入框派发 Ctrl+Enter（与原生快捷键同路径）。
    // 走原生确认 = 状态流转、服务器同步、重复句段传播全是 memoQ 自己的逻辑。
    // 注意：确认后 memoQ 会把活动行跳到下一个未确认段（原生行为）。
    // 新版确认/拒绝走 HTTP 行接口（行号显式指定），不再依赖 memoQ 内部“活动行”：
    // 真机发现合成快捷键会作用在 memoQ 当前活动行上，切行后可能拒绝错行。
    // 实验结论（2026-11-26 真机）：新版页面对 JS 合成的 Ctrl/Shift+Enter
    // 不响应（isTrusted=false 或 ProseMirror 拦截），行状态不会改变。
    // 因此产品路径仍走 HTTP 行接口；本函数保留仅用于以后可信输入方案验证。
    var __rowOps = null;
    function newRowOps() {
      if (!__rowOps) {
        __rowOps = window.__mdRowOps.create({
          docBase: newDocApiBase, rowIdWrite: newRowIdForWrite, rowId: newRowIdFor,
          headers: newApiHeaders, fetch: newApiFetch, rowsState: newRowsApiState,
          rowStatus: newRowStatusFromMeta, refreshRow: newRefreshRowCache,
          rowsJump: newRowsApiJump, editFlags: newEditFlags,
          activeView: newActiveView, anyView: newAnyView, detect: detectEditor,
          pageConfirmInput: pageConfirmInput,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __rowOps;
    }
    window.__md.api.lockRow = function () { return newRowOps().api_lockRow.apply(null, arguments); };
    window.__md.api.clearRow = function () { return newRowOps().api_clearRow.apply(null, arguments); };
    window.__md.api.splitRow = function () { return newRowOps().api_splitRow.apply(null, arguments); };
    window.__md.api.joinRow = function () { return newRowOps().api_joinRow.apply(null, arguments); };
    window.__md.api.confirmSegment = function () { return newRowOps().api_confirmSegment.apply(null, arguments); };
    window.__md.api.rejectSegment = function () { return newRowOps().api_rejectSegment.apply(null, arguments); };
    window.__md.api.refreshRowCache = function () { return newRowOps().api_refreshRowCache.apply(null, arguments); };
    window.__md.api.refreshRowCacheByRow = function () { return newRowOps().api_refreshRowCacheByRow.apply(null, arguments); };
    window.__md.api.jumpToRow = function () { return newRowOps().api_jumpToRow.apply(null, arguments); };
    window.__md.api.openFindReplace = function () { return newRowOps().api_openFindReplace.apply(null, arguments); };

    var __segmentApi = null;
    function newSegmentApi() {
      if (!__segmentApi) {
        __segmentApi = window.__mdSegmentApi.create({
          detect: detectEditor, tryFocus: newTryFocusPending,
          findViewByRow: newFindViewByRow, activeView: newActiveView, anyView: newAnyView,
          readView: newReadSegment, oldRead: oldReadSegment, editFlags: newEditFlags,
          writeView: newWriteSegment, refreshRow: newRefreshRowCache, putRow: newPutRowSync,
          tokenSymbols: newTokenSymbols, rowStatus: newRowStatusFromMeta,
          symbolsText: newSymbolsText, symbolsPlain: newSymbolsPlainText,
          rowsState: newRowsApiState, oldWrite: oldWriteSegment,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __segmentApi;
    }
    window.__md.api.readSegment = function (rowId) { return newSegmentApi().readSegment(rowId); };
    window.__md.api.writeSegment = function (tokens, rowId) { return newSegmentApi().writeSegment(tokens, rowId); };

    var __previewContext = null;
    function newPreviewContext() {
      if (!__previewContext) {
        __previewContext = window.__mdPreviewContext.create({
          fetch: newApiFetch, headers: newApiHeaders, docBase: newDocApiBase,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __previewContext;
    }
    window.__md.api.previewContextReq = function () {
      return newPreviewContext().previewContextReq();
    };

    window.__md.api.parseEditorString = function (s) { return newTagsApi().parseEditorString(s); };

    /* ---- TM/TB 命中：TranslationService.GetTranslationResults（同域 fetch，异步，轮询取结果）
       实测协议（rt_tmtb4）：Row 用 {id, guid} 最小对象即可；DocInstanceId = WebTrans.Core.docInstanceId；
       响应 {Success, Value:{Hits[]}}，Hit.Type 0=TM / 1=TB，信封必查 SessionExpired */
    function apiPost(svc, body) {
      return window.__mdLegacyApi.post(svc, body);
    }

    /* ---- Ctrl+E 添加术语：列表只读；Entry 由 memoQ 原生模块初始化，用户确认后才提交 ---- */
    function termFail(kind, req, err) {
      try { __md.push(kind, { req: req, err: String(err || '未知错误').slice(0, 260) }); } catch (e) {}
    }
    function termCore() {
      var core = window.WebTrans && window.WebTrans.Core;
      if (!core) throw new Error('memoQ Core 未找到（请先打开文档）');
      return core;
    }
    function termProjectGuid(core) {
      var prj = core.projectGuid || core.projectId;
      if (!prj) {
        try { prj = new URL(location.href).searchParams.get('prj'); } catch (e) {}
      }
      if (!prj) throw new Error('项目 GUID 未找到');
      return String(prj);
    }
    // 新版编辑器没有 WebTrans.Core：项目 GUID 直接从 URL /projects/<guid>/docs/... 取。
    function newProjectGuidFromUrl() {
      try {
        var m = /\/projects\/([^/?#]+)/.exec(location.pathname || '');
        if (m && m[1]) return String(m[1]);
      } catch (e) {}
      try { return String(new URL(location.href).searchParams.get('prj') || ''); } catch (e) {}
      return '';
    }
    // 新版术语条目：优先用调用方给的语言码（TB 命中 detail.languages），
    // 否则按命中术语文本在语言层里反查；两语言层时兜底 source/target。
    function newTermLangCodes(entry, params) {
      params = params || {};
      var wantS = String(params.sourceLang || '').trim();
      var wantT = String(params.targetLang || '').trim();
      var srcText = String(params.sourceText || params.source || '').trim();
      var tgtText = String(params.targetText || params.target || '').trim();
      var layers = (entry && entry.LanguageLevelMetaInfos) || [];
      var srcLayer = wantS ? termLanguage(entry, wantS) : null;
      var tgtLayer = wantT ? termLanguage(entry, wantT) : null;
      for (var i = 0; i < layers.length; i++) {
        var texts = termLanguageTerms(layers[i]);
        if (!srcLayer && srcText && texts.indexOf(srcText) >= 0) srcLayer = layers[i];
        if (!tgtLayer && tgtText && texts.indexOf(tgtText) >= 0) tgtLayer = layers[i];
      }
      if ((!srcLayer || !tgtLayer) && layers.length === 2) {
        if (!srcLayer) srcLayer = layers[0];
        if (!tgtLayer) tgtLayer = layers[1];
      }
      return {
        src: srcLayer ? String(srcLayer.LanguageCode || '') : '',
        tgt: tgtLayer ? String(tgtLayer.LanguageCode || '') : '',
      };
    }
    // 新版页面里没有 WebTrans.Core：从 TB 命中缓存/页面全局状态里找文档语言码，
    // 找不到时由调用方退回术语库模板里的语言层顺序。
    function scanLangFields(obj, depth, out, seen) {
      if (!obj || typeof obj !== 'object' || depth > 4 || seen.indexOf(obj) >= 0) return;
      seen.push(obj);
      var keys = Object.keys(obj);
      for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        var low = key.toLowerCase();
        var val = obj[key];
        if (typeof val === 'string' && val.trim()) {
          var text = val.trim();
          var isSource = /(source|src).*lang|lang.*(source|src)/.test(low)
            || low === 'src' || low === 'source';
          var isTarget = /(target|tgt).*lang|lang.*(target|tgt)/.test(low)
            || low === 'tgt' || low === 'target';
          if (isSource && !out.src) out.src = text;
          if (isTarget && !out.tgt) out.tgt = text;
        } else if (val && typeof val === 'object' && depth < 4) {
          scanLangFields(val, depth + 1, out, seen);
        }
        if (out.src && out.tgt) return;
      }
    }
    function newDocumentLanguageCodes() {
      var cached = window.__md._docLangs;
      if (cached && cached.src && cached.tgt) return cached;
      var out = {};
      var seen = [];
      var roots = [];
      try { if (window.__md._termLangs) roots.push(window.__md._termLangs); } catch (e) {}
      var names = ['__INITIAL_STATE__', '__PRELOADED_STATE__', '__APP_STATE__',
                   '__memoqState', '__APP_CONFIG__', '__DOCUMENT_STATE__'];
      for (var i = 0; i < names.length; i++) {
        try { if (window[names[i]]) roots.push(window[names[i]]); } catch (e) {}
      }
      for (var j = 0; j < roots.length && !(out.src && out.tgt); j++) {
        scanLangFields(roots[j], 0, out, seen);
      }
      if (out.src && out.tgt) {
        try { window.__md._docLangs = out; } catch (e) {}
      }
      return out;
    }
    function newTermProjectGuidFor(params) {
      return String((params && params.projectGuid) || newProjectGuidFromUrl() || '');
    }
    var __termsApi = null;
    function newTermsApi() {
      if (!__termsApi) {
        __termsApi = window.__mdTermsApi.create({
          post: apiPost,
          model: window.__mdTermsModel,
          detectEditor: detectEditor,
          termCore: termCore,
          termProjectGuid: termProjectGuid,
          fail: termFail,
          newProjectGuidFromUrl: newProjectGuidFromUrl,
          termProjectGuidFor: newTermProjectGuidFor,
          documentLanguageCodes: newDocumentLanguageCodes,
          getEntry: termGetEntry,
          langCodes: newTermLangCodes,
          language: termLanguage,
          languageDetail: termLanguageDetail,
          metaValue: termMetaValue,
          examples: termExamples,
          primaryTerm: termPrimaryTerm,
          patchHtml: termPatchPrettyHtml,
          setMeta: termSetMeta,
          entryToGui: termEntryToGui,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __termsApi;
    }
    function termTbList() { return newTermsApi().termTbList.apply(null, arguments); }
    function termTemplateEntryGui() { return newTermsApi().termTemplateEntryGui.apply(null, arguments); }
    function termAlignQuickLayers() { return newTermsApi().termAlignQuickLayers.apply(null, arguments); }
    function termQuickAddEntry() { return newTermsApi().termQuickAddEntry.apply(null, arguments); }

    /* ---- 术语条目结构（读取 PascalCase → 提交 camelCase，均来自真实抓包） ---- */
    function termMetaList() { return window.__mdTermsModel.termMetaList.apply(null, arguments); }
    function termMetaName() { return window.__mdTermsModel.termMetaName.apply(null, arguments); }
    function termMetaValue() { return window.__mdTermsModel.termMetaValue.apply(null, arguments); }
    function termSetMeta() { return window.__mdTermsModel.termSetMeta.apply(null, arguments); }
    function termLanguage() { return window.__mdTermsModel.termLanguage.apply(null, arguments); }
    function termPrimaryTerm() { return window.__mdTermsModel.termPrimaryTerm.apply(null, arguments); }
    function termExamples() { return window.__mdTermsModel.termExamples.apply(null, arguments); }
    function termLanguageTerms() { return window.__mdTermsModel.termLanguageTerms.apply(null, arguments); }
    function termLanguageDetail() { return window.__mdTermsModel.termLanguageDetail.apply(null, arguments); }
    function termEscapeHtml() { return window.__mdTermsModel.termEscapeHtml.apply(null, arguments); }
    function termPatchPrettyHtml() { return window.__mdTermsModel.termPatchPrettyHtml.apply(null, arguments); }
    function termMetaToGui() { return window.__mdTermsModel.termMetaToGui.apply(null, arguments); }
    function termLanguageToGui() { return window.__mdTermsModel.termLanguageToGui.apply(null, arguments); }
    function termEntryToGui() { return window.__mdTermsModel.termEntryToGui.apply(null, arguments); }
    var __termsAdd = null;
    function newTermsAdd() {
      if (!__termsAdd) {
        __termsAdd = window.__mdTermsAdd.create({
          detect: detectEditor, termCore: termCore, termProjectGuid: termProjectGuid,
          fail: termFail, projectGuid: newProjectGuidFromUrl, langCodes: newTermLangCodes,
          language: termLanguage, primaryTerm: termPrimaryTerm, metaValue: termMetaValue,
          setMeta: termSetMeta, apiPost: apiPost,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __termsAdd;
    }
    function termGetEntry(tb, id, prj) { return newTermsAdd().termGetEntry(tb, id, prj); }
    window.__md.api.termAddReq = function (req, params) { return newTermsAdd().termAddReq(req, params); };
    window.__md.api.termEntryReq = function (req, params) { return newTermsAdd().termEntryReq(req, params); };
    /* 详情栏用：读回原文/译文语言层的 Definition 与术语层 Example（只读）。 */
    window.__md.api.termDetailReq = function (req, params) {
      return newTermsApi().termDetail(req, params);
    };
    window.__md.api.termEditReq = function (req, params) {
      return newTermsApi().termEdit(req, params);
    };

    /* ---- Ctrl+Q 快速添加术语 ----
       与 Ctrl+E 不同：不打开编辑浮层，直接复用旧 QTermService：
       ListServerProjectTBs → GetEmptyMetaList → AddNewEntry。
       单术语库直接加；多术语库 push term-pick-tb 让 Qt 弹选择浮窗（可记住）。
       新版没有 Core：projectGuid 从 URL 取，语言层用命中缓存/全局状态，找不到时按模板顺序。 */
    window.__md.api.termQuickAddReq = function (req, params) {
      return newTermsApi().termQuickAdd(req, params);
    };

    /* ---- 段信息：行内上下文字段 + 行注释 + 文档注释（按文档缓存一次） ---- */
    var __segmentInfo = null;
    function newSegmentInfoApi() {
      if (!__segmentInfo) {
        __segmentInfo = window.__mdSegmentInfo.create({
          detect: detectEditor, space: newApiNamespace, rowId: newRowIdFor,
          headers: newApiHeaders, fetch: newApiFetch, commentTexts: newCommentTexts,
          oldGridCtrl: oldGridCtrl, findRowByNo: findRowByNo, apiPost: apiPost,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __segmentInfo;
    }
    function newFetchSegmentInfo(rowNo) { return newSegmentInfoApi().fetchNew(rowNo); }
    window.__md.api.segmentInfo = function (rowNo) {
      return newSegmentInfoApi().segmentInfo(rowNo);
    };

    /* ---- Concordance 语词检索：直接查询当前 memoQ 项目可用的 TM ---- */
    // 新版编辑器：POST /concordance 建检索上下文 → GET /concordance?contextId=...
    // 返回 hits[{source,target,meta}]；source/target 都是 symbols，直接复用 newSymbolsTokens 映射。
    var __concordanceApi = null;
    function newConcordanceApi() {
      if (!__concordanceApi) {
        __concordanceApi = window.__mdConcordance.create({
          docBase: newDocApiBase, headers: newApiHeaders, fetch: newApiFetch,
          symbolsTokens: newSymbolsTokens, detect: detectEditor, apiPost: apiPost,
          parseTagArr: parseTagArr,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __concordanceApi;
    }
    window.__md.api.concordanceReq = function (reqId, text, direction) {
      return newConcordanceApi().req(reqId, text, direction);
    };

    var __tmHits = null;
    function newTmHits() {
      if (!__tmHits) {
        __tmHits = window.__mdTmHits.create({
          detect: detectEditor, fetchHits: newFetchHitsApi, oldGridCtrl: oldGridCtrl,
          findRowByNo: findRowByNo, apiPost: apiPost, parseTagArr: parseTagArr,
          push: function (type, payload) { try { __md.push(type, payload); } catch (e) {} },
        });
      }
      return __tmHits;
    }
    window.__md.api.tmHitsReq = function (rowNo) { return newTmHits().tmHitsReq(rowNo); };
    window.__md.api.tmHitsPoll = function () { return newTmHits().tmHitsPoll(); };

    /* ---- 旧版全段写回：token 流 → 编辑器字符串 → Convert → insertContent ----
       tag 形态：开 {id>  闭 <id}  空 <id>；{t:'newline'} 用原文 br tag 的 id（空形态） */
    function oldWriteSegment(tokens, strict) {
      var ed = oldActiveEditorForTarget(strict);
      if (!ed) return { ok: false, err: '旧版编辑器实例未找到（目标行未激活）' };
      if (ed.settings && ed.settings.isReadOnly) return { ok: false, err: '段为只读' };
      var root = oldEditorRoot(ed);
      if (!root) return { ok: false, err: '旧版编辑器根节点未找到' };
      // 也扫原文格，找 br tag 备用
      var srcRoot = null;
      try {
        var p = page();
        var cell = root.closest && (root.closest((p && p.editorCell) || '.editor-cell') || root.closest('td'));
        var row = cell && cell.parentElement;
        if (row) {
          for (var ci = 0; ci < row.children.length; ci++) {
            var other = row.children[ci].querySelector ? row.children[ci] : null;
            if (other && other !== cell && other.querySelector && !other.contains(root)) {
              var cand = other.querySelector((p && p.contentRoot) || '.content-container') || other.querySelector('[class*="content"]');
              if (cand && cand !== root) { srcRoot = cand; break; }
            }
          }
        }
      } catch (e) {}

      // 收集 tag 信息（DOM 顺序与 token 中 tag 顺序一致）
      function collectTags(rt) {
        var list = [], br = null;
        if (!rt) return { list: list, br: br };
        (function walk(node) {
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          var cls = String(node.className || '');
          if (/\btag\b/.test(cls) && /editor-char/.test(cls)) {
            var inner = node.querySelector('.tag-content');
            if (inner && inner.hasAttribute && inner.hasAttribute('data-tagid')) {
              var id = inner.getAttribute('data-tagid');
              var kind2 = /inline-close/.test(cls) ? 'close' : (/inline-empty/.test(cls) ? 'empty' : 'open');
              // 名称解析（识别 br）
              var name = (inner.textContent || '').trim();
              if (/^\d{1,3}$/.test(name) || !name) {
                var info = oldResolveTag(ed, node);
                name = info && info.name ? info.name : '';
              }
              var isBr = name === 'mq:ch';
              list.push({ id: id, kind: kind2 });
              if (isBr && !br) br = { id: id };
              return; // 不下钻 tag 内部
            }
          }
          for (var i = 0; i < node.childNodes.length; i++) walk(node.childNodes[i]);
        })(rt);
        return { list: list, br: br };
      }
      var tgt = collectTags(root);
      var src = collectTags(srcRoot);
      var brTag = tgt.br || src.br;
      // 兜底 1：段内/原文都没有 mq:ch → 查行 ITaglist（换行 = 空值 tag，定义在行的 tag 列表里）
      if (!brTag) {
        try {
          var ctrl0 = oldGridCtrl();
          if (ctrl0) {
            var ar0 = ctrl0.getActiveRow && ctrl0.getActiveRow();
            var rows0 = oldCachedRows(ctrl0);
            for (var ri = 0; ri < rows0.length; ri++) {
              if (rows0[ri].id !== (ar0 && ar0.id)) continue;
              // 换行定义优先查原文，再查译文。不能只写 target||source：
              // targetWebSegment 对象即使存在，也不保证其 ITaglist 含 mq:ch；
              // 原文的 <mq:ch val=""> 正是 memoQ 的换行定义。
              var segs0 = [rows0[ri].sourceWebSegment, rows0[ri].targetWebSegment];
              for (var si0 = 0; si0 < segs0.length && !brTag; si0++) {
                var seg0 = segs0[si0] || {};
                var il = seg0.ITaglist;
                var ilArr = il && il.toArray ? il.toArray() : (il || []);
                for (var ti2 = 0; ti2 < ilArr.length; ti2++) {
                  var tg = ilArr[ti2];
                  var tgName = tg.Name || tg.name || '';
                  var tgAttr = String(tg.AttrInfo || tg.attrInfo || '');
                  var mv = /\bval="([^"]*)"/.exec(tgAttr);
                  var tv = mv ? mv[1] : ((tg.val !== undefined && tg.val !== null) ? String(tg.val) : '');
                  if (tgName === 'mq:ch' || /\r|\n/.test(tv) || /(^|\b)br(\b|$)/i.test(tgName)) {
                    brTag = { id: String((tg.NumID !== undefined) ? tg.NumID : tg.id) };
                    break;
                  }
                }
              }
              break;
            }
          }
        } catch (e) {}
      }

      // 按 id 索引目标/原文 tag 列表（token 自带 id 时用，插入新 tag 后顺序映射会错位）
      function kindById(id) {
        var all = tgt.list.concat(src.list);
        for (var i = 0; i < all.length; i++) if (String(all[i].id) === String(id)) return all[i].kind;
        return null;
      }

      // 拼编辑器字符串
      var s = '', ti = 0;
      for (var i = 0; i < tokens.length; i++) {
        var tk = tokens[i];
        if (tk.t === 'text') { s += tk.v; continue; }
        if (tk.t === 'newline') {
          // 优先 token 自带的换行 tag id（读取时记住的），其次现场探测
          var nid = tk.id !== undefined && tk.id !== '' && tk.id !== null ? String(tk.id) : (brTag && brTag.id);
          if (!nid) return { ok: false, err: '该段没有可用换行 tag（原文无 br/空值换行 tag，行 tag 列表也没有）' };
          s += '<' + nid + '>';
          continue;
        }
        if (tk.t === 'tag') {
          // token 自带 id（读取带回 / 面板新插入）→ 直接用，不被顺序映射绑架
          if (tk.id !== undefined && tk.id !== '' && tk.id !== null) {
            var k = tk.tagKind || kindById(tk.id) || 'empty';
            if (k === 'open') s += '{' + tk.id + '>';
            else if (k === 'close') s += '<' + tk.id + '}';
            else s += '<' + tk.id + '>';
            continue;
          }
          var info = tgt.list[ti] || src.list[ti];
          ti++;
          if (!info) return { ok: false, err: 'tag 序号超出（第 ' + ti + ' 个）：新增 tag 请从 tag 面板插入（自带 id）' };
          if (info.kind === 'open') s += '{' + info.id + '>';
          else if (info.kind === 'close') s += '<' + info.id + '}';
          else s += '<' + info.id + '>';
          continue;
        }
        return { ok: false, err: '未知 token 类型 ' + tk.t };
      }
      // 探针验证：insertContent 直接吃编辑器字符串（InsertCharsOperationParams.editorString）
      // 全选用模型偏移（tag 计 1），不能用字符串长度
      try {
        if (ed.focus) ed.focus();
        var len = ed.getContentLength ? ed.getContentLength() : s.length;
        ed.selectRange({ getAboluteRange: function () { return { start: 0, end: len }; } });
        ed.insertContent(s);
        return { ok: true };
      } catch (e) {
        return { ok: false, err: 'select/insert ERR ' + e.message };
      }
    }

    // 行变化轮询（300ms）：新旧编辑器分别探测
    setInterval(function () {
      // 签出对话框自动处理：上次会话未正常签入/文档被其他会话持有时，
      // memoQ 会弹「是，签出项目」挡住整个文档打开流程，不点 grid 永远不初始化
      try {
        var p0 = page();
        var cb = p0 && p0.checkout ? document.getElementById(p0.checkout) : null;
        if (cb && !cb.__md_clicked) { cb.__md_clicked = 1; cb.click(); log('auto-clicked checkout dialog'); }
      } catch (e) {}
      var kind = detectEditor();
      var key = '';
      try {
        if (kind === 'new') {
          var v = newActiveView();
          if (v) key = 'new|' + v.state.doc.attrs.rowId;
        } else if (kind === 'old') {
          var ed = oldActiveEditor();
          if (ed && document.activeElement && pageConfirmInput()
              && document.activeElement === pageConfirmInput()) {
            // 只监听“活动行 id”，不要把光标位置/内容长度当行号。
            // 旧逻辑会让每次移动光标都触发整段重读，造成延迟、闪烁和未保存内容被覆盖的风险。
            var ctrlRow = oldGridCtrl();
            var activeRow = ctrlRow && ctrlRow.getActiveRow && ctrlRow.getActiveRow();
            if (activeRow && activeRow.id !== undefined) key = 'old|' + activeRow.id;
          }
        }
      } catch (e) {}
      if (key && key !== window.__md._lastRowKey) {
        window.__md._lastRowKey = key;
        window.__md.push('row-changed', { editor: kind, key: key });
      }
    }, 300);

    window.__md.ready = true;
    window.__md.push('bridge-ready', { url: location.href, t: Date.now() });
    log('bridge ready');

    // 会话保活：memoQ 服务器会话闲置会过期，而桌面端可能长时间挂后台不碰网络。
    // 每 5 分钟同源拉一次首页，让服务器看到会话活跃（对正式实例和往返测试实例都生效）。
    if (/memoqworld\.com$|memoqworld\.com:\d+$/.test(location.host)) {
      setInterval(function () {
        try {
          fetch(location.origin + '/memoqweb/', { method: 'GET', credentials: 'same-origin' })
            .then(function (r) { window.__md._ka = { t: Date.now(), status: r.status }; })
            .catch(function (e) { window.__md._ka = { t: Date.now(), err: String(e) }; });
        } catch (e) {}
      }, 5 * 60 * 1000);
    }
  });
})();

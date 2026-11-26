/* 段信息 / 注释：新版注释 API、旧版文档注释缓存与合并。 */
(function () {
  if (window.__mdSegmentInfo) return;

  function create(deps) {
    function fetchNew(rowNo) {
      var base = deps.space('translation');
      var rowId = deps.rowId(rowNo);
      if (!base) {
        deps.push('segment-info', { ok: true, rowNo: Number(rowNo), contextId: '',
                                    originalId: '', comments: [], commentsLoading: false,
                                    err: '新版注释 API 路径未找到' });
        return;
      }
      var headers = deps.headers();
      headers['Content-Type'] = 'application/json';
      deps.fetch(base + '/comments', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: [parseInt(rowId, 10)] }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (items) {
        if (!Array.isArray(items)) throw new Error('注释返回不是数组');
        if (String(window.__md._infoRow) !== String(rowNo)) return;  // 已切行：丢弃
        var info = { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                     comments: deps.commentTexts(items), commentsLoading: false,
                     newEditor: true };
        window.__md._info = info;
        deps.push('segment-info', info);
      }).catch(function (e) {
        if (String(window.__md._infoRow) !== String(rowNo)) return;
        var info = { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                     comments: [], commentsLoading: false, newEditor: true,
                     err: String(e.message || e).slice(0, 160) };
        window.__md._info = info;
        deps.push('segment-info', info);
      });
    }

    function segmentText(c) {
      if (c === null || c === undefined) return '';
      if (typeof c === 'string' || typeof c === 'number') return String(c).trim();
      var keys = ['Text', 'text', 'Comment', 'comment', 'Content', 'content', 'Message', 'message', 'Value', 'value'];
      for (var i = 0; i < keys.length; i++) {
        var v = c[keys[i]];
        if (typeof v === 'string' || typeof v === 'number') {
          v = String(v).trim();
          if (v) return v;
        }
      }
      return '';
    }
    function commentBelongsToRow(c, row) {
      if (!c || typeof c !== 'object') return false;
      var ids = [row && row.id, row && row.guid, row && row.originalId];
      var keys = ['RowId', 'rowId', 'RowID', 'SegmentId', 'segmentId', 'SegmentID',
                  'OriginalId', 'originalId', 'RowGuid', 'rowGuid', 'SegmentGuid', 'segmentGuid'];
      var found = false;
      for (var i = 0; i < keys.length; i++) {
        if (c[keys[i]] === undefined || c[keys[i]] === null) continue;
        found = true;
        if (ids.some(function (id) { return id !== null && id !== undefined && String(id) === String(c[keys[i]]); })) return true;
      }
      var nested = c.Row || c.row || c.Segment || c.segment;
      if (nested && typeof nested === 'object') {
        found = true;
        var nk = ['id', 'Id', 'guid', 'Guid', 'originalId', 'OriginalId'];
        for (var j = 0; j < nk.length; j++) {
          if (ids.some(function (id) { return id !== null && id !== undefined && String(id) === String(nested[nk[j]]); })) return true;
        }
      }
      // 没有行标识的条目可能是文档级备注，不能冒充当段注释。
      return false;
    }
    function docCommentKey(core) {
      var prj = core && (core.projectGuid || core.projectGUID || core.projectId);
      var doc = core && (core.docGuid || core.docGUID || core.documentGuid);
      try {
        var u = new URL(location.href);
        prj = prj || u.searchParams.get('prj');
        doc = doc || u.searchParams.get('doc');
      } catch (e) {}
      return prj && doc ? String(prj) + '|' + String(doc) : '';
    }
    function currentSegmentInfo(rowNo) {
      var ctrl = deps.oldGridCtrl();
      var row = ctrl && deps.findRowByNo(ctrl, rowNo);
      if (!row) return { ok: false, err: '行 ' + rowNo + ' 不在缓存中' };
      var cd = row.clientData || {};
      var contextId = row.contextId || row.contextID || row.ContextId || row.ContextID ||
                      cd.contextId || cd.contextID || cd.ContextId || cd.ContextID || '';
      var comments = [];
      var inline = row.rowStatus && row.rowStatus.comments;
      if (Array.isArray(inline)) {
        inline.forEach(function (c) { var t = segmentText(c); if (t) comments.push(t); });
      }
      var cache = window.__md._docComments;
      if (cache && cache.status === 'done' && Array.isArray(cache.items)) {
        cache.items.forEach(function (c) {
          if (!commentBelongsToRow(c, row)) return;
          var t = segmentText(c);
          if (t && comments.indexOf(t) < 0) comments.push(t);
        });
      }
      return { ok: true, rowNo: rowNo, contextId: String(contextId || ''),
               originalId: row.originalId === undefined || row.originalId === null ? '' : String(row.originalId),
               comments: comments, commentsLoading: !!(cache && cache.status === 'pending') };
    }
    function segmentInfo(rowNo) {
      if (deps.detect() === 'new') {
        window.__md._infoRow = rowNo;
        window.__md._info = { status: 'pending', rowNo: Number(rowNo) };
        fetchNew(rowNo);
        return { ok: true, rowNo: Number(rowNo), contextId: '', originalId: '',
                 comments: [], commentsLoading: true, newEditor: true };
      }
      if (deps.detect() !== 'old') return { ok: false, err: '段信息仅旧版支持' };
      window.__md._infoRow = rowNo;
      var core = window.WebTrans && window.WebTrans.Core;
      var key = docCommentKey(core);
      var cache = window.__md._docComments;
      if (key && (!cache || cache.key !== key)) {
        cache = window.__md._docComments = { key: key, status: 'pending', items: [] };
        var u = key.split('|');
        deps.apiPost('TranslationService/GetDocumentComments', { projectGuid: u[0], docGuid: u[1] }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || !b.Success) throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          var val = b.Value;
          cache.items = Array.isArray(val) ? val : (val && (val.Comments || val.Items || val.Rows)) || [];
          cache.status = 'done';
        }).catch(function (e) {
          cache.status = 'error'; cache.error = String(e.message || e).slice(0, 160);
        }).then(function () {
          try {
            var currentRow = window.__md._infoRow;
            if (currentRow) deps.push('segment-info', currentSegmentInfo(currentRow));
          } catch (e) {}
        });
      }
      return currentSegmentInfo(rowNo);
    };

    return { fetchNew: fetchNew, segmentInfo: segmentInfo };
  }
  window.__mdSegmentInfo = { create: create };
})();

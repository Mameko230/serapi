/* 行操作：confirm/reject/lock/split/join，刷新/跳行/查找替换入口。 */
(function () {
  if (window.__mdRowOps) return;

  function create(deps) {
    function newRowAction(rowNo, action) {
      var base = deps.docBase();
      if (!base) return { ok: false, err: '新版文档 API 未就绪' };
      var target = parseInt(rowNo, 10);
      if (!isFinite(target) || target < 1) return { ok: false, err: '行号无效' };
      var rowId = deps.rowIdWrite(target);
      if (rowId === null) {
        return { ok: false, err: '目标行未渲染，缺少 rowId，已拒绝按行号写入' };
      }
      var headers = deps.headers();
      headers['Content-Type'] = 'application/json';
      var batch = !!(deps.batchRowActions && action === 'confirm');
      var url = batch ? (base + '/rows/' + action)
                      : (base + '/rows/' + rowId + '/' + action);
      var body = batch ? { rowIds: [Number(rowId)],
                           saveToTranslationMemory: action === 'confirm',
                           autoOptions: {} }
                       : { AutoOptions: {} };
      deps.fetch(url, {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify(body),
      }).then(function (r) {
        return r.json().then(function (body) { return { status: r.status, body: body }; })
          .catch(function () { return { status: r.status, body: null }; });
      }).then(function (res) {
        if (res.status !== 200) {
          var b = res.body || {};
          throw new Error(b.detail || b.title || b.ErrorMessage || ('HTTP ' + res.status));
        }
        if (!batch) {
          var row = (res.body && (res.body.row || res.body)) || {};
          var status = (row.meta && row.meta.status) ? String(row.meta.status) : '';
          var mappedStatus = '';
          try {
            var cached = null;
            try { cached = deps.rowsState().rows[target] || null; } catch (e) {}
            mappedStatus = deps.rowStatus(
              { status: status }, cached ? !!cached.tgt : true);
          } catch (e) {}
          try { deps.refreshRow(rowId); } catch (e) {}
          deps.push('row-action-result', {
            ok: true, action: action, rowNo: target, rowId: rowId, status: status,
            mappedStatus: mappedStatus,
          });
          return;
        }
        // 原生批量 job 返回 jobId；轮询目标行拿到真实 meta.status（TR/R1/R2 阶段不同）
        var tries = 0;
        function poll() {
          tries += 1;
          var h2 = deps.headers();
          h2['Content-Type'] = 'application/json';
          deps.fetch(base + '/rows', {
            method: 'POST', credentials: 'same-origin', headers: h2,
            body: JSON.stringify({ rowIds: [Number(rowId)], scope: 'entireRow' }),
          }).then(function (r2) { return r2.json(); }).then(function (rows) {
            var row = (rows && rows[0]) || {};
            var st = (row.meta && row.meta.status) ? String(row.meta.status) : '';
            if (!st && tries < 12) { setTimeout(poll, 400); return; }
            var mapped = '';
            try {
              mapped = deps.rowStatus({ status: st }, !!(row.target && row.target.symbols
                && row.target.symbols.length));
            } catch (e) {}
            try { deps.refreshRow(rowId); } catch (e) {}
            deps.push('row-action-result', {
              ok: true, action: action, rowNo: target, rowId: rowId,
              status: st, mappedStatus: mapped,
            });
          }).catch(function (e) {
            if (tries < 12) { setTimeout(poll, 400); return; }
            deps.push('row-action-result', {
              ok: false, action: action, rowNo: target, rowId: rowId,
              err: String(e.message || e).slice(0, 200),
            });
          });
        }
        setTimeout(poll, 250);
      }).catch(function (e) {
        deps.push('row-action-result', {
          ok: false, action: action, rowNo: target, rowId: rowId,
          err: String(e.message || e).slice(0, 200),
        });
      });
      return { ok: true, pending: true, rowNo: target, rowId: rowId };
    }

    // 结构操作：lock / split / join / clear。显式 rowId，不走整段 PUT。
    function newStructuralOp(rowNo, action, body, req) {
      var rowId = deps.rowIdWrite(rowNo);
      if (rowId === null) {
        return { ok: false, err: '目标行未渲染，缺少 rowId，已拒绝结构操作' };
      }
      var flags = deps.editFlags(deps.activeView() || deps.anyView());
      if (flags.tracking) {
        return { ok: false, err: '跟踪修改开启时禁止结构写回' };
      }
      if (flags.readOnly) {
        return { ok: false, err: '当前文档为只读，禁止结构操作' };
      }
      var base = deps.docBase();
      if (!base) return { ok: false, err: '文档 API 未就绪' };
      var headers = deps.headers();
      headers['Content-Type'] = 'application/json';
      deps.fetch(base + '/rows/' + rowId + '/' + action, {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify(body || {}),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json().catch(function () { return null; });
      }).then(function (data) {
        try {
          deps.push('structural-result', {
            req: req, ok: true, action: action, rowNo: rowNo, rowId: rowId, data: data,
          });
        } catch (e) {}
      }).catch(function (e) {
        try {
          deps.push('structural-result', {
            req: req, ok: false, action: action, rowNo: rowNo, rowId: rowId,
            err: String(e.message || e).slice(0, 200),
          });
        } catch (e2) {}
      });
      return { ok: true, pending: true, action: action, rowNo: rowNo, rowId: rowId };
    }

    function api_lockRow(rowNo, lock, req) {
      return newStructuralOp(rowNo, 'lock', { lockValue: !!lock }, req);
    }
    function api_clearRow(rowNo, req) {
      return newStructuralOp(rowNo, 'clear', {}, req);
    }
    function api_splitRow(rowNo, sourceSegmentPosition, req) {
      return newStructuralOp(rowNo, 'split',
        { sourceSegmentPosition: parseInt(sourceSegmentPosition, 10) || 0 }, req);
    }
    function api_joinRow(rowNo, rowCount, req) {
      return newStructuralOp(rowNo, 'join',
        { rowCount: Math.max(1, parseInt(rowCount, 10) || 1) }, req);
    }

    function api_confirmSegment(rowNo) {
      var kind = deps.detect();
      if (kind === 'new') return newRowAction(rowNo, 'confirm');
      if (kind !== 'old') return { ok: false, err: 'confirmSegment 仅新版/旧版编辑器支持' };
      try {
        var inp = deps.pageConfirmInput();
        if (!inp) return { ok: false, err: '隐藏输入框未找到' };
        inp.focus();
        ['keydown', 'keypress', 'keyup'].forEach(function (t) {
          try {
            inp.dispatchEvent(new KeyboardEvent(t, {
              key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
              ctrlKey: true, bubbles: true, cancelable: true
            }));
          } catch (e) {}
        });
        return { ok: true };
      } catch (e) { return { ok: false, err: 'confirmSegment ERR ' + e.message }; }
    }

    function api_rejectSegment(rowNo) {
      var kind = deps.detect();
      if (kind === 'new') return newRowAction(rowNo, 'reject');
      if (kind !== 'old') return { ok: false, err: 'rejectSegment 仅新版/旧版编辑器支持' };
      try {
        var inp = deps.pageConfirmInput();
        if (!inp) return { ok: false, err: '隐藏输入框未找到' };
        inp.focus();
        ['keydown', 'keypress', 'keyup'].forEach(function (t) {
          try {
            inp.dispatchEvent(new KeyboardEvent(t, {
              key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
              shiftKey: true, bubbles: true, cancelable: true
            }));
          } catch (e) {}
        });
        return { ok: true };
      } catch (e) { return { ok: false, err: 'rejectSegment ERR ' + e.message }; }
    }

    function api_refreshRowCache(rowId) {
      return deps.refreshRow(rowId);
    }

    function api_refreshRowCacheByRow(rowNo) {
      return deps.refreshRow(deps.rowId(rowNo));
    }

    function api_jumpToRow(rowNo) {
      return deps.rowsJump(rowNo);
    }

    // 新版原生查找替换：Qt 先打开引擎浮层，再调这里合成 Ctrl+F 打开 memoQ 自己的面板。
    function api_openFindReplace() {
      try {
        if (deps.detect() !== 'new') return { ok: false, err: '查找替换仅新版支持' };
        var el = null;
        try {
          var active = document.activeElement;
          if (active && active.closest && active.closest('div.ProseMirror')) el = active;
        } catch (e) {}
        if (!el) {
          try { el = document.querySelector('div.ProseMirror'); } catch (e) {}
        }
        if (!el) el = document.body;
        var init = {
          key: 'f', code: 'KeyF', keyCode: 70, which: 70,
          ctrlKey: true, bubbles: true, cancelable: true, composed: true,
        };
        ['keydown', 'keypress', 'keyup'].forEach(function (type) {
          try { el.dispatchEvent(new KeyboardEvent(type, init)); } catch (e) {}
        });
        return { ok: true };
      } catch (e) { return { ok: false, err: 'openFindReplace ERR ' + e.message }; }
    }

    return { api_lockRow, api_clearRow, api_splitRow, api_joinRow, api_confirmSegment, api_rejectSegment, api_refreshRowCache, api_refreshRowCacheByRow, api_jumpToRow, api_openFindReplace };
  }

  window.__mdRowOps = { create: create };
})();

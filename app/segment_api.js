/* 当前段读取/写回：新版 view + 旧版 editor 适配入口。 */
(function () {
  if (window.__mdSegmentApi) return;

  function create(deps) {
    function readSegment(rowId) {
      var kind = deps.detect();
      try {
        if (kind === 'new') {
          // 切行时可能存在“滚动后行还没渲染”的挂起目标：每次读取前再尝试聚焦一次
          deps.tryFocus();
          var view = (rowId !== undefined && rowId !== null && deps.findViewByRow(rowId))
            || deps.activeView() || deps.anyView();
          if (!view) return { ok: false, err: '新版编辑器 view 未找到（先点进一个段）' };
          var r = deps.readView(view);
          r.ok = true;
          return r;
        }
        if (kind === 'old') { var r2 = deps.oldRead(rowId !== undefined && rowId !== null); return r2; }
        return { ok: false, err: '不在编辑器页面' };
      } catch (e) { return { ok: false, err: 'read ERR ' + e.message }; }
    }

    function writeSegment(tokens, rowId) {
      var kind = deps.detect();
      try {
        if (kind === 'new') {
          var view = (rowId !== undefined && rowId !== null && deps.findViewByRow(rowId))
            || deps.activeView() || deps.anyView();
          if (!view) return { ok: false, err: '新版编辑器 view 未找到' };
          if (view.state.doc.attrs.locked) return { ok: false, err: '该段已锁定' };
          var editFlags = deps.editFlags(view);
          if (editFlags.tracking) {
            return { ok: false, err: '文档已开启跟踪修改，禁止整段写回（会制造假修订）' };
          }
          if (editFlags.readOnly) {
            return { ok: false, err: '当前文档为只读，禁止写回' };
          }
          var rid = view.state.doc.attrs.rowId;
          if (rid === undefined || rid === null) {
            return { ok: false, err: '新版行 ID 未找到' };
          }
          if (rowId !== undefined && rowId !== null && String(rowId) !== String(rid)) {
            return { ok: false, err: '写入行与当前活动行不一致，已拒绝' };
          }
          var written = deps.writeView(view, tokens || []);
          if (!written || !written.ok) return written;
          if (typeof XMLHttpRequest !== 'function') {
            // 离线契约测试没有 XHR：保留旧行为，只刷新缓存，不伪装成已服务端保存。
            deps.refreshRow(rid);
            return { ok: true, pending: true };
          }
          var row = deps.putRow(rid, { side: 'target',
                                         symbols: deps.tokenSymbols(tokens || []) });
          var status = (row.meta && row.meta.status) ? String(row.meta.status) : '';
          var rowNo = (typeof row.id === 'number') ? row.id + 1 : null;
          var mapped = '';
          try { mapped = deps.rowStatus({ status: status }, true); } catch (e) {}
          var fullTgt = deps.symbolsText(row.target || {});
          // PUT 已经返回该行：直接补进段列表缓存，不再额外发一次 POST /rows。
          // 只补已在缓存窗里的行，避免空缓存被写成“只有一行”的假列表。
          try {
            var st = deps.rowsState();
            var cur = st.rows && rowNo ? st.rows[rowNo] : null;
            if (cur) {
              cur.tgt = fullTgt;
              if (row.source) cur.src = deps.symbolsPlain(row.source);
              if (row.meta && row.meta.matchRate != null) {
                cur.tmRate = Number(row.meta.matchRate) || 0;
              }
              if (mapped) cur.status = mapped;
            }
          } catch (eCache) {}
          try {
            deps.push('row-write-result', {
              ok: true, rowNo: rowNo, rowId: String(rid), status: status,
              mappedStatus: mapped, tgt: fullTgt.slice(0, 60), tgtFull: fullTgt,
            });
          } catch (e) {}
          return { ok: true, status: status, rowNo: rowNo, rowId: String(rid) };
        }
        if (kind === 'old') return deps.oldWrite(tokens || [], rowId !== undefined && rowId !== null);
        return { ok: false, err: '不在编辑器页面' };
      } catch (e) { return { ok: false, err: 'write ERR ' + e.message }; }
    }

    return { readSegment: readSegment, writeSegment: writeSegment };
  }
  window.__mdSegmentApi = { create: create };
})();

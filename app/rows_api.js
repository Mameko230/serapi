/* rows 网络分页/跳窗/单行刷新。依赖由 bridge 注入，状态模型在 rows_store.js。 */
(function () {
  if (window.__mdRowsApi) return;

  function entryOf(deps, raw) {
    return deps.entry(raw);
  }

  function start(deps, count) {
    var st = deps.state();
    if (st.fetching || st.done) return false;
    var f = deps.filterState();
    var filtered = !!(f.active && f.rowIds);
    var total = filtered ? f.rowIds.length : (deps.rowTotal() || 0);
    var startAt = st.next;
    if (total && startAt >= total) { st.done = true; return false; }
    var ids = [];
    if (filtered) {
      ids = f.rowIds.slice(startAt, startAt + (count || st.chunk));
    } else {
      var end = startAt + (count || st.chunk);
      if (total) end = Math.min(total, end);
      for (var i = startAt; i < end; i++) ids.push(i);
    }
    if (!ids.length) { st.done = true; return false; }
    var base = deps.docBase();
    if (!base) { st.error = '文档 API 路径未找到'; return false; }
    var headers = deps.headers();
    headers['Content-Type'] = 'application/json';
    var docKey = deps.path();
    st.fetching = true;
    try {
      deps.fetch(base + '/rows', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: ids, scope: 'entireRow' }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (rows) {
        if (st.doc !== docKey) return;
        if (!Array.isArray(rows)) throw new Error('行数据返回不是数组');
        var maxId = st.next;
        for (var i = 0; i < rows.length; i++) {
          var entry = entryOf(deps, rows[i]);
          if (!entry) continue;
          st.rows[entry.rowNo] = entry;
          maxId = Math.max(maxId, parseInt(entry.rowId, 10) + 1);
        }
        st.next = filtered ? startAt + ids.length : maxId;
        st.fetching = false;
        st.status = 'done';
        st.total = filtered ? total : (deps.rowTotal() || Math.max(st.total, maxId));
        if (rows.length < ids.length) st.done = true;
        deps.push('rows-updated', {
          source: 'rows-api', cached: Object.keys(st.rows).length,
        });
      }).catch(function (e) {
        if (st.doc !== docKey) return;
        st.fetching = false;
        st.error = String(e.message || e).slice(0, 160);
        st.errorAt = Date.now();
      });
    } catch (e) {
      st.fetching = false;
      st.error = String(e.message || e).slice(0, 160);
      st.errorAt = Date.now();
    }
    return true;
  }

  function jump(deps, rowNo) {
    var base = deps.docBase();
    if (!base) return { ok: false, err: '文档 API 未就绪' };
    var f = deps.filterState();
    if (f.active) return { ok: false, err: '过滤状态下暂不支持跳行' };
    var target = parseInt(rowNo, 10);
    if (!isFinite(target) || target < 1) return { ok: false, err: '行号无效' };
    var st = deps.state();
    var total = deps.rowTotal() || st.total || 0;
    var chunk = st.chunk || 100;
    var rid = target - 1;
    var startAt = Math.max(0, rid - Math.floor(chunk / 3));
    var end = startAt + chunk;
    if (total && end > total) {
      end = total;
      startAt = Math.max(0, end - chunk);
    }
    if (!total) total = end;
    var ids = [];
    for (var i = startAt; i < end; i++) ids.push(i);
    if (!ids.length) return { ok: false, err: '行号超出范围' };
    var headers = deps.headers();
    headers['Content-Type'] = 'application/json';
    var docKey = deps.path();
    st.fetching = true;
    try {
      deps.fetch(base + '/rows', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: ids, scope: 'entireRow' }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (rows) {
        if (st.doc !== docKey) return;
        if (!Array.isArray(rows)) throw new Error('行数据返回不是数组');
        st.rows = {};
        st.mode = 'window';
        st.windowStart = startAt;
        st.windowEnd = end - 1;
        st.next = end;
        st.total = total;
        st.fetching = false;
        st.status = 'done';
        st.error = '';
        st.done = !!(total && end >= total);
        for (var j = 0; j < rows.length; j++) {
          var entry = entryOf(deps, rows[j]);
          if (entry) st.rows[entry.rowNo] = entry;
        }
        deps.push('rows-updated', { source: 'jump' });
        deps.push('jump-ready', {
          rowNo: target, windowStart: startAt + 1, windowEnd: end,
        });
      }).catch(function (e) {
        if (st.doc !== docKey) return;
        st.fetching = false;
        st.error = String(e.message || e).slice(0, 160);
        st.errorAt = Date.now();
        deps.push('jump-error', { rowNo: target, err: st.error });
      });
    } catch (e) {
      st.fetching = false;
      st.error = String(e.message || e).slice(0, 160);
      st.errorAt = Date.now();
      return { ok: false, err: st.error };
    }
    return { ok: true, pending: true, windowStart: startAt + 1, windowEnd: end };
  }

  function prev(deps, count) {
    var st = deps.state();
    if (st.fetching) return false;
    if (st.mode !== 'window' || st.windowStart === undefined) return false;
    var startAt = parseInt(st.windowStart, 10) || 0;
    if (startAt <= 0) return false;
    var end = startAt;
    startAt = Math.max(0, startAt - (count || st.chunk || 100));
    var ids = [];
    for (var i = startAt; i < end; i++) ids.push(i);
    if (!ids.length) return false;
    var base = deps.docBase();
    if (!base) return false;
    var headers = deps.headers();
    headers['Content-Type'] = 'application/json';
    var docKey = deps.path();
    st.fetching = true;
    try {
      deps.fetch(base + '/rows', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: ids, scope: 'entireRow' }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (rows) {
        if (st.doc !== docKey) return;
        if (!Array.isArray(rows)) throw new Error('行数据返回不是数组');
        for (var i = 0; i < rows.length; i++) {
          var entry = entryOf(deps, rows[i]);
          if (entry) st.rows[entry.rowNo] = entry;
        }
        st.windowStart = startAt;
        st.fetching = false;
        st.status = 'done';
        st.error = '';
        deps.push('rows-updated', { source: 'rows-api-prev',
                                    cached: Object.keys(st.rows).length });
      }).catch(function (e) {
        if (st.doc !== docKey) return;
        st.fetching = false;
        st.error = String(e.message || e).slice(0, 160);
        st.errorAt = Date.now();
      });
    } catch (e) {
      st.fetching = false;
      st.error = String(e.message || e).slice(0, 160);
      st.errorAt = Date.now();
      return false;
    }
    return true;
  }

  function refresh(deps, rowId) {
    var rid = parseInt(rowId, 10);
    if (!isFinite(rid) || rid < 0) return false;
    var base = deps.docBase();
    if (!base) return false;
    var st = deps.state();
    var docKey = deps.path();
    var headers = deps.headers();
    headers['Content-Type'] = 'application/json';
    try {
      deps.fetch(base + '/rows', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify({ rowIds: [rid], scope: 'entireRow' }),
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (rows) {
        if (st.doc !== docKey || !Array.isArray(rows)) return;
        var updated = 0;
        for (var i = 0; i < rows.length; i++) {
          var entry = entryOf(deps, rows[i]);
          if (!entry) continue;
          if (!st.rows[entry.rowNo]) continue;
          st.rows[entry.rowNo] = entry;
          updated++;
        }
        if (updated) deps.push('rows-updated', { source: 'row-refresh' });
      }).catch(function () {});
    } catch (e) { return false; }
    return true;
  }

  window.__mdRowsApi = { start: start, jump: jump, prev: prev, refresh: refresh };
})();

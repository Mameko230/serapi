/* 新版 rows 缓存状态：分页窗口的纯数据部分（状态、单行映射、列表投影）。
 * 网络请求仍由 bridge 发起，模块只负责可测试的行缓存模型。 */
(function () {
  if (window.__mdRowsStore) return;

  function state() {
    var docKey = location.pathname;
    var st = window.__md._rowsApi;
    if (!st || st.doc !== docKey) {
      st = window.__md._rowsApi = {
        doc: docKey, status: 'idle', fetching: false, done: false, error: '',
        errorAt: 0, rows: {}, next: 0, total: 0, chunk: 100,
      };
    }
    return st;
  }

  function reset() {
    window.__md._rowsApi = null;
  }

  function segmentSymbols(seg) {
    if (!seg) return [];
    if (seg.symbols) return seg.symbols;
    if (seg.segment && seg.segment.symbols) return seg.segment.symbols;
    return [];
  }

  function tagSymbols(seg) {
    var out = [];
    var symbols = segmentSymbols(seg);
    for (var i = 0; i < symbols.length; i++) {
      var s = symbols[i] || {};
      if (String(s.type) === '2' || String(s.type) === 'tag' || String(s.type) === 'Tag') {
        out.push(s);
      }
    }
    return out;
  }

  function entry(raw, plainText, rowStatus) {
    var id = Number(raw && raw.id);
    if (!isFinite(id) || id < 0) return null;
    var meta = (raw && raw.meta) || {};
    var src = plainText(raw && raw.source);
    var tgt = plainText(raw && raw.target);
    return {
      rowNo: id + 1, rowId: String(id), src: src, tgt: tgt,
      locked: !!meta.isLocked, maxLen: 0,
      status: rowStatus(meta, !!tgt),
      tmRate: Number(meta.matchRate || 0) || 0,
      // 原始 source tag symbols：写回换行 tag 时直接复用原文值/类型，
      // 不从 ProseMirror attrs 重建（PM 会丢失 tagType 等字段）。
      srcTags: tagSymbols(raw && raw.source),
    };
  }

  function list(st, filteredTotal, rowTotal) {
    var out = [];
    for (var k in st.rows) {
      if (Object.prototype.hasOwnProperty.call(st.rows, k)) out.push(st.rows[k]);
    }
    out.sort(function (a, b) { return a.rowNo - b.rowNo; });
    var total = filteredTotal || st.total || rowTotal;
    var done = !!st.done || (total > 0 && st.next >= total);
    return {
      rows: out, total: total, cached: out.length,
      done: done, error: st.error || '', filtered: !!filteredTotal,
      mode: st.mode || 'prefix',
      windowStart: st.windowStart || 0, windowEnd: st.windowEnd || 0,
    };
  }

  window.__mdRowsStore = { state: state, reset: reset, entry: entry, list: list };
})();

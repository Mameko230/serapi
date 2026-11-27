/* memoQ 预览附加信息：只读解析 preview/meta + preview/html。
 * 输出每行 extras（标签/值/kind）与 speaker/maxLen；不修改页面，不把正文塞进 Qt。 */
(function () {
  if (window.__mdPreviewContext) return;

  function classify(label) {
    var s = String(label || '');
    if (/話者|送信者|speaker|character|role|キャラ/i.test(s)) return 'speaker';
    if (/注釈|コメント|comment|备注|備考/i.test(s)) return 'comment';
    if (/コンテキスト|context|文脈|シーン|上下文|场景/i.test(s)) return 'context';
    if (/字数|文字数|長さ|长度|制限|limit/i.test(s)) return 'maxLen';
    return 'other';
  }

  function firstNumber(value) {
    var m = /-?\d+(?:\.\d+)?/.exec(String(value == null ? '' : value));
    if (!m) return 0;
    var n = Number(m[0]);
    return isFinite(n) && n > 0 ? n : 0;
  }

  function parseExtras(table) {
    var extras = [];
    var others = table.querySelectorAll('tr.other');
    for (var i = 0; i < others.length; i++) {
      var tr = others[i];
      var leftEl = tr.querySelector('td.left');
      var rightEl = tr.querySelector('td.right');
      var label = String((leftEl && leftEl.textContent) || '').replace(/\s+/g, ' ').trim();
      var value = String((rightEl && rightEl.textContent) || '').replace(/\s+/g, ' ').trim();
      if (!label && !value) continue;
      var kind = classify(label);
      extras.push({ label: label, value: value, kind: kind,
                    maxLen: kind === 'maxLen' ? firstNumber(value) : 0 });
    }
    var speaker = [];
    var maxLen = 0;
    for (var j = 0; j < extras.length; j++) {
      if (extras[j].kind === 'speaker' && extras[j].value) speaker.push(extras[j].value);
      if (extras[j].kind === 'maxLen' && extras[j].maxLen > maxLen) maxLen = extras[j].maxLen;
    }
    return { extras: extras, speaker: speaker.join(' / '), maxLen: maxLen };
  }

  function create(deps) {
    function load() {
      var docKey = location.pathname;
      var old = window.__md._previewCtx;
      if (old && old.doc === docKey && old.status === 'done') {
        deps.push('preview-context', { ok: true, cached: true, rows: old.rows });
        return { ok: true, cached: true };
      }
      if (old && old.doc === docKey && old.status === 'pending') {
        return { ok: true, pending: true };
      }
      window.__md._previewCtx = { doc: docKey, status: 'pending', rows: [] };
      var editorBase = deps.docBase && deps.docBase();
      if (!editorBase) {
        window.__md._previewCtx.status = 'error';
        deps.push('preview-context', { ok: false, rows: [], err: '文档 API 路径未找到' });
        return { ok: false, err: '文档 API 路径未找到' };
      }
      var transBase = editorBase.replace('/api/editor/', '/api/translation/');
      var headers = deps.headers ? deps.headers() : {};
      headers['Content-Type'] = 'application/json';
      var metaUrl = transBase + '/preview/meta';
      var htmlUrl = transBase + '/preview/html/doc0.htmlp';
      Promise.all([
        deps.fetch(metaUrl, { headers: headers }).then(function (r) {
          if (!r.ok) throw new Error('preview/meta HTTP ' + r.status);
          return r.json();
        }),
        deps.fetch(htmlUrl, { headers: headers }).then(function (r) {
          if (!r.ok) throw new Error('preview/html HTTP ' + r.status);
          return r.text();
        }),
      ]).then(function (out) {
        var meta = out[0];
        var html = out[1];
        var metaRow = Array.isArray(meta) ? meta[0] : (meta || {});
        var files = (metaRow && metaRow.files) || [];
        var f0 = files[0] || {};
        var map = f0.rowIdsByStructuralIds || {};
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var tables = doc.querySelectorAll('table');
        var rows = [];
        var seen = {};
        for (var i = 0; i < tables.length; i++) {
          var t = tables[i];
          var span = t.querySelector('span[data-labIdx]');
          var labIdx = span ? parseInt(span.getAttribute('data-labIdx'), 10) : i;
          if (!isFinite(labIdx)) labIdx = i;
          var rowIds = map[String(labIdx)];
          if (!Array.isArray(rowIds) || !rowIds.length) {
            if (!map[String(labIdx)]) {
              // 映射缺失时按预览顺序兜底（只影响显示，不影响写回）。
              rowIds = [labIdx];
            }
          }
          var parsed = parseExtras(t);
          for (var k = 0; k < rowIds.length; k++) {
            var rowNo = Number(rowIds[k]) + 1;
            if (!isFinite(rowNo) || rowNo <= 0 || seen[rowNo]) continue;
            seen[rowNo] = true;
            rows.push({
              rowNo: rowNo,
              labIdx: labIdx,
              sourcecell: span ? String(span.getAttribute('sourcecell') || '') : '',
              extras: parsed.extras,
              speaker: parsed.speaker,
              maxLen: parsed.maxLen,
            });
          }
        }
        rows.sort(function (a, b) { return a.rowNo - b.rowNo; });
        window.__md._previewCtx = { doc: docKey, status: 'done', rows: rows };
        deps.push('preview-context', { ok: true, rows: rows });
      }).catch(function (e) {
        window.__md._previewCtx = { doc: docKey, status: 'error', rows: [] };
        deps.push('preview-context', {
          ok: false, rows: [], err: String(e && e.message ? e.message : e).slice(0, 180),
        });
      });
      return { ok: true, pending: true };
    }

    return { previewContextReq: function () { return load(); } };
  }

  window.__mdPreviewContext = { create: create };
})();

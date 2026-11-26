/* 实时 QA 纯规则引擎：输入 token 流，输出段内警告；不依赖 DOM、不写页面。 */
(function () {
  if (window.__mdLint) return;

  var RULE_LABELS = {
    digits: '数字', tags: 'Tag', width: '全半角', terms: '术语', lineLength: '行长',
  };

  function plain(tokens, keepNewline) {
    var out = '';
    for (var i = 0; i < (tokens || []).length; i++) {
      var t = tokens[i] || {};
      if (t.t === 'text') out += String(t.v == null ? '' : t.v);
      else if (t.t === 'newline') out += keepNewline ? '\n' : ' ';
      else if (t.t === 'tag') out += '\uFFFC';
    }
    return out;
  }

  function lineTexts(tokens) {
    var lines = [''];
    for (var i = 0; i < (tokens || []).length; i++) {
      var t = tokens[i] || {};
      if (t.t === 'newline') { lines.push(''); continue; }
      if (t.t === 'text') {
        var parts = String(t.v == null ? '' : t.v).split('\n');
        for (var j = 0; j < parts.length; j++) {
          if (j) lines.push('');
          lines[lines.length - 1] += parts[j];
        }
      }
    }
    return lines;
  }

  function normalizeDigits(s) {
    return String(s || '').replace(/[０-９]/g, function (ch) {
      return String.fromCharCode(ch.charCodeAt(0) - 0xFEE0);
    });
  }

  function digitRuns(s) {
    var m = normalizeDigits(s).match(/\d+/g) || [];
    return m;
  }

  function tagKey(t) {
    var kind = t.tagKind || t.kind || 'empty';
    var id = t.id;
    if (id === undefined || id === null || id === '') {
      return 'name:' + String(t.name || t.display || '') + ':' + kind;
    }
    return 'id:' + String(id) + ':' + kind;
  }

  function tagCounts(tokens) {
    var map = {}, order = [];
    for (var i = 0; i < (tokens || []).length; i++) {
      var t = tokens[i];
      if (!t || t.t !== 'tag') continue;
      var k = tagKey(t);
      if (!map[k]) { map[k] = { key: k, count: 0, token: t }; order.push(k); }
      map[k].count++;
    }
    return { map: map, order: order };
  }

  function weightedLength(s) {
    var n = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      n += (c >= 0x20 && c <= 0x7E) ? 0.5 : 1;
    }
    return n;
  }

  function termText(hit, side) {
    if (!hit || typeof hit !== 'object') return '';
    if (side === 'source') return String(hit.source || hit.s || hit.SourceDisplayText || '').trim();
    return String(hit.target || hit.t || hit.TargetDisplayText || '').trim();
  }

  function analyze(input) {
    input = input || {};
    var rules = input.rules || {};
    var opts = input.options || {};
    var src = input.source || [];
    var tgt = input.target || [];
    var warnings = [];
    var srcLines = lineTexts(src);
    var tgtLines = lineTexts(tgt);
    var srcPlain = plain(src, false);
    var tgtPlain = plain(tgt, false);

    function enabled(name) { return rules[name] !== false; }
    function add(rule, line, message, extra) {
      var w = { rule: rule, label: RULE_LABELS[rule] || rule, line: Math.max(0, line || 0),
                message: message };
      if (extra) for (var k in extra) if (extra[k] !== undefined) w[k] = extra[k];
      warnings.push(w);
    }

    /* 1. 数字一致性：按多重集合比较，保留原文/译文各自缺失与多余。 */
    if (enabled('digits')) {
      var dOpt = opts.digits || {};
      var minLen = Math.max(1, parseInt(dOpt.minLength || 1, 10) || 1);
      var srcNums = digitRuns(srcPlain).filter(function (x) { return x.length >= minLen; });
      var tgtNums = digitRuns(tgtPlain).filter(function (x) { return x.length >= minLen; });
      var srcCount = {}, tgtCount = {};
      srcNums.forEach(function (x) { srcCount[x] = (srcCount[x] || 0) + 1; });
      tgtNums.forEach(function (x) { tgtCount[x] = (tgtCount[x] || 0) + 1; });
      Object.keys(srcCount).forEach(function (num) {
        var need = srcCount[num] - (tgtCount[num] || 0);
        if (need > 0) add('digits', 0, '原文数字 “' + num + '” 在译文中缺少 ' + need + ' 处', { number: num });
      });
      Object.keys(tgtCount).forEach(function (num) {
        var extra = tgtCount[num] - (srcCount[num] || 0);
        if (extra > 0) add('digits', 0, '译文多出数字 “' + num + '” ' + extra + ' 处', { number: num });
      });
    }

    /* 2. Tag 差额：按 (id, kind) 计数；原文有、译文无 = 缺，反之 = 多。 */
    if (enabled('tags')) {
      var sc = tagCounts(src), tc = tagCounts(tgt);
      sc.order.forEach(function (k) {
        var a = sc.map[k].count, b = (tc.map[k] || { count: 0 }).count;
        if (a > b) {
          var t = sc.map[k].token || {};
          add('tags', 0, '缺少 tag ' + (t.name || t.display || '#' + (t.id || '?')) + '（' + (a - b) + ' 个）',
              { tag: t.name || '', tagId: t.id });
        }
      });
      tc.order.forEach(function (k) {
        var a = (sc.map[k] || { count: 0 }).count, b = tc.map[k].count;
        if (b > a) {
          var t2 = tc.map[k].token || {};
          add('tags', 0, '多出 tag ' + (t2.name || t2.display || '#' + (t2.id || '?')) + '（' + (b - a) + ' 个）',
              { tag: t2.name || '', tagId: t2.id });
        }
      });
    }

    /* 3. 全半角混用：同一译文行内数字同时出现半角与全角。 */
    if (enabled('width')) {
      var wOpt = opts.width || {};
      if (wOpt.checkDigits !== false) {
        for (var li = 0; li < tgtLines.length; li++) {
          var line = tgtLines[li];
          if (/[0-9]/.test(line) && /[０-９]/.test(line)) {
            add('width', li, '译文同一行混用全角/半角数字', { lineText: line.slice(0, 60) });
          }
        }
      }
      if (wOpt.checkPunctuation) {
        for (var pi = 0; pi < tgtLines.length; pi++) {
          if (/[\u3040-\u30ff\u4e00-\u9fff][,!.?]/.test(tgtLines[pi])) {
            add('width', pi, '日中文本后使用了半角标点', { lineText: tgtLines[pi].slice(0, 60) });
          }
        }
      }
    }

    /* 4. TB 术语违例：只检查带目标术语的 TB 命中；原文包含、译文不包含才报。 */
    if (enabled('terms')) {
      var terms = input.terms || [];
      var seen = {};
      for (var ti = 0; ti < terms.length; ti++) {
        var hit = terms[ti] || {};
        var sTerm = termText(hit, 'source');
        var tTerm = termText(hit, 'target');
        if (!sTerm || !tTerm) continue;
        if (srcPlain.indexOf(sTerm) < 0) continue;
        if (tgtPlain.indexOf(tTerm) >= 0) continue;
        var key = sTerm + '\u0000' + tTerm;
        if (seen[key]) continue;
        seen[key] = 1;
        add('terms', 0, '术语未采用：' + sTerm + ' → ' + tTerm, { sourceTerm: sTerm, targetTerm: tTerm });
      }
    }

    /* 5. 行长超限：与现有字数限制联动，不重复造状态。 */
    if (enabled('lineLength')) {
      var lOpt = opts.lineLength || {};
      var lineLimit = Number(input.lineLimit || 0);
      var maxLines = parseInt(input.maxLines || 0, 10) || 0;
      var weighted = lOpt.weighted !== false;
      for (var lj = 0; lj < tgtLines.length; lj++) {
        var wLen = weighted ? weightedLength(tgtLines[lj]) : tgtLines[lj].length;
        if (lineLimit > 0 && wLen > lineLimit) {
          add('lineLength', lj, '第 ' + (lj + 1) + ' 行超长：' + fmt(wLen) + ' / ' + fmt(lineLimit), { length: wLen });
        }
      }
      if (maxLines > 0 && tgtLines.length > maxLines) {
        add('lineLength', 0, '行数超限：' + tgtLines.length + ' / ' + maxLines, { lines: tgtLines.length });
      }
    }

    warnings.sort(function (a, b) { return a.line - b.line || a.rule.localeCompare(b.rule); });
    var counts = {};
    warnings.forEach(function (w) { counts[w.rule] = (counts[w.rule] || 0) + 1; });
    return { ok: true, version: 1, warnings: warnings, counts: counts,
             total: warnings.length, sourceLines: srcLines.length, targetLines: tgtLines.length };
  }

  function fmt(n) { return Number(n).toFixed(1).replace(/\.0$/, ''); }

  window.__mdLint = { analyze: analyze, ruleLabels: RULE_LABELS };
})();

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

  function attrSignature(value) {
    if (value === null || value === undefined) return '';
    if (Array.isArray(value)) {
      return value.map(function (a) {
        a = a || {};
        return String(a.name || '') + '=' + String(a.value === undefined ? '' : a.value);
      }).sort().join('&');
    }
    if (typeof value === 'object') {
      return Object.keys(value).sort().map(function (k) {
        var v = value[k];
        return k + '=' + String(v && typeof v === 'object'
          ? (v.value === undefined ? '' : v.value) : v);
      }).join('&');
    }
    return String(value);
  }

  function tagDisplayInfo(t) {
    if (!t) return { no: '', value: '', name: '' };
    if (t.t === 'newline') return { no: '', value: '', name: 'mq:ch' };
    var attrs = t.attrs || {};
    var raw = t.raw || {};
    function firstValue(container) {
      if (!container) return '';
      if (Array.isArray(container)) {
        for (var i = 0; i < container.length; i++) {
          var item = container[i] || {};
          var n = String(item.name || '').toLowerCase();
          if (n === 'val') return String(item.value === undefined ? '' : item.value);
        }
        for (var j = 0; j < container.length; j++) {
          var it = container[j] || {};
          if (String(it.name || '').toLowerCase() === 'displaytext') {
            return String(it.value === undefined ? '' : it.value);
          }
        }
        return '';
      }
      if (typeof container === 'object') {
        var keys = Object.keys(container);
        for (var k = 0; k < keys.length; k++) {
          if (keys[k].toLowerCase() === 'val') {
            var v = container[keys[k]];
            return String(v && typeof v === 'object'
              ? (v.value === undefined ? '' : v.value) : v);
          }
        }
      }
      return '';
    }
    var no = attrs.output !== undefined ? attrs.output
           : (t.output !== undefined ? t.output
             : (raw.output !== undefined ? raw.output : (t.id !== undefined ? t.id : '')));
    var value = firstValue(attrs.attributes !== undefined ? attrs.attributes : raw.attributes);
    if (!value) {
      var display = attrs.display !== undefined ? attrs.display : raw.display;
      value = display && typeof display === 'object'
        ? String(display.text || '') : String(display || (t.display || ''));
    }
    return {
      no: (no === null || no === undefined || no === '') ? '' : String(no),
      value: String(value || ''),
      name: String(t.name || attrs.name || raw.name || ''),
    };
  }

  function tagKey(t) {
    // memoQ 新版 tag 的 NumID 是按段分配的，源/译可能不同；QA 只比较
    // 标签名 + 类型 + 属性值，避免把“编号不同”误报成缺 tag。
    if (t.t === 'newline') return 'name:mq:ch:newline';
    var attrs = t.attrs || {};
    var raw = t.raw || {};
    var name = String(t.name || attrs.name || raw.name || t.display || '');
    var tagType = (attrs.tagType !== undefined ? attrs.tagType
                  : (raw.tagType !== undefined ? raw.tagType : (t.tagType || '')));
    var inline = (attrs.inlineTagType !== undefined ? attrs.inlineTagType
                 : (raw.inlineTagType !== undefined ? raw.inlineTagType : ''));
    var attributes = attrs.attributes !== undefined ? attrs.attributes
                   : (raw.attributes !== undefined ? raw.attributes : '');
    var display = attrs.display !== undefined ? attrs.display : raw.display;
    var dispText = display && typeof display === 'object'
      ? String(display.text || '') : String(display || '');
    var kind = String(t.tagKind || t.kind || attrs.tagKind || raw.tagKind || '');
    return 'name:' + name + ':' + String(tagType) + ':' + String(inline)
      + ':' + kind + ':' + attrSignature(attributes) + ':' + dispText;
  }

  function tagCounts(tokens) {
    var map = {}, order = [];
    for (var i = 0; i < (tokens || []).length; i++) {
      var t = tokens[i];
      if (!t || (t.t !== 'tag' && t.t !== 'newline')) continue;
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
          var info = tagDisplayInfo(t);
          var isNewline = t.t === 'newline' || String(info.name || t.name || '') === 'mq:ch';
          // 换行 tag 的视觉/原生行数一致时，不再因 token 表示差异报假警。
          if (isNewline && srcLines.length === tgtLines.length) return;
          add('tags', 0, isNewline ? '行数不相等'
                : '缺少 tag ' + (t.name || t.display || '#' + (t.id || '?')) + '（' + (a - b) + ' 个）',
              { tag: t.name || '', tagId: t.id, tagNo: info.no, tagValue: info.value,
                tagMissing: true, tagCount: a - b, tagNewline: isNewline });
        }
      });
      tc.order.forEach(function (k) {
        var a = (sc.map[k] || { count: 0 }).count, b = tc.map[k].count;
        if (b > a) {
          var t2 = tc.map[k].token || {};
          var info2 = tagDisplayInfo(t2);
          var isNewline2 = t2.t === 'newline' || String(info2.name || t2.name || '') === 'mq:ch';
          if (isNewline2 && srcLines.length === tgtLines.length) return;
          add('tags', 0, isNewline2 ? '行数不相等'
                : '多出 tag ' + (t2.name || t2.display || '#' + (t2.id || '?')) + '（' + (b - a) + ' 个）',
              { tag: t2.name || '', tagId: t2.id, tagNo: info2.no, tagValue: info2.value,
                tagMissing: false, tagCount: b - a, tagNewline: isNewline2 });
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
      var rowLimit = Number(input.rowLimit || 0);
      var maxLines = parseInt(input.maxLines || 0, 10) || 0;
      var weighted = lOpt.weighted !== false;
      for (var lj = 0; lj < tgtLines.length; lj++) {
        var wLen = weighted ? weightedLength(tgtLines[lj]) : tgtLines[lj].length;
        if (lineLimit > 0 && wLen > lineLimit) {
          add('lineLength', lj, '第 ' + (lj + 1) + ' 行超长：' + fmt(wLen) + ' / ' + fmt(lineLimit), { length: wLen });
        }
      }
      if (rowLimit > 0) {
        var totalLen = 0;
        for (var rj = 0; rj < tgtLines.length; rj++) {
          totalLen += weighted ? weightedLength(tgtLines[rj]) : tgtLines[rj].length;
        }
        if (totalLen > rowLimit) {
          add('lineLength', 0, '整段字数超限：' + fmt(totalLen) + ' / ' + fmt(rowLimit),
              { length: totalLen });
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

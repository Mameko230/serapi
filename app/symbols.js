/* memoQ symbols → 文本 / token。纯函数模块，不依赖 DOM，桥接层与离线契约测试共用。 */
(function () {
  if (window.__mdSymbols) return;

  function segmentSymbols(seg) {
    if (!seg) return [];
    if (seg.symbols) return seg.symbols;
    if (seg.segment && seg.segment.symbols) return seg.segment.symbols;
    return [];
  }

  function symbolChar(value) {
    var n = null;
    if (typeof value === 'number') n = value;
    else if (typeof value === 'string' && /^\d+$/.test(value) && value.length <= 7) {
      n = parseInt(value, 10);
    }
    if (n !== null && isFinite(n)) {
      try { return String.fromCodePoint(n); } catch (e) {}
    }
    return String(value == null ? '' : value);
  }

  function text(seg) {
    var symbols = segmentSymbols(seg);
    var out = [];
    for (var i = 0; i < symbols.length; i++) {
      out.push(symbolChar((symbols[i] || {}).value));
    }
    return out.join('');
  }

  function plainText(seg) {
    var symbols = segmentSymbols(seg);
    var out = [];
    for (var i = 0; i < symbols.length; i++) {
      var s = symbols[i] || {};
      var type = s.type;
      if (type === 1 || type === 'text' || type === 'Text') {
        out.push(symbolChar(s.value));
      }
    }
    return out.join('');
  }

  function segText(seg) {
    if (seg && typeof seg.text === 'string' && seg.text) return seg.text;
    return text(seg);
  }

  function tokens(seg) {
    var symbols = segmentSymbols(seg);
    var out = [];
    var buf = '';
    var flush = function () {
      if (buf) { out.push({ t: 'text', v: buf }); buf = ''; }
    };
    for (var i = 0; i < symbols.length; i++) {
      var s = symbols[i] || {};
      var type = String(s.type);
      if (type === '2') {
        flush();
        var disp = (s.display && typeof s.display === 'object')
          ? String(s.display.text == null ? '' : s.display.text)
          : String(s.display == null ? '' : s.display);
        var inline = String(s.inlineTagType == null ? '' : s.inlineTagType);
        var tagType = (inline === '2') ? 'inline-self-closed' : 'inline-closed';
        out.push({
          t: 'tag', tagKind: 'empty', name: String(s.name || ''),
          display: disp, tagType: tagType,
          attrs: { type: tagType, name: String(s.name || ''),
                   isSpecial: !!(s.display && s.display.isSpecial),
                   displayText: disp },
          raw: s,
        });
      } else if (type === '1' || type === 'text') {
        buf += symbolChar(s.value);
      } else {
        buf += symbolChar(s.value);
      }
    }
    flush();
    return out;
  }

  function haveTags(seg) {
    var symbols = segmentSymbols(seg);
    for (var i = 0; i < symbols.length; i++) {
      var type = symbols[i] && symbols[i].type;
      if (type !== 1 && type !== 'text' && type !== 'Text') return true;
    }
    return false;
  }

  function tagPlan(srcTokens, tgtTokens) {
    var have = {}, need = {};
    var count = function (list, bucket) {
      for (var i = 0; i < list.length; i++) {
        var t = list[i] || {};
        if (t.t !== 'tag') continue;
        var name = String(t.name || '');
        bucket[name] = (bucket[name] || 0) + 1;
      }
    };
    count(srcTokens || [], have);
    count(tgtTokens || [], need);
    for (var name in need) {
      if (!Object.prototype.hasOwnProperty.call(need, name)) continue;
      if (need[name] > (have[name] || 0)) return false;
    }
    return true;
  }

  window.__mdSymbols = {
    segmentSymbols: segmentSymbols,
    char: symbolChar,
    text: text,
    plainText: plainText,
    segText: segText,
    tokens: tokens,
    haveTags: haveTags,
    tagPlan: tagPlan,
  };
})();

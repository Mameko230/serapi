/* 旧版 listTags 与编辑器字符串解析。 */
(function () {
  if (window.__mdTagsApi) return;
  function create(deps) {
    function listTags(rowNo) {
      try {
        var kind = deps.detect();
        if (kind === 'new') {
          var seg = deps.readCurrent ? deps.readCurrent() : null;
          if (!seg || !seg.ok) return { ok: false, err: '当前段尚未读取' };
          function tagToken(tk) {
            if (!tk || tk.t !== 'tag') return null;
            return {
              t: 'tag', id: tk.id == null ? '' : String(tk.id),
              kind: tk.tagKind || tk.kind || (tk.attrs && tk.attrs.tagKind) || 'empty',
              name: String(tk.name || (tk.attrs && tk.attrs.name) || ''),
              display: String(tk.display || (tk.attrs && tk.attrs.displayText) || ''),
              tagType: String(tk.tagType || (tk.attrs && tk.attrs.type) || ''),
              attrs: tk.attrs || null,
            };
          }
          function tagsOf(tokens) {
            var out = [];
            for (var i = 0; i < (tokens || []).length; i++) {
              var one = tagToken(tokens[i]);
              if (one) out.push(one);
            }
            return out;
          }
          return { ok: true, tags: tagsOf(seg.tokens), sourceTags: tagsOf(seg.srcTokens) };
        }
        if (kind !== 'old') return { ok: false, err: 'listTags 仅新版/旧版支持' };
        var ctrl = deps.oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var row = deps.findRowByNo(ctrl, rowNo);
        if (!row) return { ok: false, err: '行 ' + rowNo + ' 不在缓存中' };
        return { ok: true,
                 tags: deps.segTags(row.targetWebSegment),
                 sourceTags: deps.segTags(row.sourceWebSegment) };
      } catch (e) { return { ok: false, err: 'listTags ERR ' + e.message }; }
    }

    function parseEditorString(s) {
      var tokens = [], re = /(\{\d+>|\<\d+\}|\<\d+\>)/g, last = 0, m;
      s = String(s == null ? '' : s);
      while ((m = re.exec(s))) {
        if (m.index > last) tokens.push({ t: 'text', v: s.slice(last, m.index) });
        var code = m[0], id = /\d+/.exec(code)[0];
        tokens.push({ t: 'tag', id: id,
          tagKind: code.charAt(0) === '{' ? 'open' : (code.charAt(code.length - 1) === '}' ? 'close' : 'empty') });
        last = m.index + code.length;
      }
      if (last < s.length) tokens.push({ t: 'text', v: s.slice(last) });
      return tokens;
    }
    

    return { listTags, parseEditorString };
  }
  window.__mdTagsApi = { create: create };
})();

/* 评论数据：HTTP 注释 → 纯文本 + 锚点范围。纯函数模块，便于只读展示与契约测试。 */
(function () {
  if (window.__mdComments) return;

  function texts(items) {
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var c = items[i] || {};
      var t = '';
      if (typeof c === 'string') t = c;
      else if (typeof c.text === 'string') t = c.text;
      else if (typeof c.commentText === 'string') t = c.commentText;
      else if (typeof c.content === 'string') t = c.content;
      else if (typeof c.message === 'string') t = c.message;
      else if (c.comment && typeof c.comment.text === 'string') t = c.comment.text;
      if (t && t.trim()) out.push(t.trim());
    }
    return out;
  }

  // HTTP: { commentId, range: { start, length }, byMe }
  // 插件: { from, to, commentId, own }
  function ranges(items) {
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var c = items[i] || {};
      var r = c.range;
      if (!r || typeof r.start !== 'number' || typeof r.length !== 'number') continue;
      if (r.length <= 0) continue;
      out.push({
        from: r.start,
        to: r.start + r.length,
        commentId: String(c.commentId == null ? '' : c.commentId),
        own: !!c.byMe,
      });
    }
    return out;
  }

  window.__mdComments = { texts: texts, ranges: ranges };
})();

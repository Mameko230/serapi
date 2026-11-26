/* 旧版行缓存/行号/tag 解析。 */
(function () {
  if (window.__mdOldRows) return;
  function create(deps) {
    function oldGridCtrl() {
      try {
        var el = deps.pageGridEl();
        if (!el || !window.angular) return null;
        var sc = window.angular.element(el).scope();
        return (sc && sc.ctrl) || null;
      } catch (e) { return null; }
    }
    function oldCachedRows(ctrl) {
      try {
        var rows = ctrl.gridContentManager && ctrl.gridContentManager.getAllCachedRows();
        if (!rows) return [];
        if (Array.isArray(rows)) return rows;
        if (typeof rows.toArray === 'function') return rows.toArray();
        if (typeof rows.getEnumerator === 'function') {
          var en = rows.getEnumerator(), r = [];
          while (en.moveNext()) r.push(en.getCurrent());
          return r;
        }
      } catch (e) {}
      return [];
    }
    function oldRowNoOf(r) {
      // 已探明：getAllCachedRows 返回原始行数据，无 rowNumber；id = 显示行号 - 1（moveToRow 验证过）
      try { if (typeof r.id === 'number') return r.id + 1; } catch (e) {}
      try { if (r.row && typeof r.row.rowNumber === 'number') return r.row.rowNumber; } catch (e) {}
      try {
        var m = /(\d+)/.exec(String(r.rowNumber));
        if (m) return parseInt(m[1], 10);
      } catch (e) {}
      try { if (typeof r.rowNumber === 'number') return r.rowNumber; } catch (e) {}
      return null;
    }

    // ITaglist 条目解析（探针确认的真实结构）：
    // PascalCase — NumID / Type(0开 1闭 2空) / Name / AttrInfo("displaytext=.. val=..") / TextPosition
    function parseTagArr(arr) {
      var tags = [];
      for (var j = 0; j < arr.length; j++) {
        var t = arr[j];
        var ty = (t.Type !== undefined) ? t.Type : t.type;
        var kindName = (ty === 0 || ty === 'Open' || ty === 'open') ? 'open'
                     : (ty === 1 || ty === 'Close' || ty === 'close') ? 'close' : 'empty';
        var attr = String(t.AttrInfo || t.attrInfo || '');
        var mDisp = /displaytext="([^"]*)"/.exec(attr);
        var mVal = /\bval="([^"]*)"/.exec(attr);
        var rawVal = (t.val !== undefined && t.val !== null) ? String(t.val) : '';
        tags.push({
          id: String((t.NumID !== undefined) ? t.NumID : t.id),
          kind: kindName,
          name: t.Name || t.name || '',
          display: (mDisp ? mDisp[1] : '') || t.displayText || t.DisplayText || '',
          val: mVal ? mVal[1] : rawVal,
          attrs: attr,          // 完整 AttrInfo（长显用：mq:ch val=" " 风格）
          pos: (t.TextPosition !== undefined) ? t.TextPosition : (t.textPosition || 0)
        });
      }
      tags.sort(function (a, b) { return a.pos - b.pos; });  // 按原文位置排序 = 插入顺序
      return tags;
    }
    function segTags(seg) {
      var list = seg && seg.ITaglist;
      var arr = list && list.toArray ? list.toArray() : (list || []);
      return parseTagArr(arr);
    }
    // 找行（1 起显示行号）
    function findRowByNo(ctrl, rowNo) {
      var rows = oldCachedRows(ctrl);
      for (var i = 0; i < rows.length; i++) {
        if (oldRowNoOf(rows[i]) === rowNo) return rows[i];
      }
      return null;
    }

    return { oldGridCtrl, oldCachedRows, oldRowNoOf, parseTagArr, segTags, findRowByNo };
  }
  window.__mdOldRows = { create: create };
})();

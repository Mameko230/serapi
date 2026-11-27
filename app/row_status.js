/* memoQ 行状态枚举 → Serapi 状态列。独立纯函数模块，便于契约测试。 */
(function () {
  if (window.__mdRowStatus) return;

  function fromMeta(meta, hasTarget) {
    var st = String((meta && meta.status) || '');
    var low = st.toLowerCase();
    if (/proofread|proofreader|r2[-_\s]*confirmed|reviewer[-_\s]*2|proofreader[-_\s]*2/.test(low)) return 'reviewer2';
    if (/reviewed|r1[-_\s]*confirmed|reviewer[-_\s]*1|proofreader[-_\s]*1/.test(low)) return 'reviewer1';
    if (/rejected/.test(low)) return 'rejected';
    if (/manuallyconfirmed|tr[-_\s]*confirmed|(^|[^a-z])confirmed([^a-z]|$)/.test(low)) return 'confirmed';
    if (/pre[-_\s]*translated|assembled|machine[-_\s]*translated|xtranslated/.test(low)) {
      return hasTarget ? 'edited' : 'untranslated';
    }
    if (/not[-_\s]*started|untrans|empty/.test(low)) return 'untranslated';
    if (/edited/.test(low)) return hasTarget ? 'edited' : 'untranslated';
    return hasTarget ? 'edited' : 'untranslated';
  }

  function observe(onChange) {
    if (!window.MutationObserver || !document.body) return;
    var timer = null;
    var changedRows = {};
    function inEditor(node) {
      try {
        return !!(node && node.closest &&
          node.closest('.ProseMirror, [contenteditable="true"], textarea'));
      } catch (e) { return false; }
    }
    var observer = new MutationObserver(function (mutations) {
      var relevant = false;
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        var node = m.target;
        try {
          var roleRow = node && node.closest && node.closest('[role="row"]');
          if (!roleRow) continue;
          // 编辑器正文的输入不触发状态同步；只看行状态/徽章等非编辑区变化。
          if (inEditor(node)) continue;
          // memoQ 新版状态单元格是 .translation-row 的兄弟节点，
          // 不能只按 .translation-row 过滤，否则拒绝/确认状态永远收不到。
          var tr = roleRow.querySelector('.translation-row');
          var rid = tr && tr.getAttribute('data-row-id');
          if ((rid === null || rid === undefined || rid === '') && node.closest) {
            var cell = node.closest('[id^="status-cell-"]');
            var mm = cell && /status-cell-(\d+)/.exec(cell.id || '');
            if (mm) rid = mm[1];
          }
          if (rid !== null && rid !== undefined && rid !== '') changedRows[rid] = true;
          if (m.type === 'attributes') { relevant = true; break; }
          if (m.type === 'characterData' && node.parentElement) { relevant = true; break; }
          if (m.type === 'childList') { relevant = true; break; }
        } catch (e) {}
      }
      if (!relevant || timer) return;
      timer = setTimeout(function () {
        timer = null;
        var ids = Object.keys(changedRows);
        changedRows = {};
        try { onChange(ids); } catch (e) {}
      }, 250);
    });
    observer.observe(document.body, {
      subtree: true, attributes: true, childList: true, characterData: true,
      attributeFilter: ['class', 'aria-label', 'data-status', 'style'],
    });
  }

  window.__mdRowStatus = { fromMeta: fromMeta, observe: observe };
})();

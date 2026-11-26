/* 过滤：新版 filter API + 旧版原生过滤面板。 */
(function () {
  if (window.__mdFilterWorkflow) return;
  function create(deps) {
    function filterReq(direction, sourceText, targetText, regex) {
      try {
        if (deps.detect() === 'new') {
          var f = deps.filterState();
          f.status = 'pending';
          f.error = '';
          var filterSet = deps.filterSet(sourceText, targetText, regex);
          var clear = !Object.keys(filterSet).length;
          deps.filterPost(filterSet, function (err, rowIds) {
            if (err) {
              f.status = 'error';
              f.error = String(err).slice(0, 160);
              try { deps.push('filter-error', { err: f.error }); } catch (e) {}
              return;
            }
            f.active = !clear;
            f.rowIds = clear ? [] : rowIds;
            f.status = 'done';
            deps.rowsReset();
            try { deps.push('rows-updated', { source: 'filter' }); } catch (e) {}
          });
          return { ok: true, pending: true };
        }
        if (deps.detect() !== 'old') return { ok: false, err: '过滤器仅旧版支持' };
        var target = direction === 'target';
        var el = deps.pageFilterInput(target ? 'target' : 'source');

        var sc = (el && window.angular) ? angular.element(el).scope() : null;
        var fctrl = sc && sc.ctrl;
        if (!fctrl || typeof fctrl.filterForSourceOrTarget !== 'function') {
          return { ok: false, err: '过滤器未就绪，请先打开旧版编辑器' };
        }
        if (!sc.filterPaneSettings) sc.filterPaneSettings = {};
        // 两个框都写“已提交”的条件：未按 Enter 的输入不会提前参与过滤。
        sc.filterPaneSettings.sourceText = String(sourceText || '');
        sc.filterPaneSettings.targetText = String(targetText || '');
        try { sc.$applyAsync ? sc.$applyAsync() : sc.$apply(); } catch (e) {}
        fctrl.filterForSourceOrTarget(!target);
        // 原生过滤是异步刷新网格：此处 rowCount 还是旧值，不能当过滤结果返回。
        // Qt 侧等过滤稳定后重新 listRows，以 total/rows 为准。
        return { ok: true, filterIsOn: !!sc.filterPaneSettings.filterIsOn };
      } catch (e) { return { ok: false, err: '过滤器 ERR ' + e.message }; }
    }
    function clearFilterReq() {
      try {
        if (deps.detect() === 'new') {
          var f = deps.filterState();
          f.status = 'pending';
          f.error = '';
          deps.filterPost({}, function (err) {
            if (err) {
              f.status = 'error';
              f.error = String(err).slice(0, 160);
              try { deps.push('filter-error', { err: f.error }); } catch (e) {}
              return;
            }
            f.active = false;
            f.rowIds = [];
            f.status = 'idle';
            deps.rowsReset();
            try { deps.push('rows-updated', { source: 'filter-clear' }); } catch (e) {}
          });
          return { ok: true, pending: true };
        }
        if (deps.detect() !== 'old') return { ok: false, err: '过滤器仅旧版支持' };
        var el = deps.pageFilterInput('source');

        var sc = (el && window.angular) ? angular.element(el).scope() : null;
        var fctrl = sc && sc.ctrl;
        if (!fctrl || typeof fctrl.clearFilters !== 'function') {
          return { ok: false, err: '过滤器未就绪，请先打开旧版编辑器' };
        }
        fctrl.clearFilters();
        // 同上：清空也是异步恢复网格，行数由随后的 listRows 读取。
        return { ok: true };
      } catch (e) { return { ok: false, err: '清除过滤器 ERR ' + e.message }; }
    }

    return { filterReq, clearFilterReq };
  }
  window.__mdFilterWorkflow = { create: create };
})();

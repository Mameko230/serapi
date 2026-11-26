/* 旧版段列表读取（新版委托 newListRows）。 */
(function () {
  if (window.__mdRowListOld) return;
  function create(deps) {
    function listRows() {
      var kind = deps.detect();
      if (kind === 'new') return deps.newListRows();
      if (kind !== 'old') return { ok: false, err: 'listRows 仅旧版支持' };
      try {
        var ctrl = deps.oldGridCtrl();
        if (!ctrl) return { ok: false, err: 'gridCtrl 未找到' };
        var rows = deps.oldCachedRows(ctrl);
        var total = null;
        try { total = ctrl.gridContentManager.rowCount; } catch (e) {}
        function clean(s) {
          return String(s == null ? '' : s)
            .replace(/\{\d+>|<\d+[}>]/g, '■')  // tag 代码 → 占位符，便于阅读
            .replace(/\s+/g, ' ').trim();
        }
        // memoQ 的权威状态在 td.status-cell；tr 的 class 不含完整状态，不能用来猜。
        // 先匹配审校者，再匹配普通 confirmed，避免 r1/r2 被笼统归为译者确认。
        function statusFromText(v) {
          var s = String(v || '').toLowerCase();
          if (!s) return null;
          if (/r2[-_\s]*confirmed|reviewer[-_\s]*2|proofreader[-_\s]*2/.test(s)) return 'reviewer2';
          if (/r1[-_\s]*confirmed|reviewer[-_\s]*1|proofreader[-_\s]*1/.test(s)) return 'reviewer1';
          if (/rejected/.test(s)) return 'rejected';
          if (/manuallyconfirmed|tr[-_\s]*confirmed|(^|[^a-z])confirmed([^a-z]|$)/.test(s)) return 'confirmed';
          if (/edited|draft|pre[-_\s]*translated|fragment[-_\s]*assembled|mt[-_\s]*segments/.test(s)) return 'edited';
          if (/untrans|empty/.test(s)) return 'untranslated';
          return null;
        }
        var out = [];
        var dmap = {};
        var lmap = {};
        var clsSample = [];
        try {
          var p = deps.page();
          var trs = document.querySelectorAll((p && p.rows) || 'tr');
          for (var ti = 0; ti < trs.length; ti++) {
            var tr = trs[ti];
            if (!tr.querySelector || !tr.querySelector((p && p.editorCell) || '.editor-cell')) continue;
            var od = tr.querySelector((p && p.orderCell) || 'td.order');
            var no2 = od ? parseInt(od.textContent, 10) : NaN;
            if (!no2) continue;
            var stCell = tr.querySelector((p && p.statusCell) || 'td.status-cell');
            var cls = String(stCell ? stCell.className : tr.className || '');
            if (clsSample.length < 3) clsSample.push(cls.slice(0, 60));
            var st2 = statusFromText(cls);
            if (st2) dmap[no2] = st2;
            var lockEl = tr.querySelector((p && p.lockIcon) || '[data-iconkey="lock"]');
            if (lockEl) lmap[no2] = /(^|\s)locked(\s|$)/.test(String(lockEl.className));
          }
        } catch (e) {}
        function rowStatusOf(r) {
          try {
            // memoQ 原生 RowStatus.translationState 是分批缓存行也具备的权威字段。
            // 只读权限可能让 DOM 只剩灰色/只读样式；它绝不能覆盖 ManuallyConfirmed/R1/R2。
            var rs = r.rowStatus;
            if (rs !== undefined && rs !== null) {
              var vals = [];
              if (typeof rs === 'string' || typeof rs === 'number') vals.push(rs);
              else {
                // memoQ 12.5 bundle 的 TranslationState 枚举（不可按数组顺序自行猜测）：
                // 0 未开始；1 预翻译；2 已编辑；3 译者确认；4 R2；
                // 5 片段组合；6 机器翻译；7 R1；8 已拒绝。
                try {
                  var nativeState = rs.translationState;
                  if (nativeState !== undefined && nativeState !== null && nativeState !== '') {
                    var nativeNum = Number(nativeState);
                    var nativeMap = {
                      0: 'untranslated', 1: 'edited', 2: 'edited', 3: 'confirmed',
                      4: 'reviewer2', 5: 'edited', 6: 'edited', 7: 'reviewer1', 8: 'rejected'
                    }
                    if (isFinite(nativeNum) && nativeMap[nativeNum]) return nativeMap[nativeNum];
                    vals.push(nativeState);
                  }
                  var sm = rs.stateMachine && rs.stateMachine.stateMachine;
                  if (sm && sm.current) vals.push(sm.current);
                } catch (e) {}
                var keys = ['Status', 'status', 'State', 'state', 'Name', 'name', 'Value', 'value'];
                for (var k = 0; k < keys.length; k++) {
                  if (rs[keys[k]] !== undefined) vals.push(rs[keys[k]]);
                }
              }
              for (var vi = 0; vi < vals.length; vi++) {
                var st3 = statusFromText(vals[vi]);
                if (st3) return st3;
              }
            }
            // 缓存没有可识别语义时再读渲染行；未渲染行也走同一回退。
            var no3 = typeof r.id === 'number' ? r.id + 1 : null;
            if (no3 && dmap[no3]) return dmap[no3];
            var es = r.targetWebSegment && r.targetWebSegment.EditorString;
            var hasTgt = !!(es && String(es).replace(/\{\d+>|<\d+[}>]/g, '').trim());
            if (!hasTgt) return 'untranslated';
          } catch (e) {}
          return 'unknown';
        }
        function rowLocked(r) {
          // 实测：_locked 才是用户上锁；_isReadOnly 还可能表示 R2 权限，不能混用。
          if (r.rowStatus && typeof r.rowStatus._locked === 'boolean') return r.rowStatus._locked;
          var no = typeof r.id === 'number' ? r.id + 1 : null;
          return !!(no && lmap[no]);
        }
        for (var i = 0; i < rows.length; i++) {
          var r = rows[i];
          out.push({
            rowNo: typeof r.id === 'number' ? r.id + 1 : null,
            src: clean(r.sourceWebSegment && r.sourceWebSegment.EditorString).slice(0, 60),
            tgt: clean(r.targetWebSegment && r.targetWebSegment.EditorString).slice(0, 60),
            locked: rowLocked(r),
            maxLen: r._maxLengthChars || 0,
            status: rowStatusOf(r),
            // memoQ 段自身的来源匹配率；不是当前 TM 查询结果的最高分。
            tmRate: r.rowStatus && r.rowStatus._matchRate !== undefined
                    ? Number(r.rowStatus._matchRate) : null,
          });
        }
        return { ok: true, rows: out, total: total, cached: rows.length, trClsSample: clsSample };
      } catch (e) { return { ok: false, err: 'listRows ERR ' + e.message }; }
    }

    /* 原生过滤：旧版过滤面板的 Enter 入口（txtSourceFilter/txtTargetFilter）。
       返回的 rowCount 就是过滤后行数；getAllCachedRows 随后只含匹配行，
       行 id 仍是原始 0 基行号（listRows 的 rowNo = id + 1）。 */

    return { listRows };
  }
  window.__mdRowListOld = { create: create };
})();

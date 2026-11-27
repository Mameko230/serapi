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

  window.__mdRowStatus = { fromMeta: fromMeta };
})();

/* TM/TB 命中请求：新版行 hits API + 旧版 TranslationService。 */
(function () {
  if (window.__mdTmHits) return;

  function create(deps) {
    function tmHitsReq(rowNo) {
      // 崩溃二分诊断：MEMODESK_FAKE_RES 时跳过真实 fetch，同步返回空结果
      var fail = function (err) {
        window.__md._tm = { status: 'done', ok: false, err: String(err) };
        try { deps.push('tm-err', { row: rowNo, err: String(err).slice(0, 200) }); } catch (e) {}
      }
      try {
        if (window.__md_fakeRes) {
          window.__md._tm = { status: 'done', ok: true, tm: [], tb: [], at: [] };
          try { deps.push('tm-hits', { row: rowNo, tm: [], tb: [], at: [] }); } catch (e) {}
          return { ok: true };
        }
      } catch (e) {}
      window.__md._tm = { status: 'pending', t: Date.now() };
      try {
        if (deps.detect() === 'new') {
          deps.fetchHits(rowNo, fail);
          return { ok: true };
        }
        if (deps.detect() !== 'old') return fail('tmHits 仅旧版支持');
        var ctrl = deps.oldGridCtrl();
        if (!ctrl) return fail('gridCtrl 未找到（编辑器未打开？）');
        var row = deps.findRowByNo(ctrl, rowNo);
        if (!row) return fail('行 ' + rowNo + ' 不在缓存中（先加载更多）');
        var core = window.WebTrans && window.WebTrans.Core;
        var doc = core && core.docInstanceId;
        if (!doc) return fail('Core.docInstanceId 未找到');
        deps.apiPost('TranslationService/GetTranslationResults', {
          DocInstanceId: doc,
          Row: { id: row.id, guid: row.guid || null },
          PerformOnOriginalView: false
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) return fail('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || !b.Success) {
            return fail('HTTP ' + r.status + ' ' + String(b.ErrorDetails || b.error || '').slice(0, 140));
          }
          var hits = (b.Value && b.Value.Hits) || [];
          var sourceHtml = b.Value && b.Value.SourceHtml || '';
          var tm = [], tb = [], at = [];
          function hitTagDefs(seg) {
            var raw = seg && seg.ITaglist || [];
            var arr = raw && raw.toArray ? raw.toArray() : raw;
            return deps.parseTagArr(arr);
          }
          for (var i = 0; i < hits.length; i++) {
            var h = hits[i] || {}, md = h.MetaData || {};
            if (h.Type === 0 || h.Type === 5 || h.Type === 6) {
              var origWrap = h.OriginalWebSegmentWithHighlights || {};
              var origSeg = origWrap.Segment || origWrap.WebSegment || {};
              var decoratedHit = {
                res: md.Resource || (h.Type === 6 ? 'memoQ 自动替换' : (h.Type === 5 ? 'memoQ 非译元素' : '')),
                user: md.User || '', time: String(md.Time || '').slice(0, 16),
                srcDisp: h.SourceDisplayText || '',
                srcDecorated: origSeg.EditorString || h.SourceSegmentDecorated || h.SourceDisplayText || sourceHtml,
                tagDefs: hitTagDefs(origSeg),
                tgtDecorated: h.TargetSegmentDecorated || h.TargetDisplayText || ''
              }
              if (h.Type === 0) {
                decoratedHit.rate = md.MatchRate || 0;
                tm.push(decoratedHit);
              } else {
                decoratedHit.hitKind = h.Type === 6 ? 'at' : 'nt';
                at.push(decoratedHit);
              }
            } else if (h.Type === 1) {
              // memoQ 12.5 的 TB 命中没有 MetaData：术语库在 TBName，
              // 创建人/创建时间在 PrettyPrint1Html 的 entry-head 元数据格中。
              var tbName = h.TBName || md.Resource || md.Project || '';
              var tbUser = md.User || md.Creator || md.CreatedBy || '';
              var tbTime = md.Time || md.CreationTime || md.CreatedAt || '';
              var tbModifiedBy = md.ModifiedBy || md.LastModifiedBy || '';
              var tbModifiedTime = md.ModifiedTime || md.LastModifiedTime || '';
              try {
                if (h.PrettyPrint1Html && document.createElement) {
                  var pretty = document.createElement('div');
                  pretty.innerHTML = h.PrettyPrint1Html;
                  var metaValues = pretty.querySelectorAll('.entry-head .entry-level-meta-value');
                  var metaText = function (idx) {
                    return idx < metaValues.length ? String(metaValues[idx].textContent || '').trim() : '';
                  }
                  // 实测顺序：条目 ID、创建时间、创建者、修改时间、修改者。
                  if (!tbTime) tbTime = metaText(1);
                  if (!tbUser) tbUser = metaText(2);
                  if (!tbModifiedTime) tbModifiedTime = metaText(3);
                  if (!tbModifiedBy) tbModifiedBy = metaText(4);
                  if (!tbName) {
                    var tbNameEl = pretty.querySelector('.entry-head .tbname');
                    tbName = tbNameEl ? String(tbNameEl.textContent || '').trim() : '';
                  }
                }
              } catch (e) {}
              tb.push({ s: h.SourceDisplayText || '', t: h.TargetDisplayText || '',
                        res: tbName, user: String(tbUser || ''),
                        time: String(tbTime || '').slice(0, 19),
                        modifiedBy: String(tbModifiedBy || ''),
                        modifiedTime: String(tbModifiedTime || '').slice(0, 19),
                        entryId: h.EntryId === undefined || h.EntryId === null ? '' : String(h.EntryId),
                        tbGuid: h.TBGuid || '',
                        _rawKeys: tb.length === 0 ? Object.keys(h) : undefined });
            }
          }
          window.__md._tm = { status: 'done', ok: true, tm: tm, tb: tb, at: at };
          try { deps.push('tm-hits', { row: rowNo, tm: tm, tb: tb, at: at }); } catch (e) {}
        }).catch(fail);
      } catch (e) { fail(e.message); }
      return { ok: true };
    }
    function tmHitsPoll() {
      var t = window.__md._tm;
      return JSON.stringify(t || { status: 'none' });
    }

    return { tmHitsReq: tmHitsReq, tmHitsPoll: tmHitsPoll };
  }
  window.__mdTmHits = { create: create };
})();

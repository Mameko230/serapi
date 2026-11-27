/* memoQ 命中 entries → Serapi TM/TB 模型。纯函数模块；symbols 由前置模块提供。 */
(function () {
  if (window.__mdHits) return;
  var S = window.__mdSymbols;

  function map(entries, sourceTokens) {
    var tm = [], tb = [];
    entries = entries || [];
    sourceTokens = sourceTokens || [];
    for (var i = 0; i < entries.length; i++) {
      var h = entries[i] || {};
      var meta = h.meta || {};
      var res = h.documentName || meta.project || '';
      var type = String(h.type || '');
      if (type === 'transMemory') {
        var srcSeg = (h.segments && h.segments.source) || {};
        var tgtSeg = (h.segments && h.segments.target) || {};
        var srcText = S.segText(srcSeg);
        var tgtText = S.segText(tgtSeg);
        var srcTokens = S.tokens(srcSeg);
        var tgtTokens = S.tokens(tgtSeg);
        var hasTags = S.haveTags(srcSeg) || S.haveTags(tgtSeg);
        var planOk = !hasTags || S.tagPlan(sourceTokens, tgtTokens);
        tm.push({
          rate: Number(h.matchRate || 0), res: String(res || ''),
          user: String(h.creator || ''), time: String(h.created || '').slice(0, 16),
          srcDisp: srcText, srcDecorated: srcText, tgtDecorated: tgtText,
          srcTokens: srcTokens, tgtTokens: tgtTokens,
          strictTags: hasTags && planOk, tagPlanOk: planOk,
          readOnly: false, tagDefs: [],
        });
      } else if (type === 'termBase') {
        var langs = h.languages || {};
        var langKeys = Object.keys(langs);
        var srcLang = (h.source && h.source.langCode) || langKeys[0] || '';
        var tgtLang = h.targetLangCode || langKeys[1] || '';
        var srcIdx = (h.source && typeof h.source.termIndex === 'number')
          ? h.source.termIndex : 0;
        var tbTerm = function (lang, idx) {
          var bucket = langs[lang] || {};
          var terms = bucket.terms || [];
          var term = terms[idx] || terms[0] || null;
          return term ? String(term.term || '') : '';
        };
        var sTerm = tbTerm(srcLang, srcIdx);
        var tTerm = tbTerm(tgtLang, 0);
        if (sTerm || tTerm) {
          var detailLangs = [];
          for (var li = 0; li < langKeys.length; li++) {
            var code = langKeys[li];
            var bucket = langs[code] || {};
            var terms = bucket.terms || [];
            var role = (code === srcLang) ? 'source'
              : ((code === tgtLang) ? 'target' : 'other');
            var rawFields = (bucket.fields || []).slice();
            if (terms[0] && terms[0].fields) rawFields = rawFields.concat(terms[0].fields);
            var definition = '', examples = [], langFields = [];
            for (var fi = 0; fi < rawFields.length; fi++) {
              var f = rawFields[fi] || {};
              var fname = String(f.name || '');
              var fvalue = String(f.value == null ? '' : f.value);
              if (!fvalue) continue;
              if (/definition/i.test(fname) && !definition) definition = fvalue;
              else if (/example/i.test(fname)) examples.push(fvalue);
              else langFields.push({ name: fname, value: fvalue });
            }
            var termTexts = [];
            for (var ti = 0; ti < terms.length; ti++) {
              var tv = String((terms[ti] || {}).term || '');
              if (tv) termTexts.push(tv);
            }
            detailLangs.push({ role: role, code: code, terms: termTexts,
                               definition: definition, examples: examples,
                               fields: langFields });
          }
          var entryFields = [];
          var rawEntryFields = h.fields || [];
          for (var ei = 0; ei < rawEntryFields.length; ei++) {
            var ef = rawEntryFields[ei] || {};
            var ev = String(ef.value == null ? '' : ef.value);
            if (ev) entryFields.push({ name: String(ef.name || ''), value: ev });
          }
          if (entryFields.length) {
            for (var di = 0; di < detailLangs.length; di++) {
              if (detailLangs[di].role === 'source') {
                detailLangs[di].fields = detailLangs[di].fields.concat(entryFields);
                break;
              }
            }
          }
          var hitSrcCode = '', hitTgtCode = '';
          for (var dc = 0; dc < detailLangs.length; dc++) {
            if (detailLangs[dc].role === 'source') hitSrcCode = detailLangs[dc].code;
            else if (detailLangs[dc].role === 'target') hitTgtCode = detailLangs[dc].code;
          }
          if (hitSrcCode && hitTgtCode) {
            try { window.__md._termLangs = { src: hitSrcCode, tgt: hitTgtCode }; } catch (e) {}
          }
          tb.push({
            s: sTerm, t: tTerm, res: String(res || ''),
            user: String(h.creator || ''), time: String(h.created || '').slice(0, 19),
            modifiedBy: String(h.modifier || ''),
            modifiedTime: String(h.lastModified || '').slice(0, 19),
            entryId: String(h.entryId || h.id || ''),
            tbGuid: String(h.resourceId || ''),
            // 插入是读操作：术语库是否只读只影响“编辑条目”，不能阻止插入译文。
            newTerm: true, readOnly: false,
            detail: { readOnly: false, languages: detailLangs },
          });
        }
      }
    }
    return { tm: tm, tb: tb, at: [] };
  }

  window.__mdHits = { map: map };
})();

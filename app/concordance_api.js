/* 语词检索：新版 /concordance 两段式 + 旧版 TranslationService。 */
(function () {
  if (window.__mdConcordance) return;

  function create(deps) {
    function newReq(reqId, text, direction, fail) {
      var base = deps.docBase();
      if (!base) return fail('新版文档 API 未就绪');
      var headers = deps.headers();
      headers['Content-Type'] = 'application/json';
      var body = {
        side: direction === 'target' ? 1 : 0,
        searchText: {
          input: text, isCaseSensitive: false, findWithAnyNumber: false,
          useQuotes: false, useWildcards: false,
        },
        resources: { liveDocs: null, transMemory: null },
        oppositeSideFilter: '',
        oppositeSideSegment: null,
        sort: { orderBy: 'lastChangedAtDesc', groupBy: 'transMemory' },
        metaToPin: ['resourceTypeName'],
        tagView: 'short',
        requestWeb: {},
      };
      deps.fetch(base + '/concordance', {
        method: 'POST', credentials: 'same-origin', headers: headers,
        body: JSON.stringify(body),
      }).then(function (r) {
        return r.json().then(function (j) {
          if (r.status !== 200 || !j || !j.contextId) {
            throw new Error((j && (j.detail || j.title)) || ('HTTP ' + r.status));
          }
          return String(j.contextId);
        });
      }).then(function (contextId) {
        var url = base + '/concordance?' + new URLSearchParams({
          contextId: contextId, skip: '0', take: '50',
        }).toString();
        return deps.fetch(url, { headers: headers })
          .then(function (r) {
            return r.json().then(function (j) {
              if (r.status !== 200) {
                throw new Error((j && (j.detail || j.title)) || ('HTTP ' + r.status));
              }
              return j || {};
            });
          });
      }).then(function (data) {
        var hits = Array.isArray(data.hits) ? data.hits : [];
        var items = [];
        for (var i = 0; i < hits.length; i++) {
          var hit = hits[i] || {};
          var srcTokens = deps.symbolsTokens(hit.source || {});
          var tgtTokens = deps.symbolsTokens(hit.target || {});
          var meta = hit.meta || {};
          var proj = meta.project || {};
          var res = meta.resource || {};
          var modified = res.lastModified || {};
          function tokensText(tokens) {
            var out = '';
            for (var t = 0; t < tokens.length; t++) {
              if (tokens[t].t === 'text') out += tokens[t].v;
              else {
                var disp = String(tokens[t].display || tokens[t].name || 'tag');
                out += '[' + disp + ']';
              }
            }
            return out;
          }
          items.push({
            src: tokensText(srcTokens), tgt: tokensText(tgtTokens),
            srcTokens: srcTokens, tgtTokens: tgtTokens, tagDefs: [],
            res: String(res.name || res.id || res.type || ''),
            doc: String(meta.documentName || ''),
            user: String(modified.by || ''),
            time: String(modified.at || '').slice(0, 19).replace('T', ' '),
            project: String(proj.name || ''), client: String(proj.client || ''),
            domain: String(proj.domain || ''), subject: String(proj.subject || ''),
            created: String(modified.at || '').slice(0, 19).replace('T', ' '),
          });
        }
        deps.push('concordance-results', {
          req: reqId, text: text,
          total: Number(data.totalCount || 0), items: items,
        });
      }).catch(function (e) { fail(e.message || e); });
      return { ok: true, req: reqId };
    }

    function concordanceReq(reqId, text, direction) {
      text = String(text || '').trim();
      direction = direction === 'target' ? 'target' : 'source';
      function fail(err) {
        try { deps.push('concordance-error', { req: reqId, err: String(err).slice(0, 220) }); } catch (e) {}
      }
      if (!text) return fail('请输入检索词');
      if (deps.detect() === 'new') return newReq(reqId, text, direction, fail);
      if (deps.detect() !== 'old') return fail('语词检索仅新版/旧版支持');
      var core = window.WebTrans && window.WebTrans.Core;
      var doc = core && core.docInstanceId;
      if (!doc) return fail('Core.docInstanceId 未找到（请先打开文档）');
      var flag = core.concordanceSettings && core.concordanceSettings.ConcordanceFlag;
      flag = typeof flag === 'number' ? flag : 0;
      // 原生对话框 #search-in-target 的值是 16：译文检索使用 flag 位 16。
      // target 是“过滤译文”输入框，不是检索方向；译文查询同样必须填写 text。
      if (direction === 'target') flag = flag | 16;
      deps.apiPost('TranslationService/GetConcordanceResults', {
        docInstanceId: doc,
        concordanceParams: { text: text, target: '', limit: 50,
                             concordanceFlag: flag }
      }).then(function (r) {
        var b = r.body || {};
        if (b.SessionExpired) return fail('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || !b.Success) {
          return fail('HTTP ' + r.status + ' ' + String(b.ErrorDetails || b.ErrorMessage || '').slice(0, 160));
        }
        var val = b.Value || {};
        var raw = val.Items || [];
        var items = [];
        for (var i = 0; i < raw.length; i++) {
          var item = raw[i] || {};
          var sw = item.SourceSegmentWithHighlights || {};
          var tw = item.TargetSegmentWithHighlights || {};
          var meta = item.MetaInfo || {};
          var concSeg = sw.WebSegment || {};
          var concTags = concSeg.ITaglist;
          var concTagArr = concTags && concTags.toArray ? concTags.toArray() : (concTags || []);
          items.push({
            src: concSeg.EditorString || '',
            tgt: tw.WebSegment && tw.WebSegment.EditorString || '',
            tagDefs: deps.parseTagArr(concTagArr),
            res: meta.Resource || '', doc: meta.Document || '',
            user: meta.User || '', time: String(meta.Time || '').slice(0, 19),
            project: meta.Project || '', client: meta.Client || '',
            domain: meta.Domain || '', subject: meta.Subject || '',
            created: String(meta.Created || '').slice(0, 40)
          });
        }
        try { deps.push('concordance-results', { req: reqId, text: text,
                        total: Number(val.TotalHits || 0), items: items }); } catch (e) {}
      }).catch(function (e) { fail(e.message || e); });
      return { ok: true, req: reqId };
    };

    return { req: concordanceReq };
  }
  window.__mdConcordance = { create: create };
})();

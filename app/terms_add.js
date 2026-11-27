/* 旧版术语添加/条目读取：QTermService 原生模型。 */
(function () {
  if (window.__mdTermsAdd) return;
  function create(deps) {
    function termGetEntry(tbGuid, entryId, projectGuid) {
      return deps.apiPost('QTermService/GetEntryForTerm', {
        tbGuid: tbGuid,
        tbName: '',
        entryId: String(entryId),
        firstLanguage: null,
        secondLanguage: null,
        projectGuid: projectGuid,
        includeEntryHistory: false,
        entryNeedsModeration: false
      }).then(function (r) {
        var body = r.body || {};
        if (body.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || body.Success === false) {
          throw new Error(body.ErrorDetails || body.ErrorMessage || ('HTTP ' + r.status));
        }
        var value = body.Value || {};
        if (value.ErrorMessage) throw new Error(String(value.ErrorMessage));
        if (!value.Entry) throw new Error('memoQ 未返回术语条目');
        return value.Entry;
      });
    }
    window.__md.api.termContextReq = function (req) {
      return newTermsApi().termContext(req);
    }
    function termAddReq(req, params) {
      params = params || {};
      var source = String(params.source || '').trim();
      var target = String(params.target || '').trim();
      var tbGuid = String(params.tbGuid || '');
      if (!source || !target || !tbGuid) return deps.fail('term-add-result', req, '原文、译文和术语库均为必填');
      try {
        if (deps.detect() === 'new') {
          // 新版编辑器用文档级 quick-add；旧 QTermService 只作旧版兼容。
          var doc = String((deps.docBase && deps.docBase()) || '');
          var trans = doc.replace('/api/editor/', '/api/translation/');
          var hdr = deps.headers ? deps.headers() : {};
          hdr['Content-Type'] = 'application/json';
          deps.fetch(trans + '/info', { headers: hdr }).then(function (r) {
            return r.json();
          }).then(function (info) {
            var srcCode = String((info.project && info.project.sourceLang &&
                                  info.project.sourceLang.code) || '');
            var tgtCode = String((info.document && info.document.targetLang &&
                                  info.document.targetLang.code) || '');
            return deps.fetch(doc + '/terms/quick-add', {
              method: 'POST', headers: hdr,
              body: JSON.stringify({
                sourceTerm: { langCode: srcCode, termText: source },
                targetTerm: { langCode: tgtCode, termText: target },
              }),
            }).then(function (r2) {
              if (!r2.ok) throw new Error('HTTP ' + r2.status);
              deps.push('term-add-result', {
                req: req, ok: true, source: source, target: target, tbGuid: tbGuid,
              });
            });
          }).catch(function (e) { deps.fail('term-add-result', req, e.message || e); });
          return { ok: true };
        }
        if (deps.detect() !== 'old') return deps.fail('term-add-result', req, '添加术语仅旧版支持');
        var core = deps.termCore();
        var prj = deps.termProjectGuid(core);
        if (!window.qTerm || !qTerm.btbPage || !qTerm.Entry || !window.MQ) {
          throw new Error('memoQ 术语模块尚未就绪');
        }
        // 原生 btbPage.init 会在 WebTrans 内跳到错误页；只读取空模板，用 qTerm.Entry 构造原生数据模型。
        new Promise(function (resolve, reject) {
          MQ.ajax('~/api/QTermService/GetEmptyMetaList', { tbGuid: tbGuid, projectGuid: prj }, resolve,
                  function (_xhr, _status, err) { reject(new Error(String(err || '获取术语库模板失败'))); });
        }).then(function (b) {
          var data = Array.isArray(b) ? b : (b && b.Value);
          if (!Array.isArray(data) || !data[0] || !Array.isArray(data[0].LanguageLevelMetaInfos)) {
            throw new Error('memoQ 返回了无法识别的术语库模板');
          }
          // Entry 构造器只同步借用编号器；finally 立即恢复，不留下任何 memoQ 页面状态改动。
          var oldDisplay = qTerm.btbPage.entryDisplayModule;
          var oldSettings = qTerm.btbPage.settings;
          var metaId = -1, entry;
          qTerm.btbPage.entryDisplayModule = { getMetaInfoId: function () { return --metaId; } };
          if (!qTerm.btbPage.settings) qTerm.btbPage.settings = { HiddenLanguages: [] };
          try {
            entry = new qTerm.Entry(-1, tbGuid, data[0].ReadOnlyTb,
                                    data[0].EntryLevelMetaInfos, data[0].LanguageLevelMetaInfos, '');
          } finally {
            if (oldDisplay === undefined) delete qTerm.btbPage.entryDisplayModule;
            else qTerm.btbPage.entryDisplayModule = oldDisplay;
            if (oldSettings === undefined) delete qTerm.btbPage.settings;
            else qTerm.btbPage.settings = oldSettings;
          }
          var langs = entry && entry.languageLevelMetaInfos;
          if (!entry || !langs || langs.length < 2) throw new Error('memoQ 未能初始化双语术语 Entry');
          if (entry.readOnlyTB) throw new Error('所选术语库为只读，无法添加术语');
          if (!langs[0].termLevelMetaInfos.length || !langs[1].termLevelMetaInfos.length) {
            throw new Error('术语库缺少可用的原文/译文语言层');
          }
          // 与原生添加窗口一致，同时填写 termText 和 termWildText。
          langs[0].languageCode = core.sourceLangCode;
          langs[1].languageCode = core.targetLangCode;
          langs[0].termLevelMetaInfos[0].termText = source;
          langs[0].termLevelMetaInfos[0].termWildText = source;
          langs[1].termLevelMetaInfos[0].termText = target;
          langs[1].termLevelMetaInfos[0].termWildText = target;
          // 新增术语也带上语言层定义与术语层示例（术语库没有对应 meta 时自动忽略）。
          deps.setMeta(langs[0], 'Definition', String(params.sourceDefinition || ''));
          deps.setMeta(langs[1], 'Definition', String(params.targetDefinition || ''));
          deps.setMeta(langs[0].termLevelMetaInfos[0], 'Example', String(params.sourceExample || ''));
          deps.setMeta(langs[1].termLevelMetaInfos[0], 'Example', String(params.targetExample || ''));
          return deps.apiPost('QTermService/AddNewEntry', { TBGuid: tbGuid, EntryGui: entry, ProjectGuid: prj });
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || b.Success === false) {
            throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          }
          core.lastUsedTBGuid = tbGuid;
          // 术语已经添加成功；偏好保存失败不能误报为添加失败，避免重试产生重复术语。
          return deps.apiPost('TranslationService/SaveLastUsedTBGuid', {
            docInstanceId: core.docInstanceId, lastUsedTBGuid: tbGuid
          }).catch(function () {}).then(function () {
            deps.push('term-add-result', { req: req, ok: true, source: source, target: target });
          });
        }).catch(function (e) { deps.fail('term-add-result', req, e.message || e); });
      } catch (e) { deps.fail('term-add-result', req, e.message || e); }
      return { ok: true };
    }

    /* ---- 右键编辑术语：读 GetEntryForTerm → 改主术语/定义/注释 → UpdateEntry ----
       真实结构（2026-11-25 实测）：
         GetEntryForTerm 响应 Value.Entry（PascalCase，含 EntryLevelMetaInfos / LanguageLevelMetaInfos）；
         UpdateEntry 请求 {TBGuid, EntryId, EntryGui(camelCase), ProjectGuid, EntryNeedsModeration}；
         定义 = 语言层 MetaInfos 里的 Definition；注释 = 条目层 EntryLevelMetaInfos 里的 Note；
         响应信封 {Success, Value:{Result, ErrorMessage}}，Result=0 成功。 */
    function termEntryReq(req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return deps.fail('term-entry', req, '缺少术语条目信息');
      }
      try {
        var kind = deps.detect();
        if (kind !== 'old' && kind !== 'new') return deps.fail('term-entry', req, '编辑术语仅新版/旧版支持');
        var isNew = kind === 'new';
        var core = null;
        var prj = String(params.projectGuid || '');
        if (isNew) {
          prj = prj || deps.projectGuid();
        } else {
          core = deps.termCore();
          if (!core.sourceLangCode || !core.targetLangCode) {
            throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
          }
          prj = prj || deps.termProjectGuid(core);
        }
        if (!prj) throw new Error('项目 GUID 未找到');
        termGetEntry(tbGuid, entryId, prj).then(function (entry) {
          var codes = isNew
            ? deps.langCodes(entry, params)
            : { src: core.sourceLangCode, tgt: core.targetLangCode };
          var src = deps.language(entry, codes.src);
          var tgt = deps.language(entry, codes.tgt);
          if (!src || !tgt) throw new Error('术语条目缺少原文或译文语言层');
          var srcTerm = deps.primaryTerm(src);
          var tgtTerm = deps.primaryTerm(tgt);
          if (!srcTerm || !tgtTerm) throw new Error('术语条目缺少原文或译文术语');
          deps.push('term-entry', {
            req: req,
            tbGuid: tbGuid,
            entryId: entry.EntryId,
            projectGuid: prj,
            readOnly: !!entry.ReadOnlyTb,
            source: String(srcTerm.TermText || ''),
            target: String(tgtTerm.TermText || ''),
            sourceDefinition: deps.metaValue(src, 'Definition'),
            targetDefinition: deps.metaValue(tgt, 'Definition'),
            sourceExample: deps.metaValue(srcTerm, 'Example'),
            targetExample: deps.metaValue(tgtTerm, 'Example'),
            sourceLang: String(src.LanguageCode || ''),
            targetLang: String(tgt.LanguageCode || ''),
            languages: (entry.LanguageLevelMetaInfos || []).map(function (lang) {
              return String(lang.LanguageCode || '');
            })
          });
        }).catch(function (e) { deps.fail('term-entry', req, e.message || e); });
      } catch (e) { deps.fail('term-entry', req, e.message || e); }
      return { ok: true };
    }

    return { termGetEntry, termAddReq, termEntryReq };
  }
  window.__mdTermsAdd = { create: create };
})();

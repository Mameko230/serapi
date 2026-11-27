/* 术语服务编排：TB 列表、空模板、快捷添加。网络/推送由 bridge 注入。 */
(function () {
  if (window.__mdTermsApi) return;

  function create(deps) {
    function termTbList(prj, tgtLang) {
      return deps.post('TranslationService/ListServerProjectTBs', {
        projectGuid: prj, targetLanguage: tgtLang || '',
      }).then(function (r) {
        var b = r.body || {};
        if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || b.Success === false) {
          throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
        }
        var raw = Array.isArray(b) ? b : (Array.isArray(b.Value) ? b.Value : []);
        return raw.map(function (f) {
          return { guid: String(f.TBGuid || ''), name: String(f.TBName || f.TBGuid || ''),
                   primary: !!f.IsPrimary };
        }).filter(function (f) { return !!f.guid; });
      });
    }
    // 术语库模板（GetEmptyMetaList）→ AddNewEntry 需要的 camelCase EntryGui；
    // 模板里每层通常已有一条空术语占位，缺了就补一条，其余重复项标记删除。
    function termTemplateEntryGui(tpl, tbGuid) {
      function guiMeta(m) { return deps.model.termMetaToGui(m || {}); }
      function guiTerm(t) {
        return {
          termId: t.TermId, termText: String(t.TermText || ''),
          termWildText: String(t.TermWildText || t.TermText || ''),
          isDeleted: !!t.IsDeleted, metaInfos: (t.MetaInfos || []).map(guiMeta),
          isMetaListRendered: false,
        };
      }
      function guiLang(lang) {
        var terms = (lang.TermLevelMetaInfos || []).map(guiTerm);
        if (!terms.length) {
          terms.push({ termId: -1, termText: '', termWildText: '', isDeleted: false,
                       metaInfos: [], isMetaListRendered: false });
        }
        return {
          languageCode: String(lang.LanguageCode || ''), languageID: lang.LanguageID,
          languageName: String(lang.LanguageName || ''), isDeleted: !!lang.IsDeleted,
          metaInfos: (lang.MetaInfos || []).map(guiMeta),
          termLevelMetaInfos: terms, isMetaListRendered: false,
        };
      }
      return {
        tbGuid: tbGuid, readOnlyTB: !!tpl.ReadOnlyTb, entryId: -1,
        prettyPrintHtml: String(tpl.PrettyPrintHtml || ''),
        relationships: (tpl.Relationships || []).slice(),
        entryNeedsModeration: false,
        entryLevelMetaInfos: (tpl.EntryLevelMetaInfos || []).map(guiMeta),
        languageLevelMetaInfos: (tpl.LanguageLevelMetaInfos || []).map(guiLang),
        isMetaListRendered: false,
      };
    }
    function termAlignQuickLayers(entry, srcLang, tgtLang) {
      var layers = entry.languageLevelMetaInfos || [];
      function base(code) { return String(code || '').trim().toLowerCase().split('-')[0]; }
      function find(code) {
        var want = String(code || '').trim().toLowerCase();
        if (!want) return null;
        for (var i = 0; i < layers.length; i++) {
          var have = String(layers[i].languageCode || '').trim().toLowerCase();
          if (have && (have === want || base(have) === base(want))) return layers[i];
        }
        return null;
      }
      var src = find(srcLang);
      var tgt = find(tgtLang);
      if (src && tgt && src === tgt) tgt = null;
      if (!src || !tgt) {
        // 模板顺序兜底：第一层原文、第二层译文（旧版 qTerm.Entry 也按此顺序覆写）。
        if (!src) src = layers[0] || null;
        if (!tgt) {
          for (var i = 0; i < layers.length; i++) {
            if (layers[i] !== src) { tgt = layers[i]; break; }
          }
        }
      }
      return { src: src, tgt: tgt };
    }
    function termQuickAddEntry(req, tb, source, target, srcLang, tgtLang, prj) {
      return deps.post('QTermService/GetEmptyMetaList', {
        tbGuid: tb.guid, projectGuid: prj,
      }).then(function (r) {
        var b = r.body || {};
        if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || b.Success === false) {
          throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
        }
        var data = Array.isArray(b) ? b : (b.Value || []);
        if (!Array.isArray(data) || !data[0]
            || !Array.isArray(data[0].LanguageLevelMetaInfos)) {
          throw new Error('memoQ 返回了无法识别的术语库模板');
        }
        var entry = termTemplateEntryGui(data[0], tb.guid);
        if (entry.readOnlyTB) throw new Error('所选术语库为只读，无法添加术语');
        var pair = termAlignQuickLayers(entry, srcLang, tgtLang);
        if (!pair.src || !pair.tgt) throw new Error('术语库缺少可用的原文/译文语言层');
        if (srcLang) pair.src.languageCode = srcLang;
        if (tgtLang) pair.tgt.languageCode = tgtLang;
        pair.src.termLevelMetaInfos[0].termText = source;
        pair.src.termLevelMetaInfos[0].termWildText = source;
        pair.tgt.termLevelMetaInfos[0].termText = target;
        pair.tgt.termLevelMetaInfos[0].termWildText = target;
        return deps.post('QTermService/AddNewEntry', {
          TBGuid: tb.guid, EntryGui: entry, ProjectGuid: prj,
        });
      }).then(function (r) {
        var b = r.body || {};
        if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
        if (r.status !== 200 || b.Success === false) {
          throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
        }
        var value = b.Value || {};
        if (value.Result !== undefined && Number(value.Result) !== 0) {
          throw new Error(value.ErrorMessage || 'memoQ 拒绝了这次术语添加');
        }
        deps.push('term-quick-result', {
          req: req, ok: true, quick: true, tbGuid: tb.guid, tbName: tb.name,
          source: source, target: target,
        });
      });
    }

    function termContext(req) {
      try {
        var kind = deps.detectEditor();
        if (kind === 'new') {
          var doc = String(deps.docBase() || '');
          if (!doc) return deps.fail('term-context', req, '文档 API 路径未找到');
          var h = deps.headers ? deps.headers() : {};
          deps.fetch(doc + '/resources/meta', { headers: h }).then(function (r) {
            return r.json();
          }).then(function (meta) {
            var raw = (meta && meta.termBase) || [];
            var items = raw.map(function (tb) {
              return { guid: String(tb.id || ''), name: String(tb.name || tb.id || ''),
                       primary: !!tb.isPrimary, readOnly: !!tb.isReadOnly,
                       languages: tb.languages || [] };
            }).filter(function (tb) { return !!tb.guid; });
            if (!items.length) throw new Error('当前项目没有挂接术语库');
            var primary = items.filter(function (tb) { return tb.primary; })[0];
            deps.push('term-context', {
              req: req, items: items,
              selected: primary ? primary.guid : items[0].guid,
            });
          }).catch(function (e) { deps.fail('term-context', req, e.message || e); });
          return { ok: true };
        }
        if (kind !== 'old') return deps.fail('term-context', req, '添加术语仅旧版支持');
        var core = deps.termCore();
        var prj = deps.termProjectGuid(core);
        deps.post('TranslationService/ListServerProjectTBs', {
          projectGuid: prj, targetLanguage: core.targetLangCode,
        }).then(function (r) {
          var b = r.body || {};
          if (b.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
          if (r.status !== 200 || b.Success === false) {
            throw new Error(b.ErrorDetails || b.ErrorMessage || ('HTTP ' + r.status));
          }
          var raw = Array.isArray(b) ? b : (Array.isArray(b.Value) ? b.Value : []);
          var items = raw.map(function (f) {
            return { guid: String(f.TBGuid || ''), name: String(f.TBName || f.TBGuid || ''),
                     primary: !!f.IsPrimary };
          }).filter(function (f) { return !!f.guid; });
          var selected = String(core.lastUsedTBGuid || '');
          if (!selected) {
            var primary = items.filter(function (f) { return f.primary; })[0];
            selected = primary ? primary.guid : (items.length ? items[0].guid : '');
          }
          deps.push('term-context', { req: req, items: items, selected: selected });
        }).catch(function (e) { deps.fail('term-context', req, e.message || e); });
      } catch (e) { deps.fail('term-context', req, e.message || e); }
      return { ok: true };
    }

    function termDetail(req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return deps.fail('term-detail', req, '缺少术语条目信息');
      }
      try {
        var kind = deps.detectEditor();
        if (kind !== 'old' && kind !== 'new') {
          return deps.fail('term-detail', req, '术语详情仅新版/旧版支持');
        }
        var isNew = kind === 'new';
        var core = null;
        var prj = String(params.projectGuid || '');
        if (isNew) {
          prj = prj || deps.newProjectGuidFromUrl();
        } else {
          core = deps.termCore();
          if (!core.sourceLangCode || !core.targetLangCode) {
            throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
          }
          prj = prj || deps.termProjectGuid(core);
        }
        if (!prj) throw new Error('项目 GUID 未找到');
        deps.getEntry(tbGuid, entryId, prj).then(function (entry) {
          var codes = isNew
            ? deps.langCodes(entry, params)
            : { src: core.sourceLangCode, tgt: core.targetLangCode };
          var src = deps.language(entry, codes.src);
          var tgt = deps.language(entry, codes.tgt);
          var languages = (entry.LanguageLevelMetaInfos || []).map(function (lang) {
            var role = 'other';
            if (lang === src) role = 'source';
            else if (lang === tgt) role = 'target';
            return deps.languageDetail(lang, role);
          });
          deps.push('term-detail', {
            req: req,
            tbGuid: tbGuid,
            entryId: entry.EntryId,
            projectGuid: prj,
            readOnly: !!entry.ReadOnlyTb,
            sourceLang: src ? String(src.LanguageCode || '') : '',
            targetLang: tgt ? String(tgt.LanguageCode || '') : '',
            sourceDefinition: src ? deps.metaValue(src, 'Definition') : '',
            targetDefinition: tgt ? deps.metaValue(tgt, 'Definition') : '',
            sourceExamples: src ? deps.examples(src) : [],
            targetExamples: tgt ? deps.examples(tgt) : [],
            languages: languages,
          });
        }).catch(function (e) { deps.fail('term-detail', req, e.message || e); });
      } catch (e) { deps.fail('term-detail', req, e.message || e); }
      return { ok: true };
    }

    function termEdit(req, params) {
      params = params || {};
      var tbGuid = String(params.tbGuid || '');
      var entryId = params.entryId;
      var source = String(params.source || '').trim();
      var target = String(params.target || '').trim();
      if (!tbGuid || entryId === undefined || entryId === null || entryId === '') {
        return deps.fail('term-edit-result', req, '缺少术语条目信息');
      }
      if (!source || !target) {
        return deps.fail('term-edit-result', req, '原文术语和译文术语都需要填写');
      }
      try {
        var kind = deps.detectEditor();
        if (kind !== 'old' && kind !== 'new') {
          return deps.fail('term-edit-result', req, '编辑术语仅新版/旧版支持');
        }
        var isNew = kind === 'new';
        var core = null;
        var prj = String(params.projectGuid || '');
        if (isNew) {
          prj = prj || deps.newProjectGuidFromUrl();
        } else {
          core = deps.termCore();
          if (!core.sourceLangCode || !core.targetLangCode) {
            throw new Error('memoQ 语言信息尚未就绪，请先点击原文或译文段后再试');
          }
          prj = prj || deps.termProjectGuid(core);
        }
        if (!prj) throw new Error('项目 GUID 未找到');
        deps.getEntry(tbGuid, entryId, prj).then(function (entry) {
          if (entry.ReadOnlyTb) throw new Error('该术语库为只读，无法编辑');
          var codes = isNew
            ? deps.langCodes(entry, params)
            : { src: core.sourceLangCode, tgt: core.targetLangCode };
          var src = deps.language(entry, codes.src);
          var tgt = deps.language(entry, codes.tgt);
          if (!src || !tgt) throw new Error('术语条目缺少原文或译文语言层');
          var srcTerm = deps.primaryTerm(src);
          var tgtTerm = deps.primaryTerm(tgt);
          if (!srcTerm || !tgtTerm) throw new Error('术语条目缺少原文或译文术语');
          var srcDef = String(params.sourceDefinition || '');
          var tgtDef = String(params.targetDefinition || '');
          var srcExample = String(params.sourceExample || '');
          var tgtExample = String(params.targetExample || '');
          var oldSrc = String(srcTerm.TermText || '');
          var oldTgt = String(tgtTerm.TermText || '');
          entry.PrettyPrintHtml = deps.patchHtml(entry.PrettyPrintHtml, [
            [oldSrc, source], [oldTgt, target],
            [deps.metaValue(src, 'Definition'), srcDef],
            [deps.metaValue(tgt, 'Definition'), tgtDef],
            [deps.metaValue(srcTerm, 'Example'), srcExample],
            [deps.metaValue(tgtTerm, 'Example'), tgtExample],
          ]);
          srcTerm.TermText = source;
          srcTerm.TermWildText = source;
          tgtTerm.TermText = target;
          tgtTerm.TermWildText = target;
          deps.setMeta(src, 'Definition', srcDef);
          deps.setMeta(tgt, 'Definition', tgtDef);
          deps.setMeta(srcTerm, 'Example', srcExample);
          deps.setMeta(tgtTerm, 'Example', tgtExample);
          return deps.post('QTermService/UpdateEntry', {
            TBGuid: tbGuid,
            EntryId: entry.EntryId === undefined ? entryId : entry.EntryId,
            EntryGui: deps.entryToGui(entry),
            ProjectGuid: prj,
            EntryNeedsModeration: false,
          }).then(function (r) {
            var body = r.body || {};
            if (body.SessionExpired) throw new Error('会话过期，请重新登录 memoQ');
            if (r.status !== 200 || body.Success === false) {
              throw new Error(body.ErrorDetails || body.ErrorMessage || ('HTTP ' + r.status));
            }
            var value = body.Value || {};
            var result = value.Result === undefined ? 0 : Number(value.Result);
            if (result !== 0) throw new Error(value.ErrorMessage || 'memoQ 拒绝了这次术语修改');
            deps.push('term-edit-result', {
              req: req, ok: true, entryId: entry.EntryId, tbGuid: tbGuid,
              source: source, target: target,
            });
          });
        }).catch(function (e) { deps.fail('term-edit-result', req, e.message || e); });
      } catch (e) { deps.fail('term-edit-result', req, e.message || e); }
      return { ok: true };
    }

    function termQuickAddNew(req, source, target) {
      var docBase = String((deps.docBase && deps.docBase()) || '');
      var transBase = docBase.replace('/api/editor/', '/api/translation/');
      if (!docBase || transBase === docBase) {
        deps.fail('term-quick-err', req, '文档 API 路径未找到');
        return { ok: false };
      }
      var hdr = deps.headers ? deps.headers() : {};
      hdr['Content-Type'] = 'application/json';
      deps.fetch(transBase + '/info', { headers: hdr }).then(function (r) {
        return r.json();
      }).then(function (info) {
        var srcCode = String((info && info.project && info.project.sourceLang &&
                              info.project.sourceLang.code) || '');
        var tgtCode = String((info && info.document && info.document.targetLang &&
                              info.document.targetLang.code) || '');
        if (!srcCode || !tgtCode) throw new Error('未能识别文档语言');
        return deps.fetch(docBase + '/terms/quick-add', {
          method: 'POST', headers: hdr,
          body: JSON.stringify({
            sourceTerm: { langCode: srcCode, termText: source },
            targetTerm: { langCode: tgtCode, termText: target },
          }),
        }).then(function (r2) {
          return r2.text().then(function (txt) {
            if (!r2.ok) throw new Error('HTTP ' + r2.status + ' ' + txt.slice(0, 120));
            try { var body = JSON.parse(txt || '{}'); if (body.Success === false) {
              throw new Error(body.ErrorMessage || body.ErrorDetails || '术语添加失败');
            } } catch (e) {
              if (e && String(e.message || '').indexOf('HTTP ') === 0) throw e;
            }
            deps.push('term-quick-result', {
              req: req, ok: true, tbGuid: '', tbName: '主术语库',
              source: source, target: target,
            });
          });
        });
      }).catch(function (e) { deps.fail('term-quick-err', req, e.message || e); });
      return { ok: true };
    }

    function termQuickAdd(req, params) {
      params = params || {};
      var source = String(params.source || '').trim();
      var target = String(params.target || '').trim();
      if (!source || !target) {
        return deps.fail('term-quick-err', req, '请分别在原文、译文选中要添加的术语');
      }
      try {
        var kind = deps.detectEditor();
        if (kind !== 'old' && kind !== 'new') {
          return deps.fail('term-quick-err', req, '快速添加术语仅新版/旧版支持');
        }
        if (kind === 'new' && !window.__md.__legacyTermQuickAdd && deps.docBase) {
          // 新版编辑器有自己的快捷添加端点：自动选主术语库并用文档真实语言码。
          return termQuickAddNew(req, source, target);
        }
        var core = null, prj = '', srcLang = '', tgtLang = '';
        if (kind === 'old') {
          core = deps.termCore();
          prj = String(params.projectGuid || deps.termProjectGuid(core));
          srcLang = String(core.sourceLangCode || '');
          tgtLang = String(core.targetLangCode || '');
        } else {
          prj = deps.termProjectGuidFor(params);
          var docLangs = deps.documentLanguageCodes();
          // DOM 的 lang=jp/zh 只是页面本地化代码，不等于 memoQ TB 的 jpn/zho；
          // 用它只做“识别成功”判断，实际写条目交给 TB 模板语言层。
          var domOnly = !!docLangs.fromDom;
          srcLang = String(params.sourceLang || (domOnly ? '' : (docLangs.src || '')) || '');
          tgtLang = String(params.targetLang || (domOnly ? '' : (docLangs.tgt || '')) || '');
          if (domOnly && !params.targetLang) tgtLang = '';
        }
        if (!prj) throw new Error('项目 GUID 未找到');
        if (kind === 'new' && !domOnly && (!srcLang || !tgtLang)) {
          return deps.fail('term-quick-err', req,
            '未能识别文档语言：请先切换到有术语命中的段，再使用 Ctrl+Q');
        }
        var wanted = String(params.tbGuid || '').trim();
        function withTbList(items) {
          if (!items.length) throw new Error('当前项目没有可用的术语库');
          var chosen = null;
          if (wanted) {
            for (var i = 0; i < items.length; i++) {
              if (items[i].guid === wanted) { chosen = items[i]; break; }
            }
          }
          if (!chosen && !wanted && items.length === 1) chosen = items[0];
          if (!chosen) {
            var primary = items.filter(function (x) { return x.primary; })[0];
            deps.push('term-pick-tb', {
              req: req, items: items, source: source, target: target,
              selected: wanted, stale: !!wanted,
              primary: primary ? primary.guid : (items[0] ? items[0].guid : ''),
              srcLang: srcLang, tgtLang: tgtLang, projectGuid: prj,
            });
            return;
          }
          // 优先使用术语库模板里的真实语言层 code；显式传入的语言码（测试/旧版）
          // 仍由 termQuickAddEntry 覆盖，DOM lang 兜底时 src/tgt 为空。
          return termQuickAddEntry(req, chosen, source, target, srcLang, tgtLang, prj)
            .then(function () {
              if (core) {
                core.lastUsedTBGuid = chosen.guid;
                return deps.post('TranslationService/SaveLastUsedTBGuid', {
                  docInstanceId: core.docInstanceId, lastUsedTBGuid: chosen.guid,
                }).catch(function () {});
              }
            });
        }
        termTbList(prj, tgtLang).then(function (items) {
          if (items && items.length) return withTbList(items);
          // 新版 DOM 语言码不一定是 TB targetLanguage 过滤值；退回不筛选。
          return termTbList(prj, '').then(withTbList);
        }).catch(function (e) { deps.fail('term-quick-err', req, e.message || e); });
      } catch (e) { deps.fail('term-quick-err', req, e.message || e); }
      return { ok: true };
    }

    return { termTbList, termTemplateEntryGui, termAlignQuickLayers, termQuickAddEntry,
             termContext, termDetail, termEdit, termQuickAdd, termQuickAddNew };
  }

  window.__mdTermsApi = { create: create };
})();

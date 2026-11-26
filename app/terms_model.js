/* 术语条目 GUI 模型：MetaInfo / 语言 / 术语 / 示例映射。纯函数模块。 */
(function () {
  if (window.__mdTermsModel) return;
    function termMetaList(container) {
      if (!container) return [];
      return container.MetaInfos || container.metaInfos ||
        container.EntryLevelMetaInfos || container.entryLevelMetaInfos || [];
    }
    function termMetaName(meta) {
      return String((meta && (meta.Name !== undefined ? meta.Name : meta.name)) || '');
    }
    function termMetaValue(container, name) {
      var list = termMetaList(container);
      var want = String(name || '').toLowerCase();
      for (var i = 0; i < list.length; i++) {
        if (termMetaName(list[i]).toLowerCase() !== want) continue;
        var value = list[i].ValueAsObject;
        if (value === undefined) value = list[i].valueAsObject;
        return value === null || value === undefined ? '' : String(value);
      }
      return '';
    }
    function termSetMeta(container, name, value) {
      var list = termMetaList(container);
      var want = String(name || '').toLowerCase();
      var text = String(value === null || value === undefined ? '' : value);
      var empty = text === '';
      for (var i = 0; i < list.length; i++) {
        var meta = list[i];
        if (termMetaName(meta).toLowerCase() !== want) continue;
        if ('ValueAsObject' in meta) meta.ValueAsObject = empty ? null : text;
        if ('valueAsObject' in meta) meta.valueAsObject = empty ? null : text;
        if ('IsNoValue' in meta) meta.IsNoValue = empty;
        if ('isNoValue' in meta) meta.isNoValue = empty;
        return true;
      }
      return false;
    }
    function termLanguage(entry, code) {
      var langs = (entry && entry.LanguageLevelMetaInfos) || [];
      var want = String(code || '').trim().toLowerCase();
      if (!want) return null;
      var wantBase = want.split('-')[0];
      var baseMatch = null;
      var baseCount = 0;
      for (var i = 0; i < langs.length; i++) {
        var lc = String(langs[i].LanguageCode || '').trim().toLowerCase();
        if (!lc) continue;
        if (lc === want) return langs[i];
        if (lc.split('-')[0] === wantBase) {
          baseMatch = langs[i];
          baseCount++;
        }
      }
      // core.targetLangCode 可能是 zho，而条目里是 zho-CN；只在唯一匹配时退化到基础语言码。
      return baseCount === 1 ? baseMatch : null;
    }
    function termPrimaryTerm(lang) {
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (!terms[i].IsDeleted) return terms[i];
      }
      return null;
    }
    function termExamples(lang) {
      var out = [];
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (terms[i].IsDeleted) continue;
        var value = termMetaValue(terms[i], 'Example');
        if (value && out.indexOf(value) < 0) out.push(value);
      }
      return out;
    }
    function termLanguageTerms(lang) {
      var out = [];
      var terms = (lang && lang.TermLevelMetaInfos) || [];
      for (var i = 0; i < terms.length; i++) {
        if (terms[i].IsDeleted) continue;
        var text = String(terms[i].TermText || '');
        if (text && out.indexOf(text) < 0) out.push(text);
      }
      return out;
    }
    function termLanguageDetail(lang, role) {
      return {
        code: String(lang.LanguageCode || ''),
        name: String(lang.LanguageName || ''),
        role: role,
        terms: termLanguageTerms(lang),
        definition: termMetaValue(lang, 'Definition'),
        examples: termExamples(lang)
      };
    }
    function termEscapeHtml(text) {
      return String(text === null || text === undefined ? '' : text)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    // PrettyPrintHtml 只是条目展示缓存；按旧值→新值做一次保守替换，服务端若重新生成也无副作用。
    function termPatchPrettyHtml(html, pairs) {
      var out = String(html || '');
      for (var i = 0; i < pairs.length; i++) {
        var from = String(pairs[i][0] || '');
        var to = String(pairs[i][1] || '');
        if (!from || from === to) continue;
        var escapedFrom = termEscapeHtml(from);
        if (out.indexOf(from) >= 0) out = out.split(from).join(termEscapeHtml(to));
        if (escapedFrom !== from && out.indexOf(escapedFrom) >= 0) {
          out = out.split(escapedFrom).join(termEscapeHtml(to));
        }
      }
      return out;
    }
    function termMetaToGui(meta) {
      return {
        name: meta.Name,
        displayName: meta.DisplayName,
        description: meta.Description || '',
        typeName: meta.TypeName,
        allowedValues: meta.AllowedValues === undefined ? null : meta.AllowedValues,
        valueAsObject: meta.ValueAsObject === undefined ? null : meta.ValueAsObject,
        isNoValue: !!meta.IsNoValue,
        isUnique: !!meta.IsUnique,
        isRequired: !!meta.IsRequired,
        isReadonly: !!meta.IsReadOnly,
        isMultiLine: !!meta.IsMultiLine,
        imageDimension: meta.ImageDimension === undefined ? null : meta.ImageDimension,
        defaultValueAsObject: meta.DefaultValueAsObject === undefined ? null : meta.DefaultValueAsObject,
        timeStampForServer: meta.TimeStampForServer === undefined ? null : meta.TimeStampForServer,
        valueSetType: meta.ValueSetType === undefined ? 0 : meta.ValueSetType
      };
    }
    function termLanguageToGui(lang) {
      return {
        languageCode: lang.LanguageCode,
        languageID: lang.LanguageID,
        languageName: lang.LanguageName,
        isDeleted: !!lang.IsDeleted,
        metaInfos: (lang.MetaInfos || []).map(termMetaToGui),
        termLevelMetaInfos: (lang.TermLevelMetaInfos || []).map(function (term) {
          return {
            termId: term.TermId,
            termText: term.TermText,
            termWildText: term.TermWildText,
            isDeleted: !!term.IsDeleted,
            metaInfos: (term.MetaInfos || []).map(termMetaToGui),
            isMetaListRendered: false
          };
        }),
        isMetaListRendered: false
      };
    }
    function termEntryToGui(entry) {
      return {
        tbGuid: entry.TbGuid,
        readOnlyTB: !!entry.ReadOnlyTb,
        entryId: entry.EntryId,
        prettyPrintHtml: entry.PrettyPrintHtml || '',
        relationships: entry.Relationships || [],
        entryNeedsModeration: false,
        entryLevelMetaInfos: (entry.EntryLevelMetaInfos || []).map(termMetaToGui),
        languageLevelMetaInfos: (entry.LanguageLevelMetaInfos || []).map(termLanguageToGui),
        isMetaListRendered: false
      };
    }

  window.__mdTermsModel = {
    termMetaList: termMetaList,
    termMetaName: termMetaName,
    termMetaValue: termMetaValue,
    termSetMeta: termSetMeta,
    termLanguage: termLanguage,
    termPrimaryTerm: termPrimaryTerm,
    termExamples: termExamples,
    termLanguageTerms: termLanguageTerms,
    termLanguageDetail: termLanguageDetail,
    termEscapeHtml: termEscapeHtml,
    termPatchPrettyHtml: termPatchPrettyHtml,
    termMetaToGui: termMetaToGui,
    termLanguageToGui: termLanguageToGui,
    termEntryToGui: termEntryToGui
  };
})();

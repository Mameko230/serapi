/* 页面选择器规则与基础查询。 */
(function () {
  if (window.__mdPageHelpers) return;
    var PAGE = window.__MD_PAGE_RULES || {};

    function page() { return PAGE[window.__mdDetect.detectEditor()] || null; }
    function pageGridEl() {
      var p = page();
      return (p && p.grid) ? document.querySelector(p.grid) : null;
    }
    function pageConfirmInput() {
      var p = page();
      if (!p || !p.confirm) return null;
      var ids = Array.isArray(p.confirm) ? p.confirm : [p.confirm];
      for (var i = 0; i < ids.length; i++) {
        var el = document.getElementById(ids[i]);
        if (el) return el;
      }
      return null;
    }
    function pageFilterInput(direction) {
      var p = page();
      if (!p) return null;
      return document.getElementById(direction === 'target' ? p.filterTarget : p.filterSource);
    }
    function pagePmList() {
      var p = page();
      return (p && p.proseMirror) ? document.querySelectorAll(p.proseMirror) : [];
    }

  window.__mdPageHelpers = { PAGE: PAGE, page: page, pageGridEl: pageGridEl,
    pageConfirmInput: pageConfirmInput, pageFilterInput: pageFilterInput,
    pagePmList: pagePmList };
})();

# -*- coding: utf-8 -*-
"""引擎页/JS 调用/探针/自检/往返测试生命周期。"""

import json


class RuntimeSelftestMixin:
    def _engine_page(self):
        """定位承载 memoQ 编辑器的页面：优先推送事件追踪到的编辑器页（最可靠），
        退回 URL 启发，最后回退主引擎页。"""
        pid = self._editor_pid
        if pid is not None:
            page = self._pages.get(pid)
            if page is not None:
                return page
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, EngineView):
                u = str(w.url().url())
                if 'Translation.aspx' in u or '/editor/' in u or 'webtrans' in u:
                    return w.page()
        w = self.tabs.currentWidget()
        if isinstance(w, EngineView):
            return w.page()
        return self.web.page()

    def call_js(self, expr: str, callback=None):
        # PyQt6 6.12 + WebEngine 6.140：runJavaScript(expr, None) 在表达式返回
        # undefined 时会触发原生 fail-fast；无回调必须走真正的单参数重载。
        page = self._engine_page()
        if callback is None:
            page.runJavaScript(expr)
        else:
            page.runJavaScript(expr, callback)

    def log(self, s: str):
        # 日志面板已移除：走状态栏 + 进程 stdout（终端/重定向文件里可查）
        try:
            print(f"[serapi] {s}", flush=True)
        except Exception:
            pass
        self.statusBar().showMessage(s, 5000)

    def run_probe_file(self):
        """执行 probe.js（项目根目录），把 JSON 结果打印到日志"""
        import pathlib
        probe = pathlib.Path(__file__).resolve().parent.parent / "probe.js"
        if not probe.exists():
            self.log(f"探针文件不存在: {probe}")
            return
        src = probe.read_text(encoding="utf-8")
        wrapped = ("try{var __r=(function(){" + src + "\n})();"
                   "JSON.stringify(__r,null,1)}catch(__e){'ERR: '+__e.message}")
        self.log(f"> 运行探针 {probe.name}")

        def done(r):
            self.log("⇒ 探针结果：")
            self.log(str(r)[:6000])

        self.call_js(wrapped, done)

    def on_load_finished(self, ok: bool):
        self.log(f"页面加载 {'OK' if ok else '失败'}")

    def run_selftest(self):
        self.log("自检：等待桥接就绪……")
        self._st_tries = 0

        def poll():
            self._st_tries += 1
            if self._st_tries > 40:  # 约 8 秒超时
                self.log("自检超时：桥接未就绪")
                self._selftest_done("timeout")
                return
            self.call_js("window.__md && __md.ready ? __md.api.ping() : 'not-ready'", step2)

        def step2(r2):
            if r2 == "pong":
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(1500, lambda: self._selftest_done(r2))
            else:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(200, poll)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, poll)

    def _selftest_done(self, r):
        from PyQt6.QtWidgets import QApplication
        ok = (r == "pong") and self._bridge_ready
        print("SELFTEST:", "PASS" if ok else f"FAIL ping={r} push={self._bridge_ready}")
        QApplication.instance().quit()

    # ---------------- 持久化补测（--rt-modify 专用，须与 _rt_start 内闭包同生命周期） ----------------
    def _p_reload(self):
        page = self._engine_page()
        self._p_tries = 0
        page.load(page.url())  # 整页刷新：验证写回内容是否落库
        QTimer.singleShot(6000, self._p_phase2_focus)

    def _p_phase2_focus(self):
        self.call_js(f"__md.api.focusSegment({self._rt_row})",
                     lambda _ok: QTimer.singleShot(1500, self._p_phase2_read))

    def _p_phase2_read(self):
        self._p_tries += 1
        if self._p_tries > 20:
            print("ROUNDTRIP: FAIL 持久化验证：刷新后段无法读取", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        self.call_js("JSON.stringify(__md.api.readSegment())", self._p_phase2_check)

    def _p_phase2_check(self, r):
        try:
            res = json.loads(r)
        except Exception:
            res = {"ok": False}
        if not res.get("ok"):
            QTimer.singleShot(1200, self._p_phase2_focus)
            return
        import re as _re
        if _re.sub(r"\D", "", str(res.get("rowNo") or "")) != str(self._rt_row):
            QTimer.singleShot(800, self._p_phase2_focus)  # 还没激活到目标行
            return
        text = "".join(tk.get("v", "") for tk in res.get("tokens") or [] if tk.get("t") == "text")
        if "⟦持久⟧" in text:
            print("ROUNDTRIP: 持久化 PASS（整页刷新后修改仍在，已落库）", flush=True)
            print("ROUNDTRIP: 恢复原内容……", flush=True)
            inner = json.dumps(self._p_orig_tokens, ensure_ascii=False)
            expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)})))"
            self.call_js(expr, self._p_restore_done)
        else:
            print(f"ROUNDTRIP: FAIL 持久化：刷新后未找到标记，读到文本={text[:80]!r}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

    def _p_restore_done(self, r):
        try:
            w = json.loads(r)
        except Exception:
            w = {}
        if not w.get("ok"):
            print(f"ROUNDTRIP: FAIL 恢复写回失败: {w.get('err')}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        QTimer.singleShot(1500, self._p_reload_verify)

    def _p_reload_verify(self):
        page = self._engine_page()
        self._p_tries = 0
        page.load(page.url())
        QTimer.singleShot(6000, self._p_phase3_focus)

    def _p_phase3_focus(self):
        self.call_js(f"__md.api.focusSegment({self._rt_row})",
                     lambda _ok: QTimer.singleShot(1500, self._p_phase3_read))

    def _p_phase3_read(self):
        self._p_tries += 1
        if self._p_tries > 20:
            print("ROUNDTRIP: FAIL 恢复验证：刷新后段无法读取", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        self.call_js("JSON.stringify(__md.api.readSegment())", self._p_phase3_check)

    def _p_phase3_check(self, r):
        from PyQt6.QtWidgets import QApplication
        try:
            res = json.loads(r)
        except Exception:
            res = {"ok": False}
        if not res.get("ok"):
            QTimer.singleShot(1200, self._p_phase3_focus)
            return
        import re as _re
        if _re.sub(r"\D", "", str(res.get("rowNo") or "")) != str(self._rt_row):
            QTimer.singleShot(800, self._p_phase3_focus)
            return
        got = res.get("tokens") or []
        if got == self._p_orig_tokens:
            print("ROUNDTRIP: 恢复 PASS（原内容已写回并落库）", flush=True)
        else:
            print(f"ROUNDTRIP: FAIL 恢复不一致: 期望 {len(self._p_orig_tokens)} tokens，读回 {len(got)}", flush=True)
            print(f"ROUNDTRIP: 期望={json.dumps(self._p_orig_tokens, ensure_ascii=False)[:400]}", flush=True)
            print(f"ROUNDTRIP: 读回={json.dumps(got, ensure_ascii=False)[:400]}", flush=True)
        QApplication.instance().quit()

    # ---------------- 自动往返测试（读 → 原样写回 → 复读比对） ----------------
    def _rt_start(self):
        tokens_ref = [None]
        self._rt_tries = 0
        last_href = [""]

        def fail(msg):
            print(f"ROUNDTRIP: FAIL {msg}", flush=True)
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

        def finish_probe():
            """探针收尾：默认退出；MEMODESK_PROBE_HOLD=1 时保留窗口供 CDP 继续调试。"""
            import os as _os
            if _os.environ.get("MEMODESK_PROBE_HOLD"):
                print("PROBE: HOLD —— 窗口保留，调试完成后手动关闭", flush=True)
                return
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()

        def poll():
            self._rt_tries += 1
            if self._rt_tries > 1200:  # 约 20 分钟（含手动登录时间）
                fail("timeout waiting editor")
                return
            self.call_js("(__md && __md.ready) ? (__md.api.detect() + '@' + location.href) : ('no@' + location.href)", step)

        def step(d):
            if isinstance(d, str) and "@" in d:
                d, href = d.split("@", 1)
            else:
                href = ""
            if href != last_href[0]:
                last_href[0] = href
                print(f"ROUNDTRIP: page -> {href[:130]}", flush=True)
            if d in ("new", "old"):
                if self._probe_js:
                    # 探针模式：尝试点段（部分探针需要编辑器实例），但不等待，1.5s 后直接跑探针
                    print(f"PROBE: editor={d}, focusing segment...", flush=True)
                    self.call_js(f"__md.api.focusSegment({self._rt_row})", lambda _r: QTimer.singleShot(1500, run_probe_file))
                else:
                    print(f"ROUNDTRIP: editor={d}, focusing segment...", flush=True)
                    focus_tries = [0]

                    def after_focus(ok):
                        if ok is True or ok == "true":
                            QTimer.singleShot(800, try_read)
                            return
                        focus_tries[0] += 1
                        if focus_tries[0] > 25:
                            fail("focus: 目标行始终未能激活（点段失败）")
                            return
                        QTimer.singleShot(1000, lambda: self.call_js(
                            f"__md.api.focusSegment({self._rt_row})", after_focus))

                    self.call_js(f"__md.api.focusSegment({self._rt_row})", after_focus)
            else:
                QTimer.singleShot(1000, poll)

        probe_tries = [0]

        def probe_wait_ed():
            # 等编辑器实例真正出现（点击后异步渲染），最多 20 秒
            probe_tries[0] += 1
            if probe_tries[0] > 20:
                print("PROBE: FAIL editor instance never appeared", flush=True)
                finish_probe()
                return

            def check(r):
                try:
                    st = json.loads(r)
                except Exception:
                    st = {}
                if st.get("hasEd"):
                    run_probe_file()
                else:
                    self.call_js(f"__md.api.focusSegment({self._rt_row})", lambda _r: QTimer.singleShot(1000, probe_wait_ed))

            self.call_js("JSON.stringify(__md.api.debugState())", check)

        def run_probe_file():
            try:
                import pathlib
                src = pathlib.Path(self._probe_js).read_text(encoding="utf-8")
            except Exception as e:
                print(f"PROBE: ERR reading file: {e}", flush=True)
                finish_probe()
                return
            # 两步走：先执行并把结果挂到 window.__pr，再单独读回（规避单表达式返回 None 的问题）
            # 注意：探针文件本身是 (function(){...})() 表达式，必须 return 出来，否则外层拿到 undefined
            wrapped = ("window.__pr='step1';try{var __r=(function(){return (" + src +
                       ")})();window.__pr='step2 typeof='+typeof __r;"
                       "window.__pr=String(JSON.stringify(__r,null,1)).slice(0,9000);"
                       "}catch(__e){window.__pr='ERR: '+__e};'probe-done'")
            self.call_js(wrapped, probe_done)

        pr_async_tries = [0]

        def _poll_pr_async():
            pr_async_tries[0] += 1
            if pr_async_tries[0] > 180:
                print("PROBE: async:\n(超时：探针 162 秒内未写出 __prAsync)", flush=True)
                finish_probe()
                return
            self.call_js("window.__prAsync===undefined ? '' : String(window.__prAsync).slice(0,9000)", _pr_async_done)

        def _pr_async_done(r3):
            if r3:
                print(f"PROBE: async:\n{str(r3)[:8000]}", flush=True)
                finish_probe()
            else:
                QTimer.singleShot(900, _poll_pr_async)

        def probe_done(r):
            print(f"PROBE: exec marker={r!r}", flush=True)
            self.call_js("typeof window.__pr + '@' + location.href.slice(0,80) + '@' + String(window.__pr).slice(0,9000)", probe_done2)
            # 异步确认：探针可能通过 setTimeout/setInterval 把二次结果写到 __prAsync（如 moveToRow 激活验证、grid 就绪等待）
            # 轮询等待最多 25 秒（grid 初始化慢，探针内部也可能在等页面状态）
            pr_async_tries[0] = 0
            QTimer.singleShot(800, _poll_pr_async)

        def probe_done2(r2):
            print(f"PROBE: result repr={r2!r}", flush=True)
            if r2:
                print(f"PROBE: result:\n{str(r2)[:8000]}", flush=True)

        read_tries = [0]
        rowid_js = str(self._rt_row - 1)  # UI 行号（1 起）→ 新版编辑器 rowId（0 起）

        def do_verify_read():
            self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_read)

        def try_read():
            read_tries[0] += 1
            if read_tries[0] > 15:  # 约 15 秒
                fail("read: 编辑器实例始终未出现（自动点段失败）")
                return
            self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_read)

        def got_read(r):
            try:
                res = json.loads(r)
            except Exception:
                fail(f"read parse: {str(r)[:300]}")
                return
            if not res.get("ok"):
                err = res.get("err") or ""
                if "未找到" in err and not restored[0] and read_tries[0] <= 15:
                    # 编辑器还没激活：再点一次（点准了快读，没点准慢读以耗尽重试）
                    self.call_js(f"__md.api.focusSegment({self._rt_row})",
                                 lambda ok: QTimer.singleShot(800 if (ok is True or ok == "true") else 1000, try_read))
                    return
                fail(f"read: {err}")
                return
            tokens = res.get("tokens") or []
            # 行号核对（moveToRow 异步生效窗口内可能读到上一行的残留编辑器）
            # 注意 td.order 文本形如 "4."（带句点），需归一化
            import re as _re
            row_no_got = _re.sub(r"\D", "", str(res.get("rowNo") or ""))
            if not restored[0] and row_no_got and row_no_got != str(self._rt_row) and read_tries[0] <= 15:
                print(f"ROUNDTRIP: rowNo={row_no_got} 与目标 {self._rt_row} 不符，重新激活……", flush=True)
                self.call_js(f"__md.api.focusSegment({self._rt_row})",
                             lambda ok: QTimer.singleShot(800, try_read))
                return
            if restored[0]:
                # 恢复验证阶段：只与原始快照比对，绝不再写回
                from PyQt6.QtWidgets import QApplication
                a = tokens_ref[0] or []
                if tokens == a:
                    print(f"ROUNDTRIP: RESTORED （快照 {len(a)} 个 token 已写回，段内容恢复）", flush=True)
                else:
                    print(f"ROUNDTRIP: FAIL restore mismatch: 快照 {len(a)} 个，读回 {len(tokens)} 个", flush=True)
                    print(f"ROUNDTRIP: snapshot={json.dumps(a, ensure_ascii=False)[:600]}", flush=True)
                QApplication.instance().quit()
                return
            tokens_ref[0] = tokens
            if self._rt_modify and not restored[0]:
                # 持久化补测：写入原文+标记，刷新后验证落库
                self._p_orig_tokens = list(tokens)
                tokens_ref[0] = tokens + [{"t": "text", "v": "⟦持久⟧"}]
            print(f"ROUNDTRIP: read ok, {len(tokens)} tokens, rowId={res.get('rowId')}, rowNo={res.get('rowNo')}, trCls={res.get('trCls')}", flush=True)
            print(f"ROUNDTRIP: tokens={json.dumps(tokens_ref[0], ensure_ascii=False)[:600]}", flush=True)
            inner = json.dumps(tokens_ref[0], ensure_ascii=False)
            expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)}), {rowid_js}))"
            self.call_js(expr, got_write)

        def got_write(r2):
            try:
                w = json.loads(r2)
            except Exception:
                fail(f"write parse: {str(r2)[:300]}")
                return
            if not w.get("ok"):
                fail(f"write: {w.get('err')}")
                return
            print("ROUNDTRIP: write dispatched, dumping editor state in 1s...", flush=True)
            QTimer.singleShot(1000, dump_state)

        def dump_state():
            self.call_js("JSON.stringify(__md.api.debugState())", lambda r: after_dump(r))

        def after_dump(r):
            print(f"ROUNDTRIP: state-after-write={str(r)[:800]}", flush=True)
            QTimer.singleShot(1000, lambda: self.call_js(f"JSON.stringify(__md.api.readSegment({rowid_js}))", got_recheck))

        def got_recheck(r3):
            from PyQt6.QtWidgets import QApplication
            try:
                res2 = json.loads(r3)
            except Exception:
                fail(f"recheck parse: {str(r3)[:300]}")
                return
            if not res2.get("ok"):
                fail(f"recheck: {res2.get('err')}")
                return
            a, b = tokens_ref[0] or [], res2.get("tokens") or []
            if a == b:
                print(f"ROUNDTRIP: PASS ({len(b)} tokens identical after write)", flush=True)
                if self._rt_modify and self._p_orig_tokens is not None:
                    print("ROUNDTRIP: 阶段1 PASS，刷新页面验证落库……", flush=True)
                    QTimer.singleShot(500, self._p_reload)
                    return
                QApplication.instance().quit()
                return
            if not restored[0] and a:
                # 写回疑似破坏了段内容：用快照自动恢复一次，然后只读验证
                restored[0] = True
                print("ROUNDTRIP: mismatch! attempting auto-restore of snapshot...", flush=True)
                inner = json.dumps(a, ensure_ascii=False)
                expr = f"JSON.stringify(__md.api.writeSegment(JSON.parse({json.dumps(inner)}), {rowid_js}))"
                self.call_js(expr, lambda _w: QTimer.singleShot(1500, do_verify_read))
                return
            print(f"ROUNDTRIP: FAIL mismatch: wrote {len(a)} tokens, read back {len(b)}", flush=True)
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f"  first diff at token {i}:\n    wrote: {json.dumps(x, ensure_ascii=False)[:300]}\n    read : {json.dumps(y, ensure_ascii=False)[:300]}", flush=True)
                    break
            QApplication.instance().quit()

        restored = [False]
        QTimer.singleShot(500, poll)

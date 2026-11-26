# -*- coding: utf-8 -*-
"""检测更新：只查询 GitHub 最新 Release，不下载、不执行任何东西。

- 数据源：GET https://api.github.com/repos/Mameko230/serapi/releases/latest
  （公开仓库无需 token；未认证 60 次/小时；仓库还没有 Release 时返回 404）
- 每日首次自动检查一次；手动检查随时可点。结果只用于展示，不改变程序行为。
- 安全边界：只接受 https://github.com/... 的发布页链接；Release 说明按纯文本展示。
"""
import json
import re
from datetime import date

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import (
    QNetworkAccessManager, QNetworkProxyFactory, QNetworkReply, QNetworkRequest,
)

from .version import APP_VERSION

RELEASE_API = "https://api.github.com/repos/Mameko230/serapi/releases/latest"
TIMEOUT_MS = 10000            # 代理慢/断网时不至于一直转圈
MAX_BYTES = 512 * 1024        # 响应体上限，防止异常大包
MAX_NOTES_CHARS = 6000        # Release 说明展示上限（纯文本）

_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$")
_SAFE_HOSTS = ("github.com",)


def parse_version(text):
    """'v1.2.3' → (1,2,3)；'1.2' → (1,2,0)；无法识别 → None。

    预发布后缀（1.2.0-beta）按 1.2.0 处理：/releases/latest 本身不会返回预发布版，
    这里只是兜底，避免奇怪 tag 让比较炸掉。
    """
    match = _VERSION_RE.match(str(text or "").strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def is_newer(remote, current=APP_VERSION):
    """远端版本是否比当前版本新；任一无法解析都按“不更新”处理。"""
    remote_tuple, current_tuple = parse_version(remote), parse_version(current)
    if not remote_tuple or not current_tuple:
        return False
    return remote_tuple > current_tuple


def today_str(today=None):
    return (today or date.today()).isoformat()


def should_auto_check(cfg, today=None):
    """每天首次启动检查一次：上次检查日期不是今天才自动查。"""
    last = str((cfg or {}).get("update_last_checked") or "").strip()
    return last != today_str(today)


def safe_release_url(url):
    """只放行 https://github.com/... 的发布页；其他一律返回空串。"""
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = QUrl(text)
    if not parsed.isValid() or parsed.scheme().lower() != "https":
        return ""
    host = parsed.host().lower()
    if not any(host == h or host.endswith("." + h) for h in _SAFE_HOSTS):
        return ""
    return parsed.toString()


_REASON_TEXT = {
    "no-release": "GitHub 上还没有发布版本（还没有发过 Release）。",
    "network": "无法连接 GitHub（网络或代理不可用）。",
    "timeout": "连接 GitHub 超时，请稍后重试。",
    "too-large": "GitHub 返回的数据异常，已放弃解析。",
    "bad-json": "GitHub 返回的数据无法解析。",
    "exception": "检查更新时发生异常。",
}


def reason_text(reason):
    """检查失败原因 → 给用户看的一句话。"""
    text = str(reason or "")
    if text.startswith("http-"):
        code = text[5:]
        if code == "403":
            return "GitHub 请求过于频繁（未登录每小时 60 次），请稍后再试。"
        return f"GitHub 返回 HTTP {code}。"
    return _REASON_TEXT.get(text, "未知原因。")


def plain_notes(text):
    """Release 说明（Markdown 原文）→ 适合纯文本展示的样子：去掉标题井号/引用/粗体/行内代码标记。"""
    lines = []
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = line.replace("**", "").replace("__", "").replace("`", "")
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def parse_release(payload):
    """GitHub Release JSON → 统一结构；缺 tag_name / 结构不对返回 None。"""
    if not isinstance(payload, dict):
        return None
    tag = str(payload.get("tag_name") or "").strip()
    if not parse_version(tag):
        return None
    notes = plain_notes(payload.get("body"))
    if len(notes) > MAX_NOTES_CHARS:
        notes = notes[:MAX_NOTES_CHARS] + "\n…"
    assets = []
    for asset in payload.get("assets") or []:
        if isinstance(asset, dict) and asset.get("name"):
            assets.append(str(asset["name"]))
    return {
        "version": tag,
        "name": str(payload.get("name") or tag),
        "notes": notes,
        "url": safe_release_url(payload.get("html_url")),
        "assets": assets,
        "published": str(payload.get("published_at") or "")[:10],
    }


def decide(result, skipped_version="", manual=False):
    """检查结果 → 界面动作。

    返回 (action, release)：
      update  发现比当前新的版本，显示「发现新版本」
      latest  已是最新（只有手动检查才需要反馈）
      error   检查失败（只有手动检查才弹）
      silent  静默（自动检查失败 / 已跳过 / 无更新）
    """
    if not isinstance(result, dict) or not result.get("ok"):
        return ("error", None) if manual else ("silent", None)
    release = result.get("release") or {}
    version = str(release.get("version") or "")
    if result.get("newer"):
        if manual or version != str(skipped_version or "").strip():
            return ("update", release)
        return ("silent", release)
    return ("latest", release) if manual else ("silent", release)


class ReleaseChecker(QObject):
    """异步查询最新 Release；每次 check 只发一次 finished(dict)，不抛异常。

    finished 的 payload：
      {ok, manual, reason, release, current, newer}
    """

    finished = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 这台机器必须跟随系统代理（127.0.0.1:7897），否则请求会超时
        QNetworkProxyFactory.setUseSystemConfiguration(True)
        self._nam = QNetworkAccessManager(self)
        self._reply = None
        self._manual = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    def busy(self):
        return self._reply is not None

    def check(self, manual=False):
        """同时只允许一个请求；返回是否真的发起了请求。"""
        if self._reply is not None:
            return False
        self._manual = bool(manual)
        request = QNetworkRequest(QUrl(RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"Serapi/{APP_VERSION}".encode("utf-8"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._on_finished)
        self._timer.start(TIMEOUT_MS)
        return True

    def _emit(self, result):
        self._timer.stop()
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.deleteLater()
        self.finished.emit(result)

    def _on_timeout(self):
        if self._reply is not None:
            self._reply.abort()

    def _on_finished(self):
        reply = self._reply
        if reply is None:
            return
        result = {"ok": False, "manual": self._manual, "reason": "network",
                  "release": None, "current": APP_VERSION, "newer": False}
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            status = int(status) if status is not None else 0
            if not status:
                # 没有 HTTP 状态码才是网络层失败（代理/断网/超时中止）
                result["reason"] = "timeout" if reply.error() == \
                    QNetworkReply.NetworkError.OperationCanceledError else "network"
            elif status == 404:
                result["reason"] = "no-release"       # 仓库还没有发布过版本
            elif status != 200:
                result["reason"] = f"http-{status}"
            else:
                raw = bytes(reply.readAll())
                if len(raw) > MAX_BYTES:
                    result["reason"] = "too-large"
                else:
                    release = parse_release(json.loads(raw.decode("utf-8", "replace")))
                    if release is None:
                        result["reason"] = "bad-json"
                    else:
                        result["ok"] = True
                        result["release"] = release
                        result["newer"] = is_newer(release["version"])
                        result["reason"] = ""
        except Exception:
            result["ok"] = False
            result["reason"] = "exception"
        self._emit(result)

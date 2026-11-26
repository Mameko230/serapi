# -*- coding: utf-8 -*-
"""Serapi 编辑器核心：tag 胶囊 + 多行编辑 + 序列化（token 流 ↔ QTextDocument）

设计要点：
- 换行 tag 在编辑器里就是真正的段落边界（Enter 直接换行，写回时序列化为 {t:'newline'}）
- 所有 tag 都是 ObjectReplacementCharacter 胶囊，原子级：光标进不去、Del/Backspace 整个删
- 标色/加粗等样式 tag 的「视觉效果」作用于后续文本，但 tag 本体仍以胶囊保留，写回原样输出
- 新版编辑器的 marks（bold/italic/underline/sub/super）作为字符格式往返，来源打标防止与样式 tag 混淆
"""
import json
import re

from PyQt6.QtCore import Qt, QRectF, QSizeF, QObject, pyqtSignal
from PyQt6.QtGui import (
    QTextCharFormat, QTextFormat, QColor, QFont, QFontMetricsF, QTextBlockFormat,
    QTextObjectInterface, QPainter, QPen, QTextCursor, QSyntaxHighlighter,
)
from PyQt6.QtWidgets import QTextEdit

OBJ_TAG = QTextFormat.ObjectTypes.UserObject + 1
OBJ_SPACE = QTextFormat.ObjectTypes.UserObject + 2
PAYLOAD = 1          # 胶囊载荷：token JSON
MARK_ORIGIN = 2      # 文本格式来源：True = 编辑器 marks（需随写回输出），False/None = 样式 tag 视觉效果

ORC = "\ufffc"


# ---------------- 规则匹配（与 memoweb-preview 同语义） ----------------
def _esc(s: str) -> str:
    return re.sub(r'[.+?^${}()|[\]\\]', r'\\\g<0>', s)


def tag_norm(s: str) -> str:
    s = str(s or '').strip()
    for pre in ('[/', '/', '['):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    for suf in (']', '='):
        if s.endswith(suf):
            s = s[:-1]
    return s.strip()


def tag_match(pattern: str, name: str, disp: str) -> bool:
    p = (pattern or '').strip()
    if not p:
        return False

    def test(n):
        if not n:
            return False
        if '*' in p:
            rex = '^' + '.*'.join(_esc(tag_norm(x)) for x in p.split('*')) + '$'
            return bool(re.match(rex, n)) or bool(re.match(rex, tag_norm(n)))
        return n == p or tag_norm(n) == tag_norm(p)

    return test(name) or test(disp)


def is_close_tag(name: str, disp: str) -> bool:
    return bool(re.match(r'^\[/', name or '') or re.match(r'^/', name or '')
                or re.match(r'^</', disp or '') or re.match(r'^/', disp or '')
                or '="</' in (name or ''))


def char_weight(ch: str):
    c = ord(ch)
    if 0x20 <= c <= 0x7E:
        return 0.5
    if 0xFF61 <= c <= 0xFF9F:
        return 0.5
    return 1


def count_text(s: str):
    return sum(char_weight(c) for c in s)


def fmt_num(n) -> str:
    return str(int(n)) if float(n).is_integer() else f"{n:.1f}"


def count_term_occurrences(text: str, terms):
    """最长优先、非重叠地统计术语出现次数，返回 {term: count}。

    与 MqEditor.set_term_highlights 同语义：较长术语先占位，短术语若整体落在
    一个已被占用的区间内（例如「短术语」是「长术语」的子串），不再重复计数。
    仅对非空 term 计数；term 内部按 str 归一化。
    """
    terms = {str(t or "") for t in (terms or [])}
    terms.discard("")
    counts = {t: 0 for t in terms}
    if not text or not terms:
        return counts
    occupied = bytearray(len(text))
    for term in sorted(terms, key=len, reverse=True):
        start = 0
        while True:
            found = text.find(term, start)
            if found < 0:
                break
            end = found + len(term)
            if not any(occupied[found:end]):
                counts[term] += 1
                occupied[found:end] = b"\x01" * len(term)
            start = found + 1
    return counts


# ---------------- 胶囊绘制 ----------------
def _name_hue(name: str) -> int:
    """同一 tag 名稳定落到同一色相（好认：颜色即类别）"""
    h = 0
    for ch in (name or '?'):
        h = (h * 131 + ord(ch)) % 360
    return h


def tag_attrs_text(attrs) -> str:
    """tag 属性展示：旧版是字符串；新版是 PM attrs dict。

    PM 的 attributes 可能是 list 或 dict，元素形如
    ``{"type": 1, "value": "2", "name": "displaytext"}``；dict 形态还要再取一层 value。
    """
    if not attrs:
        return ''
    if isinstance(attrs, str):
        return attrs.strip()
    if not isinstance(attrs, dict):
        return str(attrs).strip()

    def value_text(item):
        if isinstance(item, dict):
            inner = item.get('value')
            if isinstance(inner, dict):
                inner = inner.get('value')
            return '' if inner is None else str(inner)
        return str(item)

    items = []
    raw = attrs.get('attributes')
    if isinstance(raw, list):
        for item in raw:
            name = str((item or {}).get('name') or '').strip() if isinstance(item, dict) else ''
            text = value_text(item)
            if text:
                items.append(f'{name}="{text}"' if name else text)
    elif isinstance(raw, dict):
        for name, item in raw.items():
            text = value_text(item)
            if text:
                items.append(f'{name}="{text}"' if name else text)
    return ' '.join(items).strip()


class TagObject(QTextObjectInterface, QObject):
    """tag 胶囊：memoQ 新版风格药丸。短=编号，长=名称+编号；
    颜色按 tag 名稳定哈希（标色/占位/隐藏规则仍优先）
    注意：必须接口在前继承（PyQt6 的 qobject cast 要求），且 __init__ 要用 super() 链——
    显式 QObject.__init__(self) 会打断接口包装，Qt 永远不调绘制"""

    def __init__(self, cfg_get):
        super().__init__()
        self.cfg_get = cfg_get

    def intrinsicSize(self, doc, posInDocument, fmt):
        try:
            payload = json.loads(fmt.property(PAYLOAD) or '{}')
            text = self._label(payload)
        except Exception:
            return QSizeF(20, 15)
        f = QFont("Microsoft YaHei", 7)
        w = QFontMetricsF(f).horizontalAdvance(text) + 8
        return QSizeF(w, 15)

    @staticmethod
    def _attrs_text(attrs) -> str:
        return tag_attrs_text(attrs)

    def _label(self, p: dict) -> str:
        try:
            kind = p.get('tagKind')
            if not kind:
                # 新版 tag token 来自 ProseMirror，每个 tag 节点是独立标记，没有开/闭语义；
                # 用 tagType（如 inline-closed）识别，避免把成对 tag 误标成 "{...}"。
                if p.get('tagType'):
                    kind = 'empty'
                else:
                    kind = 'close' if is_close_tag(p.get('name', ''), p.get('display', '')) else 'open'
            mode = (self.cfg_get() or {}).get('tagDisplay', 'long')
            if p.get('ph'):
                core = "■"
            else:
                name = re.sub(r'^\[|\]$', '', str(p.get('name') or '?'))
                name = re.sub(r'^/', '', name).strip() or '?'
                if mode == 'short':
                    # 旧版用 NumID；新版 tag token 没有 id，退化为 memoQ 的 displayText
                    # （就是段内看到的 tag 显示文本，例如 "1"/"2"），不能显示成 "?"。
                    core = str(p.get('id') or p.get('display') or '?')
                    if len(core) > 8:
                        core = core[:7] + '…'
                else:
                    # memoQ 长显风格：名称 + 完整属性（mq:ch val=" "）
                    attrs = self._attrs_text(p.get('attrs'))
                    disp = str(p.get('display') or '').strip()
                    core = f"{name} {attrs}" if attrs else f"{name} {disp}".strip()
                    if len(core) > 36:
                        core = core[:35] + '…'
            if p.get('nl'):
                return core
            if kind == 'open':
                return "{" + core
            if kind == 'close':
                return core + "}"
            return core
        except Exception:
            # 绘制期异常在 Qt 里会直接 fail-fast 闪退，宁可退化成文本也不能抛。
            return str(p.get('name') or p.get('display') or 'tag')[:24]

    def _colors(self, p: dict):
        """返回 (文字/边框色, 底色)"""
        if p.get('ph'):
            return QColor("#b45309"), QColor("#fef3c7")
        if p.get('hidden'):
            return QColor("#94a3b8"), QColor("#f1f5f9")
        if p.get('color'):
            c = QColor(p['color'])
            bg = QColor(p['color']); bg.setAlpha(32)
            return c, bg
        hue = _name_hue(p.get('name') or p.get('display') or '?')
        fg = QColor.fromHsv(hue, 160, 130)
        bg = QColor.fromHsv(hue, 120, 255); bg.setAlpha(42)
        return fg, bg

    def drawObject(self, painter: QPainter, rect: QRectF, doc, posInDocument, fmt):
        try:
            payload = json.loads(fmt.property(PAYLOAD) or '{}')
            label = self._label(payload)
            color, bg = self._colors(payload)
            r = QRectF(rect.x() + 1, rect.y() + 2, rect.width() - 2, min(rect.height() - 4, 13))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(r, 3, 3)
            painter.setPen(QPen(color))
            f = QFont("Microsoft YaHei", 7)
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        except Exception:
            # Qt 绘制回调里抛异常会直接导致进程 fail-fast：吞掉并退化绘制。
            try:
                painter.setPen(QPen(QColor("#94a3b8")))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "tag")
            except Exception:
                pass


class SpaceObject(QTextObjectInterface, QObject):
    """空格可视化：memoQ 式蓝色圆点（中线偏下）。
    每个空格是一个原子 ORC 对象：光标进不去、Del/Backspace 整个删、
    序列化时还原成普通空格，写回与字数统计完全等价。"""

    COLOR = QColor("#7aa7e8")

    def __init__(self):
        super().__init__()

    def intrinsicSize(self, doc, posInDocument, fmt):
        fm = QFontMetricsF(doc.defaultFont())
        return QSizeF(fm.horizontalAdvance(" ") + 1, fm.height())

    def drawObject(self, painter: QPainter, rect: QRectF, doc, posInDocument, fmt):
        d = max(3.0, rect.height() * 0.13)
        cx = rect.center().x()
        cy = rect.y() + rect.height() * 0.64   # 视觉中线偏下，像 memoQ
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.COLOR)
        painter.drawEllipse(QRectF(cx - d / 2, cy - d / 2, d, d))


class QuoteHighlighter(QSyntaxHighlighter):
    """给“”加粗/上色，让开闭引号更易分辨。

    已被用户 marks 或样式 tag 明确格式化（加粗/斜体/下划线/标色）的引号
    保持原样，不覆盖——这样引号可以自然并入加粗范围。

    只写布局层附加格式（QTextLayout::setFormats），不改文档字符格式，
    因此不影响 to_tokens、dirty 与光标/选区。
    """

    QUOTES = "“”"

    def __init__(self, doc, color_getter):
        super().__init__(doc)
        self._color_getter = color_getter

    @staticmethod
    def _has_explicit_format(cf):
        if cf.property(MARK_ORIGIN):
            return True
        if cf.fontWeight() >= QFont.Weight.Bold:
            return True
        if cf.fontItalic() or cf.fontUnderline():
            return True
        return cf.hasProperty(QTextFormat.Property.ForegroundBrush)

    def highlightBlock(self, text):
        block = self.currentBlock()
        bpos = block.position()
        spans = []
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                start = frag.position() - bpos
                spans.append((start, start + frag.length(), frag.charFormat()))
            it += 1
        color = self._color_getter()
        for i, ch in enumerate(text):
            if ch not in self.QUOTES:
                continue
            cf = None
            for start, end, fmt in spans:
                if start <= i < end:
                    cf = fmt
                    break
            if cf is not None and self._has_explicit_format(cf):
                continue
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            if color is not None:
                fmt.setForeground(color)
            self.setFormat(i, 1, fmt)


# ---------------- 编辑器 ----------------
class MqEditor(QTextEdit):
    confirmRequested = pyqtSignal()          # Ctrl+Enter：确认并跳下一段
    rejectRequested = pyqtSignal()           # Shift+Enter：拒绝当前段（状态变已拒绝）
    countsChanged = pyqtSignal(str)          # 字数状态文本

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setMouseTracking(True)
        self._quote_color = QColor("#2563eb")
        self._quote_highlighter = QuoteHighlighter(
            self.document(), lambda: self._quote_color)
        from .tooltips import TagTooltipController
        self._tag_tooltip = TagTooltipController(self)
        self.setStyleSheet(
            "QTextEdit { font-family: 'Microsoft YaHei'; font-size: 16px; "
            "padding: 8px; background: #ffffff; }")
        self._cfg = {
            'newlineTags': ['mq:ch'],
            'colorTags': [], 'boldTags': [], 'italicTags': [], 'underlineTags': [],
            'placeholderTags': [], 'hiddenTags': [],
        }
        # 字数限制：手动每行上限 / 行数上限 / 原文逐行对比 / 原文最长行统一限制。
        # 后两种均读取原文，但判定互相独立，也可与手动上限同时启用。
        self._line_limit = 0
        self._max_lines = 0
        self._line_style = "bplus"   # bplus=细分隔线；cells=一行一格
        self._src_counts = None
        self._src_max_limit = 0
        self._nl_ids = []      # 载入时按序记住换行 tag id，写回时按序放回
        # 强引用必须保留：Qt documentLayout 不接管 handler 所有权，
        # 且 PyQt 包装器被 GC 回收后注册会静默失效（胶囊永远不渲染的坑）
        self._tag_handler = TagObject(lambda: self._cfg)
        self.document().documentLayout().registerHandler(OBJ_TAG, self._tag_handler)
        self._space_handler = SpaceObject()
        self.document().documentLayout().registerHandler(OBJ_SPACE, self._space_handler)
        self.textChanged.connect(self._update_counts)
        # 行卡片/当前行高亮是纯视觉层：光标移动时重绘，不改文档内容。
        self.cursorPositionChanged.connect(self.viewport().update)

    def set_line_style(self, style):
        """切换中间编辑框行视觉（B+ 细分隔线 / C 一行一格），立即重排重绘。"""
        style = style if style in ("bplus", "cells") else "bplus"
        if style == self._line_style:
            return
        self._line_style = style
        self._apply_line_readability()
        self.viewport().update()

    def _apply_line_readability(self):
        """B+ / C 共用的行距/字号基础；C 需要更高的行盒来容纳大格子。"""
        fmt = QTextBlockFormat()
        pct = 205 if self._line_style == "cells" else 170
        fmt.setLineHeight(pct, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        margin = 8 if self._line_style == "cells" else 6
        fmt.setTopMargin(margin)
        fmt.setBottomMargin(margin)
        cur = QTextCursor(self.document())
        cur.select(QTextCursor.SelectionType.Document)
        cur.mergeBlockFormat(fmt)

    def _line_cell_rects(self):
        """产出每个视觉行的视口矩形 + 是否当前行；用于自绘行背景卡片。"""
        doc = self.document()
        cur_pos = self.textCursor().position()
        editable = not self.isReadOnly()
        out = []
        block = doc.begin()
        while block.isValid():
            layout = block.layout()
            if layout is not None:
                base = block.position()
                for i in range(layout.lineCount()):
                    line = layout.lineAt(i)
                    pos = base + line.textStart()
                    c = QTextCursor(doc)
                    c.setPosition(pos)
                    rect = self.cursorRect(c)
                    current = bool(
                        editable and pos <= cur_pos
                        <= pos + max(0, line.textLength()))
                    out.append((rect, current))
            block = block.next()
        return out

    def paintEvent(self, event):
        painter = None
        try:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            width = max(0, self.viewport().width() - 14)
            for idx, (rect, current) in enumerate(self._line_cell_rects()):
                if rect.bottom() < 0 or rect.top() > self.viewport().height():
                    continue
                top = rect.top() + 1
                height = max(22.0, float(rect.height()) - 2.0)
                if self._line_style == "cells":
                    # C：一行一格，大格子 + 当前行高亮；文本仍由编辑器自动换行。
                    if current:
                        painter.setBrush(QColor(59, 130, 246, 40))
                        painter.setPen(QPen(QColor(59, 130, 246, 145), 1.3))
                    else:
                        painter.setBrush(QColor(255, 255, 255, 235) if idx % 2 == 0
                                         else QColor(244, 248, 253, 235))
                        painter.setPen(QPen(QColor(220, 230, 242), 1))
                    painter.drawRoundedRect(QRectF(6, top, width, height), 11, 11)
                    if current:
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(37, 99, 235))
                        painter.drawRoundedRect(QRectF(6, top, 4, height), 2, 2)
                else:
                    # B+：去掉斑马纹底色，只保留细分隔线；分隔线再下移几像素，
                    # 给译文行尾（含下伸笔画）留出呼吸空间。
                    sep_y = int(rect.bottom() + 5)
                    if sep_y <= self.viewport().height() + 1:
                        painter.setPen(QPen(QColor(148, 163, 184, 68), 1))
                        painter.drawLine(9, sep_y, int(width + 8), sep_y)
        except Exception:
            pass
        finally:
            if painter is not None:
                painter.end()
        super().paintEvent(event)

    def set_cfg(self, cfg: dict):
        self._cfg = cfg

    def set_quote_color(self, color):
        """更新引号高亮颜色（随编辑器配色），只重排布局层、不改内容。"""
        self._quote_color = QColor(color)
        self._quote_highlighter.rehighlight()

    def set_limits(self, line_limit: float = 0, max_lines: int = 0,
                   src_counts: list | None = None, src_max_limit: float = 0):
        """设置可同时启用的字数限制；src_max_limit 是原文最长行字数。"""
        self._line_limit = float(line_limit or 0)
        self._max_lines = int(max_lines or 0)
        self._src_counts = list(src_counts) if src_counts else None
        self._src_max_limit = float(src_max_limit or 0)
        self._update_counts()

    # ---------- TB 术语高亮（纯视觉层，不写 QTextDocument 字符格式） ----------
    TERM_BG = QColor("#dcecff")

    def set_term_highlights(self, terms):
        """高亮当前文本里的 TB 术语；最长优先、重复命中、重叠不重复涂色。

        ExtraSelection 不属于文档内容：不会改 dirty、token、tag 样式或字数。
        """
        text = self.toPlainText()
        unique = {str(term or "") for term in (terms or []) if str(term or "")}
        occupied = bytearray(len(text))
        selections = []
        for term in sorted(unique, key=len, reverse=True):
            start = 0
            while True:
                found = text.find(term, start)
                if found < 0:
                    break
                end = found + len(term)
                if not any(occupied[found:end]):
                    cur = QTextCursor(self.document())
                    cur.setPosition(found)
                    cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = cur
                    selection.format.setBackground(self.TERM_BG)
                    selections.append(selection)
                    occupied[found:end] = b"\x01" * len(term)
                start = found + 1
        self.setExtraSelections(selections)

    # ---------- 规则匹配 ----------
    def _match_entry(self, kind: str, name: str, disp: str):
        for ent in self._cfg.get(kind) or []:
            pat = ent if isinstance(ent, str) else ent.get('pattern', '')
            if not pat or not tag_match(pat, name, disp):
                continue
            close_pat = '' if isinstance(ent, str) else ent.get('close', '')
            close = bool(close_pat and tag_match(close_pat, name, disp)) or is_close_tag(name, disp)
            return {'entry': ent, 'close': close}
        return None

    def _entry_color(self, ent):
        if isinstance(ent, str):
            return None
        return ent.get('color')

    def _is_newline(self, tk: dict) -> bool:
        name, disp = tk.get('name', ''), tk.get('display', '')
        if not any(tag_match(p, name, disp) for p in self._cfg.get('newlineTags') or []):
            return False
        if name == 'mq:ch' and (tk.get('val') or disp):
            v = tk.get('val') or ''
            return ('\r' in v or '\n' in v) or disp == 'br'
        return True

    # ---------- 空格可视化 ----------
    def _show_spaces(self) -> bool:
        return bool(self._cfg.get('showSpaces'))

    def _ins_space(self, cur: QTextCursor):
        """在光标处放一个空格：开启可视化时为蓝色圆点对象，否则普通空格"""
        if self._show_spaces():
            f = QTextCharFormat()
            f.setObjectType(OBJ_SPACE)
            f.setProperty(PAYLOAD, json.dumps({'sp': True}))
            cur.insertText(ORC, f)
        else:
            cur.insertText(' ')
        return cur

    def _ins_text(self, cur: QTextCursor, text: str, fmt: QTextCharFormat):
        """插入文本：开启空格可视化时把空格拆成圆点对象"""
        v = str(text or '')
        if not self._show_spaces() or ' ' not in v:
            if v:
                cur.insertText(v, fmt)
            return cur
        parts = v.split(' ')
        for i, part in enumerate(parts):
            if i > 0:
                cur = self._ins_space(cur)
            if part:
                cur.insertText(part, fmt)
        return cur

    # ---------- 载入 ----------
    def load_tokens(self, tokens: list):
        doc = self.document()
        doc.clear()
        self._nl_ids = []
        cur = QTextCursor(doc)
        st = {'bold': False, 'italic': False, 'underline': False,
              'color': None, 'sub': False, 'super': False}
        open_names = {}

        def text_fmt(with_origin=False):
            f = QTextCharFormat()
            f.setFontWeight(QFont.Weight.Bold if st['bold'] else QFont.Weight.Normal)
            f.setFontItalic(st['italic'])
            f.setFontUnderline(st['underline'])
            if st['color']:
                f.setForeground(QColor(st['color']))
            if st['sub']:
                f.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
            elif st['super']:
                f.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
            if with_origin:
                f.setProperty(MARK_ORIGIN, True)
            return f

        def insert_tag(payload: dict):
            f = QTextCharFormat()
            f.setObjectType(OBJ_TAG)
            f.setProperty(PAYLOAD, json.dumps(payload, ensure_ascii=False))
            cur.insertText(ORC, f)

        def toggle(key, entry_name, on):
            st[key] = on

        for tk in tokens:
            if tk.get('t') == 'newline' or (tk.get('t') == 'tag' and self._is_newline(tk)):
                # 换行 tag 隐藏为纯行边界（预览框未来做原文/译文对照统一看换行）
                cur.insertBlock()
                for k in st:
                    st[k] = False if k != 'color' else None
                st['color'] = None
                open_names.clear()
                self._nl_ids.append(tk.get('id'))   # 记住换行 tag id（可能为 None）
                continue
            if tk.get('t') == 'text':
                f = text_fmt()
                marks = tk.get('marks') or []
                if marks:
                    f = QTextCharFormat(f)
                    f.setProperty(MARK_ORIGIN, True)
                    if 'bold' in marks:
                        f.setFontWeight(QFont.Weight.Bold)
                    if 'italic' in marks:
                        f.setFontItalic(True)
                    if 'underline' in marks:
                        f.setFontUnderline(True)
                    if 'sub' in marks:
                        f.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSubScript)
                    elif 'super' in marks:
                        f.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignSuperScript)
                cur = self._ins_text(cur, tk.get('v', ''), f)
                continue
            if tk.get('t') != 'tag':
                continue
            name, disp = tk.get('name', ''), tk.get('display', '')
            common = {'id': tk.get('id'), 'tagKind': tk.get('tagKind')}
            # 隐藏：暗灰小胶囊
            if any(tag_match(p, name, disp) for p in self._cfg.get('hiddenTags') or []):
                insert_tag({**common, 'hidden': True, 'name': name, 'display': disp,
                            'tagType': tk.get('tagType', ''), 'val': tk.get('val', ''),
                            'attrs': tk.get('attrs')})
                continue
            # 占位符：■
            if any(tag_match(p, name, disp) for p in self._cfg.get('placeholderTags') or []):
                insert_tag({**common, 'ph': True, 'name': name, 'display': disp,
                            'tagType': tk.get('tagType', ''), 'val': tk.get('val', ''),
                            'attrs': tk.get('attrs')})
                continue
            # 标色（开/关）
            m = self._match_entry('colorTags', name, disp)
            if m:
                if m['close']:
                    st['color'] = None
                    open_names.pop('color', None)
                else:
                    if open_names.get('color') == name:
                        st['color'] = None
                        open_names.pop('color', None)
                    else:
                        st['color'] = self._entry_color(m['entry'])
                        open_names['color'] = name
                insert_tag({**common, 'color': st['color'], 'name': name, 'display': disp,
                            'tagType': tk.get('tagType', ''), 'val': tk.get('val', ''),
                            'attrs': tk.get('attrs')})
                continue
            # 加粗 / 斜体 / 下划线（样式 tag，同样保留胶囊）
            matched = False
            for kind, key in (('boldTags', 'bold'), ('italicTags', 'italic'), ('underlineTags', 'underline')):
                mm = self._match_entry(kind, name, disp)
                if not mm:
                    continue
                matched = True
                if mm['close']:
                    st[key] = False
                    open_names.pop(key, None)
                else:
                    if open_names.get(key) == name:
                        st[key] = False
                        open_names.pop(key, None)
                    else:
                        st[key] = True
                        open_names[key] = name
                break
            insert_tag({**common, 'name': name, 'display': disp, 'styletag': matched,
                        'tagType': tk.get('tagType', ''), 'val': tk.get('val', ''),
                        'attrs': tk.get('attrs')})
        self._apply_line_readability()
        self._update_counts()

    def selected_tokens(self) -> list:
        """把当前选区还原为 token 流；文本可只选一部分，tag/空格对象保持原子性。"""
        cur = self.textCursor()
        if not cur.hasSelection():
            return []
        start, end = sorted((cur.selectionStart(), cur.selectionEnd()))
        doc = self.document()
        tokens = []

        def add_text(value, fmt=None):
            if not value:
                return
            tk = {'t': 'text', 'v': value}
            if fmt is not None and fmt.property(MARK_ORIGIN):
                marks = []
                if fmt.fontWeight() >= QFont.Weight.Bold:
                    marks.append('bold')
                if fmt.fontItalic():
                    marks.append('italic')
                if fmt.fontUnderline():
                    marks.append('underline')
                va = fmt.verticalAlignment()
                if va == QTextCharFormat.VerticalAlignment.AlignSubScript:
                    marks.append('sub')
                elif va == QTextCharFormat.VerticalAlignment.AlignSuperScript:
                    marks.append('super')
                if marks:
                    tk['marks'] = marks
            if (tokens and tokens[-1].get('t') == 'text'
                    and 'marks' not in tokens[-1] and 'marks' not in tk):
                tokens[-1]['v'] += value
            else:
                tokens.append(tk)

        for bi in range(doc.blockCount()):
            block = doc.findBlockByNumber(bi)
            bp = block.position()
            if bp >= end:
                break
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if not frag.isValid():
                    continue
                fp = frag.position()
                a, b = max(start, fp), min(end, fp + frag.length())
                if a >= b:
                    continue
                text = frag.text()
                part = text[a - fp:b - fp]
                f = frag.charFormat()
                ot = f.objectType()
                if ot == OBJ_TAG:
                    p = json.loads(f.property(PAYLOAD) or '{}')
                    if not p.get('nl'):
                        p.setdefault('t', 'tag')
                        tokens.append(p)
                elif ot == OBJ_SPACE:
                    add_text(' ' * max(1, part.count(ORC)))
                else:
                    add_text(part.replace(ORC, ' '), f)
            # QTextDocument 的块分隔符位于块尾；只有选区真正跨过它才输出换行。
            if bi < doc.blockCount() - 1:
                sep = bp + block.length() - 1
                if start <= sep < end:
                    ntk = {'t': 'newline'}
                    if bi < len(self._nl_ids) and self._nl_ids[bi] not in (None, ''):
                        ntk['id'] = self._nl_ids[bi]
                    tokens.append(ntk)
        return tokens

    def insert_tag(self, payload: dict):
        """在光标处插入 tag 胶囊（tag 面板用；payload 需含 name/display 等）"""
        p = dict(payload)
        p.setdefault('t', 'tag')
        cur = self.textCursor()
        f = QTextCharFormat()
        f.setObjectType(OBJ_TAG)
        f.setProperty(PAYLOAD, json.dumps(p, ensure_ascii=False))
        cur.insertText(ORC, f)
        self.setTextCursor(cur)

    def insert_tokens(self, tokens: list) -> bool:
        """在光标处插入 token 流（TM 命中 / 术语插入用）。
        核心约定：编辑器里有选中内容时，先整体删除选中再插入——即「插入并覆盖选中」。
        返回是否有选中被覆盖（供调用方日志/提示）。"""
        cur = self.textCursor()
        had_sel = cur.hasSelection()
        if had_sel:
            cur.removeSelectedText()   # 删除后光标自动落在选区起点
        plain = QTextCharFormat()      # 插入的文本不带样式 tag 残留格式

        def _ins_newline(nid):
            idx = cur.blockNumber()    # 新行边界 = 当前块之后（边界序号 = 块号）
            cur.insertBlock()
            if nid not in (None, ''):
                while len(self._nl_ids) < idx:
                    self._nl_ids.append(None)
                self._nl_ids.insert(idx, nid)

        for tk in tokens or []:
            kind = tk.get('t')
            if kind == 'text':
                cur = self._ins_text(cur, tk.get('v', ''), plain)
            elif kind == 'newline':
                _ins_newline(tk.get('id'))
            elif kind == 'tag':
                if self._is_newline(tk):
                    # 命中规则的空值 tag（mq:ch）= 换行，与 load_tokens 行为一致
                    _ins_newline(tk.get('id'))
                    continue
                f = QTextCharFormat()
                f.setObjectType(OBJ_TAG)
                f.setProperty(PAYLOAD, json.dumps(tk, ensure_ascii=False))
                cur.insertText(ORC, f)
        self.setTextCursor(cur)
        self.ensureCursorVisible()
        return had_sel

    # ---------- 序列化 ----------
    def to_tokens(self) -> list:
        doc = self.document()
        tokens = []
        block_count = doc.blockCount()
        for bi in range(block_count):
            block = doc.findBlockByNumber(bi)
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if not frag.isValid():
                    continue
                f = frag.charFormat()
                ot = f.objectType()
                if ot == OBJ_TAG:
                    p = json.loads(f.property(PAYLOAD) or '{}')
                    if p.get('nl'):
                        continue   # 换行胶囊：由块间 newline token 代表，不重复输出
                    p.setdefault('t', 'tag')
                    tokens.append(p)
                    continue
                if ot == OBJ_SPACE:
                    # 相邻同类 ORC 会被 Qt 合并成一个 fragment，按实际个数还原空格
                    n_sp = max(1, frag.text().count(ORC))
                    v_space = ' ' * n_sp
                    if tokens and tokens[-1].get('t') == 'text' and 'marks' not in tokens[-1]:
                        tokens[-1]['v'] += v_space
                    else:
                        tokens.append({'t': 'text', 'v': v_space})
                    continue
                text = frag.text().replace(ORC, ' ')   # 外部粘贴进来的游离 ORC 兜底为空格
                if not text:
                    continue
                tk = {'t': 'text', 'v': text}
                if f.property(MARK_ORIGIN):
                    marks = []
                    if f.fontWeight() >= QFont.Weight.Bold:
                        marks.append('bold')
                    if f.fontItalic():
                        marks.append('italic')
                    if f.fontUnderline():
                        marks.append('underline')
                    va = f.verticalAlignment()
                    if va == QTextCharFormat.VerticalAlignment.AlignSubScript:
                        marks.append('sub')
                    elif va == QTextCharFormat.VerticalAlignment.AlignSuperScript:
                        marks.append('super')
                    if marks:
                        tk['marks'] = marks
                if (tokens and tokens[-1].get('t') == 'text'
                        and 'marks' not in tokens[-1] and 'marks' not in tk):
                    tokens[-1]['v'] += text
                else:
                    tokens.append(tk)
            if bi < block_count - 1:
                ntk = {'t': 'newline'}
                # 不破坏 _nl_ids（F9 等场景会多次序列化），从副本取
                if bi < len(self._nl_ids):
                    nid = self._nl_ids[bi]
                    if nid is not None and nid != '':
                        ntk['id'] = nid
                tokens.append(ntk)
        return tokens

    # ---------- 字数 ----------
    BG_EXCEED = QColor("#fde8e8")   # 仅超限行保留淡红；正常行透明，融入共享亚克力卡片
    BG_OK = QColor(0, 0, 0, 0)      # 兼容外部引用；正常行实际会清除 BackgroundBrush

    def _update_counts(self):
        doc = self.document()
        weights = []
        for bi in range(doc.blockCount()):
            block = doc.findBlockByNumber(bi)
            w = 0.0
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if not frag.isValid():
                    continue
                f = frag.charFormat()
                ot = f.objectType()
                if ot == OBJ_TAG:
                    p = json.loads(f.property(PAYLOAD) or '{}')
                    if p.get('ph'):
                        w += 1
                    continue
                if ot == OBJ_SPACE:
                    w += 0.5
                    continue
                w += count_text(frag.text().replace(ORC, ' '))
            weights.append(w)
        total = sum(weights)

        # 各限制独立判定，任一规则超出即标红。
        exceed = [False] * len(weights)
        if self._line_limit > 0:
            for i, w in enumerate(weights):
                if w > self._line_limit:
                    exceed[i] = True
        if self._src_counts:
            for i, w in enumerate(weights):
                # 有对应原文行：逐行比字数；译文多出来的行没有原文可对应，也单独标红。
                if i >= len(self._src_counts) or w > self._src_counts[i]:
                    exceed[i] = True
        if self._src_max_limit > 0:
            for i, w in enumerate(weights):
                if w > self._src_max_limit:
                    exceed[i] = True
        total_exceed = bool(self._src_counts) and total > sum(self._src_counts)
        lines_exceed = self._max_lines > 0 and len(weights) > self._max_lines

        # 正常行清除块底色，超限行才涂淡红；不再给正常文字主动刷白。
        # setBlockFormat 会触发 contentsChanged 并把文档置脏，但这里只是视觉重绘：
        # 必须保留进入前的 modified 状态，避免仅查看被后续切行误判为真实编辑。
        was_modified = doc.isModified()
        format_changed = False
        self._visual_formatting = True
        try:
            for bi, ex in enumerate(exceed):
                block = doc.findBlockByNumber(bi)
                bf = block.blockFormat()
                has_bg = bf.hasProperty(QTextFormat.Property.BackgroundBrush)
                cur_bg = bf.background().color() if has_bg else None
                changed = False
                if ex:
                    if not has_bg or cur_bg != self.BG_EXCEED:
                        bf.setBackground(self.BG_EXCEED)
                        changed = True
                elif has_bg:
                    bf.clearProperty(QTextFormat.Property.BackgroundBrush)
                    changed = True
                if changed:
                    cur = QTextCursor(block)
                    cur.setBlockFormat(bf)
                    format_changed = True
        finally:
            self._visual_formatting = False
            if format_changed:
                doc.setModified(was_modified)

        # 状态文本
        parts = []
        for i, w in enumerate(weights):
            s = fmt_num(w)
            if self._line_limit > 0:
                s += f"/{fmt_num(self._line_limit)}"
            elif self._src_counts and i < len(self._src_counts):
                s += f"/{fmt_num(self._src_counts[i])}"
            elif self._src_max_limit > 0:
                s += f"/{fmt_num(self._src_max_limit)}"
            if exceed[i]:
                s = "!" + s
            parts.append(s)
        msg = f"共 {fmt_num(total)} 字"
        if self._src_counts:
            msg += f"/原文 {fmt_num(sum(self._src_counts))}"
        if self._src_max_limit > 0:
            msg += f"/原文最长 {fmt_num(self._src_max_limit)}"
        if len(parts) > 1 or self._line_limit > 0 or self._src_counts or self._src_max_limit > 0:
            msg += f"（行: {' / '.join(parts)}）"
        if total_exceed:
            msg += " 总字数超"
        if lines_exceed:
            msg += f" 超行数({len(weights)}/{self._max_lines})"
        self.countsChanged.emit(msg)

    # ---------- 胶囊悬停：短显时也能查看完整 tag ----------
    def tag_tooltip_at(self, position: int) -> str:
        doc = self.document()
        if position < 0 or position >= doc.characterCount():
            return ''
        cur = QTextCursor(doc)
        cur.setPosition(position)
        payload = None
        if cur.charFormat().objectType() == OBJ_TAG:
            payload = cur.charFormat().property(PAYLOAD)
        elif position > 0:
            cur.setPosition(position - 1)
            if cur.charFormat().objectType() == OBJ_TAG:
                payload = cur.charFormat().property(PAYLOAD)
        if not payload:
            return ''
        p = json.loads(payload or '{}')
        name = str(p.get('name') or p.get('display') or 'tag')
        attrs = tag_attrs_text(p.get('attrs'))
        lines = [name]
        if attrs:
            lines.append(attrs)
        if p.get('id') not in (None, ''):
            lines.append(f"编号：{p.get('id')} · {p.get('tagKind') or p.get('kind') or 'empty'}")
        elif p.get('tagType'):
            lines.append(f"类型：{p.get('tagType')}")
        return '\n'.join(lines)

    def mouseMoveEvent(self, event):
        # 按住左键选字时不弹 tag 提示（选择过程中不用看详情，也别挡视线）
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._tag_tooltip.clear()
            super().mouseMoveEvent(event)
            return
        cur = self.cursorForPosition(event.pos())
        tip = self.tag_tooltip_at(cur.position())
        self._tag_tooltip.update(tip, event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._tag_tooltip.clear()
        super().leaveEvent(event)

    # ---------- 按键 ----------
    def keyPressEvent(self, ev):
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier and ev.key() == Qt.Key.Key_Return:
            self.confirmRequested.emit()
            return
        if (ev.modifiers() & Qt.KeyboardModifier.ShiftModifier
                and not (ev.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                           | Qt.KeyboardModifier.AltModifier))
                and ev.key() == Qt.Key.Key_Return):
            self.rejectRequested.emit()
            return
        # 空格 → 蓝色圆点对象（memoQ 式非打印字符可视化）；Ctrl/Alt+空格不拦
        if (ev.key() == Qt.Key.Key_Space
                and not (ev.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                           | Qt.KeyboardModifier.AltModifier))):
            cur = self._ins_space(self.textCursor())
            self.setTextCursor(cur)
            return
        super().keyPressEvent(ev)

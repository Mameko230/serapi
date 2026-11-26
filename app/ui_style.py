# -*- coding: utf-8 -*-
"""全局 QSS。"""


class UiStyleMixin:
    def _global_stylesheet(self) -> str:
        pal = self._pal
        accent = self._outer["accent"]
        return f"""
            QLabel {{ background: transparent; }}
            QSplitter::handle {{ background: transparent; }}
            QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
            QTabBar::tab {{ padding: 6px 16px; color: {pal['muted']}; background: {pal['panel_bg']};
                           border-top-left-radius: 8px; border-top-right-radius: 8px;
                           margin-right: 4px; }}
            QTabBar::tab:selected {{ color: {accent}; background: {pal['card_bg']}; }}
            QTabBar::tab:hover:!selected {{ color: {pal['body']}; background: {pal['panel_border']}; }}
            QHeaderView::section {{ background: transparent; border: none;
                                   border-bottom: 1px solid rgba(120,130,160,60); padding: 6px 10px;
                                   color: {pal['header']}; font-weight: normal; }}
            QStatusBar {{ color: {pal['header']}; font-size: 12px; background: transparent; border: none; }}
            QToolTip {{ background: {pal['tooltip_bg']}; border: 1px solid {pal['tooltip_border']}; padding: 4px 8px;
                       color: {pal['title']}; }}
            QMessageBox {{ background: #ffffff; }}
            QMessageBox QPushButton {{ background: #ffffff; border: 1px solid #e2e8f2;
                                      border-radius: 8px; padding: 5px 18px; min-width: 64px; }}
            QMessageBox QPushButton:hover {{ background: #eef3fb; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px 0px; }}
            QScrollBar::handle:vertical {{ background: rgba(120,130,160,120); border-radius: 100px;
                                          min-height: 40px; }}
            QScrollBar::handle:vertical:hover {{ background: rgba(120,130,160,180); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{ background: transparent; height: 5px; margin: 0px 2px; }}
            QScrollBar::handle:horizontal {{ background: rgba(120,130,160,120); border-radius: 100px;
                                            min-width: 40px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollArea {{ background: transparent; border: none; }}
            QPlainTextEdit {{ border: 1px solid {pal['panel_border']}; border-radius: 10px;
                             padding: 6px 10px; background: {pal['panel_bg']};
                             selection-background-color: #cfe0fb; color: {pal['body']}; }}
        """

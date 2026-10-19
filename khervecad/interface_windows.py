"""The windows of the Fusion and SolidWorks Interface Styles
(toolbar_style.py): one stylesheet laid over the theme's for EVERY
window and dialog — panels, the object tree, tabs, fields, buttons,
group boxes, scroll bars, docks, the status bar — plus the left panel's
tabs and the 2D / 3D view backgrounds.

- **Fusion** — flat light-grey panels, a white browser tree with a pale
  blue selection, tabs in capitals with a blue underline under a BROWSER
  caption, square fields that turn blue when focused, the default button
  of a dialog filled blue (Fusion's OK), thin scroll bars; the views on
  Fusion's soft grey studio gradient.
- **SolidWorks** — blue-grey bevelled chrome: gradient tabs (icon tabs
  on the left panel, like its manager tabs), a white tree with the
  light-blue selection, raised buttons with a blue edge when hovered,
  group boxes with a shaded caption bar (its property panels); the
  views on the blue-to-white gradient.

On macOS the menu bar and menus are drawn by the system, so their look
cannot follow; their ORGANISATION does (interface_menus.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel

from . import icons, language

#: 3D view backgrounds a style brings (view3d.BACKGROUNDS gains them)
BACKGROUNDS = {"Fusion": ("#f7f8fa", "#c4ccd4"),
               "SolidWorks": ("#b8cde8", "#f8fafc")}
DARK_BACKGROUNDS = {"Fusion": ("#4a4f55", "#2c3035"),
                    "SolidWorks": ("#3c4e66", "#20262e")}

#: the left panel's tabs as icons (SolidWorks' manager tabs)
TAB_ICONS = ["mdi.file-tree-outline", "mdi.cube-outline",
             "mdi.folder-multiple-outline", "mdi.variable",
             "mdi.code-braces"]

_C = {
    ("Fusion", False): dict(
        panel="#f3f3f3", card="#ffffff", line="#d4d4d4", text="#2d2d2d",
        dim="#6b6b6b", accent="#0696d7", select="#d3eaf8",
        hover="#eaf4fb", field="#ffffff", button="#f7f7f7",
        button2="#ececec", view="#eef0f2", view2="#d3d9df"),
    ("Fusion", True): dict(
        panel="#2f2f2f", card="#383838", line="#232323", text="#e3e3e3",
        dim="#a3a3a3", accent="#2ba6e0", select="#28465a",
        hover="#33424c", field="#262626", button="#454545",
        button2="#3b3b3b", view="#40454b", view2="#2a2e33"),
    ("SolidWorks", False): dict(
        panel="#e9edf2", card="#ffffff", line="#a9b3bf", text="#1b1b1b",
        dim="#4a4a4a", accent="#2f6db5", select="#bcd7f3",
        hover="#e3effb", field="#ffffff", button="#fbfcfd",
        button2="#dde3ea", view="#c7d7ec", view2="#f5f8fb"),
    ("SolidWorks", True): dict(
        panel="#3c3f44", card="#46494f", line="#24262a", text="#ececec",
        dim="#c2c2c2", accent="#6f9bd1", select="#3d5f8c",
        hover="#4b5666", field="#2f3236", button="#565a61",
        button2="#44484e", view="#3c4e66", view2="#20262e"),
}


def colours(style, dark):
    return _C[(style, bool(dark))]


def qss(style, dark):
    """The window stylesheet of *style* (appended to the theme's)."""
    c = colours(style, dark)
    if style == "Fusion":
        return f"""
QMainWindow, QDialog, QDockWidget {{ background: {c['panel']}; }}
QWidget {{ color: {c['text']}; }}
QTreeWidget, QTreeView, QListView, QListWidget, QTableView, QTableWidget {{
    background: {c['card']}; border: 1px solid {c['line']};
    border-radius: 0; alternate-background-color: {c['card']}; }}
QTreeWidget::item, QTreeView::item {{ padding: 2px 1px; }}
QTreeView::item:hover, QListView::item:hover {{ background: {c['hover']}; }}
QTreeView::item:selected, QListView::item:selected,
QTableView::item:selected {{ background: {c['select']};
    color: {c['text']}; }}
QHeaderView::section {{ background: {c['panel']}; border: none;
    border-bottom: 1px solid {c['line']}; padding: 4px 6px;
    color: {c['dim']}; font-weight: 700; }}
QTabWidget::pane {{ border: 1px solid {c['line']}; border-radius: 0;
    background: {c['card']}; top: -1px; }}
QTabBar::tab {{ background: transparent; border: none;
    border-bottom: 2px solid transparent; padding: 6px 7px 4px 7px;
    margin-right: 0; color: {c['dim']}; font-weight: 700;
    font-size: 11px; }}
QTabBar::tab:selected {{ color: {c['accent']};
    border-bottom: 2px solid {c['accent']}; background: transparent; }}
QTabBar::tab:hover:!selected {{ color: {c['text']}; background: transparent; }}
QLabel#browserCaption {{ color: {c['dim']}; font-weight: 700;
    font-size: 11px; padding: 0 8px 0 6px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {c['field']}; border: 1px solid {c['line']};
    border-radius: 2px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
QComboBox:hover {{ border-color: {c['accent']}; }}
QPushButton {{ background: {c['button']}; border: 1px solid {c['line']};
    border-radius: 2px; padding: 4px 14px; min-height: 18px; }}
QPushButton:hover {{ background: {c['hover']}; border-color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['select']}; }}
QPushButton:default {{ background: {c['accent']}; color: #ffffff;
    border-color: {c['accent']}; font-weight: 700; }}
QPushButton:default:hover {{ background: #0a84bd; }}
QPushButton:disabled {{ color: {c['dim']}; }}
QGroupBox {{ border: none; border-top: 1px solid {c['line']};
    margin-top: 14px; padding-top: 6px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 2px; padding: 0 4px;
    color: {c['dim']}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 13px;
    height: 13px; }}
QSplitter::handle {{ background: {c['line']}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 1px; }}
QScrollBar::handle:vertical {{ background: {c['line']}; border-radius: 3px;
    min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px;
    margin: 1px; }}
QScrollBar::handle:horizontal {{ background: {c['line']};
    border-radius: 3px; min-width: 30px; }}
QDockWidget::title {{ background: {c['panel']}; padding: 5px 8px;
    border-bottom: 1px solid {c['line']}; }}
QStatusBar {{ background: {c['panel']}; border-top: 1px solid {c['line']};
    color: {c['dim']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']};
    border: 1px solid {c['line']}; padding: 4px; }}
QGraphicsView {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['view']}, stop:1 {c['view2']}); border: none; }}
QMenuBar {{ background: {c['panel']}; border-bottom: 1px solid {c['line']}; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['line']};
    padding: 3px; }}
QMenu::item {{ padding: 4px 22px 4px 12px; border-radius: 0; }}
QMenu::item:selected {{ background: {c['select']}; color: {c['text']}; }}
"""
    return f"""
QMainWindow, QDialog, QDockWidget {{ background: {c['panel']}; }}
QWidget {{ color: {c['text']}; }}
QTreeWidget, QTreeView, QListView, QListWidget, QTableView, QTableWidget {{
    background: {c['card']}; border: 1px solid {c['line']};
    border-radius: 0; alternate-background-color: {c['card']}; }}
QTreeWidget::item, QTreeView::item {{ padding: 1px 1px; }}
QTreeView::item:hover, QListView::item:hover {{ background: {c['hover']}; }}
QTreeView::item:selected, QListView::item:selected,
QTableView::item:selected {{ background: {c['select']};
    color: {c['text']}; border: 1px dotted {c['accent']}; }}
QHeaderView::section {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']}); border: none;
    border-right: 1px solid {c['line']}; border-bottom: 1px solid
    {c['line']}; padding: 3px 6px; }}
QTabWidget::pane {{ border: 1px solid {c['line']}; border-radius: 0;
    background: {c['card']}; top: -1px; }}
QTabBar::tab {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']});
    border: 1px solid {c['line']}; border-bottom: none;
    border-top-left-radius: 3px; border-top-right-radius: 3px;
    padding: 4px 9px; margin-right: -1px; }}
QTabBar::tab:selected {{ background: {c['card']}; }}
QTabBar::tab:hover:!selected {{ background: {c['hover']}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {c['field']}; border: 1px solid {c['line']};
    border-radius: 1px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
QComboBox {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']}); }}
QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']});
    border: 1px solid {c['line']}; border-radius: 3px; padding: 3px 12px;
    min-height: 18px; }}
QPushButton:hover {{ border-color: {c['accent']};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['card']}, stop:1 {c['hover']}); }}
QPushButton:pressed {{ background: {c['select']}; }}
QPushButton:default {{ border: 2px solid {c['accent']}; }}
QPushButton:disabled {{ color: {c['dim']}; }}
QGroupBox {{ border: 1px solid {c['line']}; border-radius: 3px;
    margin-top: 20px; padding-top: 6px; background: {c['card']}; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position:
    top left; left: 0; right: 0; padding: 3px 8px; font-weight: 700;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']});
    border: 1px solid {c['line']}; border-top-left-radius: 3px;
    border-top-right-radius: 3px; }}
QSplitter::handle {{ background: {c['button2']}; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QScrollBar:vertical {{ background: {c['panel']}; width: 13px; margin: 0; }}
QScrollBar::handle:vertical {{ background: qlineargradient(x1:0, y1:0,
    x2:1, y2:0, stop:0 {c['button']}, stop:1 {c['button2']});
    border: 1px solid {c['line']}; border-radius: 2px; min-height: 30px; }}
QScrollBar:horizontal {{ background: {c['panel']}; height: 13px;
    margin: 0; }}
QScrollBar::handle:horizontal {{ background: qlineargradient(x1:0, y1:0,
    x2:0, y2:1, stop:0 {c['button']}, stop:1 {c['button2']});
    border: 1px solid {c['line']}; border-radius: 2px; min-width: 30px; }}
QDockWidget::title {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']}); padding: 4px 8px;
    border: 1px solid {c['line']}; }}
QStatusBar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']});
    border-top: 1px solid {c['line']}; }}
QToolTip {{ background: #ffffe1; color: #000000; border: 1px solid #767676;
    padding: 3px; }}
QGraphicsView {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['view']}, stop:1 {c['view2']}); border: none; }}
QMenuBar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['button']}, stop:1 {c['button2']});
    border-bottom: 1px solid {c['line']}; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['line']};
    padding: 2px; }}
QMenu::item {{ padding: 4px 22px 4px 26px; }}
QMenu::item:selected {{ background: {c['hover']};
    border: 1px solid {c['accent']}; color: {c['text']}; }}
"""


def apply_stylesheet(style, dark):
    """The theme's stylesheet, plus *style*'s windows (None = theme
    only)."""
    from . import style as theme
    app = QApplication.instance()
    if app is None:
        return
    base = theme._template(theme.tokens())
    app.setStyleSheet(base + (qss(style, dark) if style else ""))


# ------------------------------------------------------- left panel
#: painted browser-tab icons (icons_cad_build), in TAB_ICONS' order
TAB_KEYS = ["tab_main", "tab_object", "tab_collections", "tab_variables",
            "tab_code"]


def _tab_icon(i, style, ink):
    """Tab *i*'s painted icon in *style*, else its glyph in *ink*."""
    from . import icons_cad
    if i < len(TAB_KEYS):
        painted = icons_cad.icon(TAB_KEYS[i], style)
        if painted is not None:
            return painted
    glyph = TAB_ICONS[i] if i < len(TAB_ICONS) else "mdi.circle"
    return icons.icon(glyph, ink)


def style_panel(win, style):
    """The left panel's tabs: icons (SolidWorks), capitals under a
    BROWSER caption (Fusion), or as they were."""
    panel = win.builder
    saved = win.__dict__.setdefault("_tab_texts", [
        (panel.tabText(i), panel.tabIcon(i)) for i in range(panel.count())])
    old = panel.cornerWidget(Qt.TopLeftCorner)
    if old is not None:
        panel.setCornerWidget(None, Qt.TopLeftCorner)
        old.deleteLater()
    for i, (text, icon) in enumerate(saved):
        if i >= panel.count():
            break
        if style == "SolidWorks":
            panel.setTabIcon(i, _tab_icon(i, "SolidWorks", "#2f5f99"))
            panel.setTabText(i, "")
            if not panel.tabToolTip(i):
                panel.setTabToolTip(i, text.replace("&", ""))
        elif style == "Fusion":
            # icons, the name in the tooltip (the user: tabs as icons)
            panel.setTabIcon(i, _tab_icon(i, "Fusion", "#0696d7"))
            panel.setTabText(i, "")
            if not panel.tabToolTip(i):
                panel.setTabToolTip(i, text.replace("&", ""))
        else:
            panel.setTabIcon(i, icon)
            panel.setTabText(i, text)
    if style in ("SolidWorks", "Fusion"):
        from PyQt5.QtCore import QSize
        panel.setIconSize(QSize(22, 22))
    if style == "Fusion":
        caption = QLabel(language.tr("BROWSER"), panel)
        caption.setObjectName("browserCaption")
        panel.setCornerWidget(caption, Qt.TopLeftCorner)
        caption.show()


# --------------------------------------------------------- 3D views
def style_views(win, style, dark):
    """The 3D view on the style's background (the classic one comes
    back from the setting saved before)."""
    from PyQt5.QtCore import QSettings
    from . import view3d
    view3d.BACKGROUNDS.update(BACKGROUNDS)
    settings = QSettings("Kherve", "KherveCAD")
    view = win.view3d
    if style in BACKGROUNDS:
        if view.background not in BACKGROUNDS:
            settings.setValue("render_bg_classic", view.background)
        view3d.BACKGROUNDS[style] = (DARK_BACKGROUNDS if dark
                                     else BACKGROUNDS)[style]
        view.background = style            # not saved: the style owns it
    elif view.background in BACKGROUNDS:
        back = settings.value("render_bg_classic", "Slate")
        view.background = back if back in view3d.BACKGROUNDS else "Slate"
    view.update()
    win.view2d.viewport().update()


def style_nav(win, style):
    """Fusion keeps its 3D navigation bar centred along the bottom of
    the canvas; the other styles keep it top-right."""
    bar = getattr(win.view3d, "nav_bar", None)
    if bar is None:
        return
    bar.anchor = "bottom-centre" if style == "Fusion" else "top-right"
    bar.place()

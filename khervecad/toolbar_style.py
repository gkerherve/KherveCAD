"""Interface Style (View ▸ Interface Style, beside Theme): make the two
toolbars look like the CAD program the user knows.

- **KherveCAD** — the classic bars (toolbars.fill_classic).
- **Fusion** — a light quick-access row (file, undo ... Vibe Model) over
  a ribbon whose tabs (SOLID, FORM, CHARACTER, INSPECT) hold panels of
  icons named underneath in capitals; the vertical bar is flat and slim
  with a blue edge on the tool in use and section captions.
- **SolidWorks** — the quick-access row over a CommandManager: large
  buttons named underneath, small ones named beside them, the tabs
  (Features, Sculpt, Character, Evaluate) underneath; bevelled blue
  hover and pressed buttons on both bars.

The first request (2026-10-18) was the toolbars; the second their icons
(icons_cad.py); the third "each of the menus ... also the windows": the
menu bar organised like the program's (interface_menus.py) and every
window's look plus the views' backgrounds (interface_windows.py). The style is a LOOK: every
button is the window's own action, so switching styles keeps shortcuts,
ticks and tooltips. Colours follow the theme's light / dark choice; the
choice persists in QSettings `interface_style`. MCP:
`set_render_options interface_style`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSettings, QSize, Qt
from PyQt5.QtWidgets import QLabel, QSizePolicy, QToolBar, QWidget

from . import language

STYLES = ("KherveCAD", "Fusion", "SolidWorks")
#: the original KherveCAD toolbars and menus
CLASSIC = "KherveCAD"
#: what a new installation starts in (2026-10-19, the user: make the
#: Fusion look the default)
DEFAULT = "Fusion"
#: the menu's words for each style
LABELS = {"KherveCAD": "KherveCAD (classic)", "Fusion": "Fusion",
          "SolidWorks": "SolidWorks"}
SETTING = "interface_style"
_SETTINGS = ("Kherve", "KherveCAD")

#: icon sizes: (vertical bar, quick-access row)
_SIZES = {"Fusion": (QSize(22, 22), QSize(18, 18)),
          "SolidWorks": (QSize(22, 22), QSize(18, 18))}

#: colour tokens per (style, dark)
_COLOURS = {
    ("Fusion", False): dict(
        quick="#eeeeee", quick_line="#d2d2d2", ribbon="#fbfbfb",
        line="#d6d6d6", text="#3c3c3c", dim="#6e6e6e", accent="#0696d7",
        hover="#e4f1fa", hover_line="#b6dbf1", press="#cbe5f6",
        side="#f6f6f6", side_hover="#e6e6e6", side_on="#dcecf8",
        sep="#e1e1e1"),
    ("Fusion", True): dict(
        quick="#2e2e2e", quick_line="#1f1f1f", ribbon="#383838",
        line="#262626", text="#e0e0e0", dim="#a8a8a8", accent="#2ba6e0",
        hover="#3c4a54", hover_line="#2b6d93", press="#285b7a",
        side="#333333", side_hover="#404040", side_on="#2c4a5e",
        sep="#474747"),
    ("SolidWorks", False): dict(
        quick="#f3f5f8", quick2="#dfe4ea", quick_line="#a9b3bf",
        ribbon="#fdfdfe", ribbon2="#e7ebf0", line="#aab4c0",
        text="#1e1e1e", dim="#4a4a4a", tab="#dde3ea", tab_on="#ffffff",
        hover="#fafcff", hover2="#d9e9fb", hover_line="#7ea7d8",
        press="#c3daf5", press_line="#3a78c2", side="#f5f7f9",
        side2="#e0e5eb", sep="#c3cad3", sep2="#ffffff"),
    ("SolidWorks", True): dict(
        quick="#4a4e55", quick2="#3a3d42", quick_line="#26282b",
        ribbon="#45494f", ribbon2="#383b40", line="#26282b",
        text="#e8e8e8", dim="#c0c0c0", tab="#33363a", tab_on="#4f545b",
        hover="#5a6575", hover2="#4b5666", hover_line="#6f9bd1",
        press="#3d5f8c", press_line="#7aa9e6", side="#43464c",
        side2="#383b40", sep="#2a2c2f", sep2="#595d64"),
}


def saved() -> str:
    name = QSettings(*_SETTINGS).value(SETTING, DEFAULT)
    return name if name in STYLES else DEFAULT


def current(win) -> str:
    return getattr(win, "_interface_style", CLASSIC)


def _dark() -> bool:
    from .style import tokens
    return bool(tokens().get("dark"))


def colours(name: str, dark: bool = None) -> dict:
    return _COLOURS[(name, _dark() if dark is None else dark)]


# ------------------------------------------------------------- QSS
def _qss_vertical(name, c):
    if name == "Fusion":
        return f"""
QToolBar#tools_bar {{ background: {c['side']}; border: none;
    border-right: 1px solid {c['line']}; padding: 2px 0; spacing: 0; }}
QToolBar#tools_bar QToolButton {{ border: none; border-radius: 0;
    border-left: 3px solid transparent; padding: 4px 5px 4px 3px;
    margin: 0; background: transparent; }}
QToolBar#tools_bar QToolButton:hover {{ background: {c['side_hover']}; }}
QToolBar#tools_bar QToolButton:pressed,
QToolBar#tools_bar QToolButton:checked {{ background: {c['side_on']};
    border-left: 3px solid {c['accent']}; }}
QToolBar#tools_bar QLabel#caption {{ color: {c['dim']}; font-size: 8px;
    font-weight: 700; padding: 6px 0 1px 0; }}
QToolBar#tools_bar::separator {{ background: {c['sep']}; height: 1px;
    margin: 3px 6px; }}
"""
    return f"""
QToolBar#tools_bar {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 {c['side']}, stop:1 {c['side2']}); border: none;
    border-right: 1px solid {c['line']}; padding: 3px 2px; spacing: 1px; }}
QToolBar#tools_bar QToolButton {{ border: 1px solid transparent;
    border-radius: 2px; padding: 3px; margin: 0 1px;
    background: transparent; }}
QToolBar#tools_bar QToolButton:hover {{ border-color: {c['hover_line']};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['hover']}, stop:1 {c['hover2']}); }}
QToolBar#tools_bar QToolButton:pressed,
QToolBar#tools_bar QToolButton:checked {{ background: {c['press']};
    border-color: {c['press_line']}; }}
QToolBar#tools_bar::separator {{ height: 2px; margin: 4px 3px;
    border-top: 1px solid {c['sep']}; border-bottom: 1px solid {c['sep2']};
    background: transparent; }}
"""


def _qss_quick(name, c):
    if name == "Fusion":
        background = c["quick"]
        hover = f"background: {c['side_hover']};"
        press = f"background: {c['press']};"
    else:
        background = (f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                      f"stop:0 {c['quick']}, stop:1 {c['quick2']})")
        hover = (f"border-color: {c['hover_line']}; background: "
                 f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                 f"stop:0 {c['hover']}, stop:1 {c['hover2']});")
        press = (f"background: {c['press']}; "
                 f"border-color: {c['press_line']};")
    return f"""
QToolBar#options_bar {{ background: {background}; border: none;
    border-bottom: 1px solid {c['quick_line']}; padding: 1px 6px;
    spacing: 1px; }}
QToolBar#options_bar QToolButton {{ border: 1px solid transparent;
    border-radius: 2px; padding: 2px; margin: 0;
    background: transparent; }}
QToolBar#options_bar QToolButton:hover {{ {hover} }}
QToolBar#options_bar QToolButton:pressed,
QToolBar#options_bar QToolButton:checked {{ {press} }}
QToolBar#options_bar::separator {{ width: 1px; margin: 3px 4px;
    background: {c['quick_line']}; }}
"""


def _qss_ribbon(name, c):
    if name == "Fusion":
        return f"""
QToolBar#ribbon_bar {{ background: {c['ribbon']}; border: none;
    border-bottom: 1px solid {c['line']}; padding: 0; spacing: 0; }}
QWidget#ribbon, QWidget#ribbonPage {{ background: {c['ribbon']}; }}
QTabBar#ribbonTabs::tab {{ background: transparent; border: none;
    border-bottom: 2px solid transparent; padding: 5px 10px 3px 10px;
    margin: 0; color: {c['dim']}; font-size: 11px; font-weight: 700; }}
QTabBar#ribbonTabs::tab:selected {{ color: {c['accent']};
    border-bottom: 2px solid {c['accent']}; }}
QTabBar#ribbonTabs::tab:hover:!selected {{ color: {c['text']}; }}
QToolButton#workspace {{ color: {c['accent']}; font-weight: 700;
    font-size: 11px; border: 1px solid {c['line']}; border-radius: 2px;
    padding: 2px 8px; margin: 3px 0 2px 0; background: {c['ribbon']}; }}
QToolButton#workspace::menu-indicator {{ image: none; }}
QWidget#ribbonPage QToolButton {{ border: 1px solid transparent;
    border-radius: 2px; padding: 3px; margin: 0;
    background: transparent; color: {c['text']}; }}
QWidget#ribbonPage QToolButton:hover {{ background: {c['hover']};
    border-color: {c['hover_line']}; }}
QWidget#ribbonPage QToolButton:pressed,
QWidget#ribbonPage QToolButton:checked {{ background: {c['press']};
    border-color: {c['accent']}; }}
QWidget#ribbonPage QToolButton#panelLabel {{ color: {c['dim']};
    font-size: 10px; font-weight: 700; padding: 0 4px 1px 4px; }}
QWidget#ribbonPage QToolButton#panelLabel::menu-indicator {{ image: none; }}
QFrame#panelSep {{ color: {c['sep']}; margin: 4px 2px; }}
"""
    return f"""
QToolBar#ribbon_bar {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['ribbon']}, stop:1 {c['ribbon2']}); border: none;
    border-bottom: 1px solid {c['line']}; padding: 0; spacing: 0; }}
QWidget#ribbon, QWidget#ribbonPage {{ background: transparent; }}
QTabBar#ribbonTabs::tab {{ background: {c['tab']};
    border: 1px solid {c['line']}; border-top: none;
    border-bottom-left-radius: 3px; border-bottom-right-radius: 3px;
    padding: 2px 14px 3px 14px; margin: 0 -1px 2px 0; color: {c['text']};
    font-size: 11px; }}
QTabBar#ribbonTabs::tab:selected {{ background: {c['tab_on']};
    font-weight: 600; }}
QTabBar#ribbonTabs::tab:hover:!selected {{ background: {c['hover2']}; }}
QWidget#ribbonPage QToolButton {{ border: 1px solid transparent;
    border-radius: 2px; padding: 2px 3px; margin: 0;
    background: transparent; color: {c['text']}; font-size: 11px; }}
QWidget#ribbonPage QToolButton#large {{ min-width: 52px; }}
QWidget#ribbonPage QToolButton:hover {{ border-color: {c['hover_line']};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 {c['hover']}, stop:1 {c['hover2']}); }}
QWidget#ribbonPage QToolButton:pressed,
QWidget#ribbonPage QToolButton:checked {{ background: {c['press']};
    border-color: {c['press_line']}; }}
QFrame#panelSep {{ color: {c['sep']}; margin: 3px 3px; }}
"""


# ----------------------------------------------------------- applying
def _clear(bar):
    """Take every action off *bar*; what the bar itself made (separators,
    the wrappers of added widgets) is deleted, the window's actions stay."""
    for act in bar.actions():
        bar.removeAction(act)
        if act.parent() is bar:
            act.deleteLater()


def _ribbon_bar(win):
    bar = getattr(win, "_ribbon_bar", None)
    if bar is None:
        bar = QToolBar("Ribbon", win)
        bar.setObjectName("ribbon_bar")
        bar.setMovable(False)
        bar.setFloatable(False)
        win.addToolBarBreak(Qt.TopToolBarArea)
        win.addToolBar(Qt.TopToolBarArea, bar)
        win._ribbon_bar = bar
    return bar


def _fill_quick(win, bar):
    """The quick-access row: file and undo on the left, Vibe Model at
    the right end."""
    parts = win._bar_parts
    for act in parts["file"]:
        bar.addAction(act)
    bar.addSeparator()
    for act in parts["undo"]:
        bar.addAction(act)
    spacer = QWidget(bar)
    spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    win._vibe_keep = set(bar.actions())
    win._vibe_keep.add(bar.addWidget(spacer))
    bar.addAction(win._vibe_act)
    win._vibe_keep.add(win._vibe_act)
    win._op_groups = {}


def _style_vertical(win, name):
    bar = win._tools_bar
    for act in getattr(win, "_tool_captions", []):
        bar.removeAction(act)
        act.deleteLater()
    win._tool_captions = []
    if name == CLASSIC:
        from .toolbars import ICON_SIZE
        bar.setStyleSheet("")
        bar.setIconSize(ICON_SIZE)
        return
    if name == "Fusion":
        for caption, first in getattr(win, "_tool_sections", []):
            if first is None:
                continue
            label = QLabel(language.tr(caption).upper(), bar)
            label.setObjectName("caption")
            label.setAlignment(Qt.AlignCenter)
            win._tool_captions.append(bar.insertWidget(first, label))
    bar.setIconSize(_SIZES[name][0])
    bar.setStyleSheet(_qss_vertical(name, colours(name)))


def restyle_icons(win, name):
    """Every action that remembers its glyph (toolbars.remember_glyph)
    takes the painted icon of style *name* (icons_cad), or its glyph
    in the style's ink when nothing is painted for it; the classic
    style puts the original icons back."""
    from PyQt5.QtWidgets import QAction
    from . import icons, icons_cad
    classic = win.__dict__.setdefault("_classic_icons", {})
    for act in win.findChildren(QAction):
        glyph = act.property("kc_glyph")
        if not glyph:
            continue
        if act not in classic:
            classic[act] = act.icon()
        if name == CLASSIC:
            act.setIcon(classic[act])
            continue
        key = act.data()
        painted = icons_cad.icon(key, name) if isinstance(key, str) \
            else None
        if painted is None:
            painted = icons.icon(glyph, icons_cad.glyph_color(
                name, act.property("kc_family") or None))
        act.setIcon(painted)


def restyle(win):
    """Colours again (the theme changed light <-> dark); layout kept."""
    name = current(win)
    if name == CLASSIC:
        return
    from . import interface_windows
    interface_windows.apply_stylesheet(name, _dark())
    interface_windows.style_views(win, name, _dark())
    c = colours(name)
    win._tools_bar.setStyleSheet(_qss_vertical(name, c))
    win._options_bar.setStyleSheet(_qss_quick(name, c))
    _ribbon_bar(win).setStyleSheet(_qss_ribbon(name, c))


def apply(win, name: str = None, remember: bool = True):
    """Lay both toolbars out in style *name* (default: the saved one)."""
    name = name if name in STYLES else saved()
    win._interface_style = name
    if remember:
        QSettings(*_SETTINGS).setValue(SETTING, name)
    vibe = bool(getattr(win, "_vibe_act", None)
                and win._vibe_act.isChecked())
    if vibe:
        win.set_vibe_model(False)
    _style_vertical(win, name)
    # icons BEFORE the ribbon: a changed action makes its buttons take
    # the action's text again, which drops the ribbon's short names
    if name != CLASSIC:
        from .ribbon import analysis_actions
        analysis_actions(win)
    restyle_icons(win, name)
    bar = win._options_bar
    _clear(bar)
    ribbon_bar = getattr(win, "_ribbon_bar", None)
    if name == CLASSIC:
        from .toolbars import ICON_SIZE, fill_classic
        fill_classic(win, bar)
        bar.setStyleSheet("")
        bar.setIconSize(ICON_SIZE)
        if ribbon_bar is not None:
            _clear(ribbon_bar)
            ribbon_bar.hide()
        win.ribbon = None
        bar.show()
    else:
        from .ribbon import Ribbon
        _fill_quick(win, bar)
        bar.setIconSize(_SIZES[name][1])
        bar.setStyleSheet(_qss_quick(name, colours(name)))
        ribbon_bar = _ribbon_bar(win)
        _clear(ribbon_bar)
        win.ribbon = Ribbon(win, name, ribbon_bar)
        ribbon_bar.addWidget(win.ribbon)
        ribbon_bar.setStyleSheet(_qss_ribbon(name, colours(name)))
        ribbon_bar.show()
        # Fusion: file / undo / Vibe sit on the ribbon's tab line; the
        # quick row only comes back in Vibe Model, when the ribbon hides
        bar.setVisible(name != "Fusion")
    # the rest of the program: menus organised like the program the
    # style imitates, the windows' look, the views' backgrounds
    from . import interface_menus, interface_windows
    if getattr(win, "_classic_menu_actions", None) is not None or \
            win.menuBar().actions():
        interface_menus.build(win, name)
    interface_windows.apply_stylesheet(
        None if name == CLASSIC else name, _dark())
    interface_windows.style_panel(win, name)
    interface_windows.style_views(win, name, _dark())
    interface_windows.style_nav(win, name)
    if vibe:
        win.set_vibe_model(True)
    for act in getattr(win, "_interface_style_group", None) and \
            win._interface_style_group.actions() or []:
        act.setChecked(act.data() == name)
    return name


def build_menu(win, view_menu):
    """View ▸ Interface Style, ticked on the style in use."""
    from PyQt5.QtWidgets import QAction, QActionGroup
    menu = view_menu.addMenu(language.tr("&Interface Style"))
    group = QActionGroup(win)
    for name in STYLES:
        act = QAction(language.tr(LABELS[name]), win, checkable=True)
        act.setData(name)
        act.setStatusTip(language.tr(
            "Make the toolbars look like {style}.").format(
                style=LABELS[name]))
        act.setChecked(name == current(win))
        act.triggered.connect(lambda _=False, n=name: apply(win, n))
        group.addAction(act)
        menu.addAction(act)
    win._interface_style_group = group
    return menu

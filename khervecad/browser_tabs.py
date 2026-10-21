"""The left panel's tabs: which show, and the Code detached into its own
window (2026-10-21, the user: "the code should be hidden ... click on
the browser itself to get the code; the same for the variables ... a
button to detach the code and see it changing as we add objects").

- Variables and Code start HIDDEN (`DEFAULT_HIDDEN`); a click on the
  BROWSER caption (Fusion), the ⋯ button at the tabs' right end or a
  right-click on the tab bar lists every tab with a tick to show it.
  Remembered in QSettings `browser/hidden` ("none" = all shown).
- The Code tab's Detach button moves the whole Code page (toolbar,
  editor, Apply) into a floating window; it keeps refreshing there as
  the model changes, and closing the window (or Attach) puts it back.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

SETTING = "browser/hidden"
DEFAULT_HIDDEN = ("variables", "code")


def _pages(panel):
    """[(key, widget, label)] in tab order."""
    return [("main", panel._main_page, "Main"),
            ("object", panel.object_tab, "Object"),
            ("collections", panel.collections, "Collections"),
            ("variables", panel.variables, "Variables"),
            ("code", panel._code_page, "Code")]


def hidden():
    from PyQt5.QtCore import QSettings
    value = QSettings("Kherve", "KherveCAD").value(SETTING, None)
    if value is None:
        return set(DEFAULT_HIDDEN)
    if isinstance(value, (list, tuple)):
        value = ",".join(value)
    return {k for k in str(value).split(",") if k and k != "none"}


def _save(keys):
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue(
        SETTING, ",".join(sorted(keys)) or "none")


def apply(panel):
    """Show / hide the tabs as remembered."""
    keys = hidden()
    for key, widget, _label in _pages(panel):
        index = panel.indexOf(widget)
        if index >= 0:
            panel.setTabVisible(index, key not in keys)
    if not panel.isTabVisible(panel.currentIndex()):
        panel.setCurrentIndex(0)


def show_tab(panel, key, on=True, current=False):
    keys = hidden()
    keys.discard(key) if on else keys.add(key)
    _save(keys)
    apply(panel)
    if on and current:
        widget = dict((k, w) for k, w, _l in _pages(panel)).get(key)
        if widget is not None and panel.indexOf(widget) >= 0:
            panel.setCurrentWidget(widget)


def menu(panel, parent=None):
    """Every tab with a tick; ticking one shows it and goes to it."""
    from PyQt5.QtWidgets import QMenu
    m = QMenu(parent or panel)
    m.setTitle(language.tr("Show tabs"))
    keys = hidden()
    for key, widget, label in _pages(panel):
        act = m.addAction(language.tr(label))
        act.setCheckable(True)
        act.setChecked(key not in keys)
        if key == "main":
            act.setEnabled(False)            # the assembly always shows
        act.toggled.connect(lambda on, k=key: show_tab(panel, k, on,
                                                       current=on))
    m.addSeparator()
    detached = getattr(panel, "_code_window", None) is not None
    m.addAction(language.tr("Attach code") if detached
                else language.tr("Detach code into a window"),
                lambda: toggle_detach(panel))
    return m


def install(panel):
    """The ⋯ corner button and the tab bar's right-click."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QToolButton
    button = QToolButton(panel)
    button.setText("⋯")
    button.setAutoRaise(True)
    button.setToolTip(language.tr("Show or hide tabs (Variables, Code…)"))
    button.clicked.connect(lambda: menu(panel).exec_(
        button.mapToGlobal(button.rect().bottomLeft())))
    panel.setCornerWidget(button, Qt.TopRightCorner)
    panel._tabs_button = button
    bar = panel.tabBar()
    bar.setContextMenuPolicy(Qt.CustomContextMenu)
    bar.customContextMenuRequested.connect(
        lambda pos: menu(panel).exec_(bar.mapToGlobal(pos)))
    apply(panel)


def caption_button(panel):
    """Fusion's BROWSER caption as a button opening the same menu."""
    from PyQt5.QtWidgets import QToolButton
    button = QToolButton(panel)
    button.setObjectName("browserCaption")
    button.setText(language.tr("BROWSER") + " ▾")
    button.setAutoRaise(True)
    button.setToolTip(language.tr("Click to show the Variables, Code… "
                                  "tabs"))
    button.clicked.connect(lambda: menu(panel).exec_(
        button.mapToGlobal(button.rect().bottomLeft())))
    return button


# ------------------------------------------------------------- detach
def toggle_detach(panel):
    if getattr(panel, "_code_window", None) is not None:
        attach(panel)
    else:
        detach(panel)


def detach(panel):
    """The Code page in its own window, kept live."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QDialog, QVBoxLayout
    if getattr(panel, "_code_window", None) is not None:
        panel._code_window.raise_()
        return panel._code_window
    page = panel._code_page
    index = panel.indexOf(page)
    if index >= 0:
        panel.removeTab(index)
    win = QDialog(panel.window(), Qt.Window)
    win.setWindowTitle(language.tr("Code — live"))
    win.setAttribute(Qt.WA_DeleteOnClose, False)
    lay = QVBoxLayout(win)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(page)
    page.show()
    win.resize(760, 820)
    win.finished.connect(lambda _r: attach(panel))
    panel._code_window = win
    _sync_button(panel)
    win.show()
    panel.refresh_code(force=True)
    return win


def attach(panel):
    win = getattr(panel, "_code_window", None)
    if win is None:
        return
    panel._code_window = None
    page = panel._code_page
    page.setParent(None)
    panel.addTab(page, language.tr("Code"))
    panel.setTabToolTip(panel.indexOf(page), language.tr(
        "The OpenSCAD program, editable"))
    try:
        win.finished.disconnect()
    except TypeError:
        pass
    win.close()
    win.deleteLater()
    _sync_button(panel)
    apply(panel)
    if "code" not in hidden():
        panel.setCurrentWidget(page)


def is_detached(panel):
    return getattr(panel, "_code_window", None) is not None


def _sync_button(panel):
    act = getattr(panel, "_detach_act", None)
    if act is None:
        return
    from . import icons
    if is_detached(panel):
        act.setIcon(icons.icon("mdi.dock-left"))
        act.setText(language.tr("Attach"))
        act.setToolTip(language.tr("Put the code back in its tab"))
    else:
        act.setIcon(icons.icon("mdi.open-in-new"))
        act.setText(language.tr("Detach"))
        act.setToolTip(language.tr(
            "Open the code in its own window — it keeps changing live "
            "as you add objects and parts"))

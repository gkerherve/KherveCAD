"""The whole ribbon inspection (2026-10-20, the user: "check that every
menu ... look like Fusion and also SolidWorks ... that all those icons do
what they are meant to do and that all the items of the menus are added
into the ribbons").

1. every command of the command menus is on a ribbon, in both styles;
2. every ribbon button wears a PAINTED icon of its style (icons_cad*),
   never a recoloured glyph;
3. every ribbon button, clicked on a document with a cube selected,
   raises nothing and visibly does something.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import sys
import traceback

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (QApplication, QDialog, QDockWidget,
                             QFileDialog, QInputDialog, QMenu, QMessageBox)

from khervecad import icons_cad, ribbon, toolbar_style
from khervecad.interface_menus import norm

#: the menus whose commands belong on the ribbon (File, Edit, View,
#: Window and Help are the window's own, as in the real programs)
SCOPE = {"Fusion": ("Create", "Modify", "Assemble", "Inspect", "Insert",
                    "Utilities"),
         "SolidWorks": ("Insert", "Tools")}
#: menu commands on the ribbon under another name
ALIASES = {"check interference": "interference",
           "check for 3d printing": "print check",
           "library": "part library"}
#: submenus that are the window's own business, not commands
SKIP_SUB = ("Add-Ins", "Open Recent")
#: buttons that may rightly change nothing on a fresh document
QUIET = {"Select"}            # already the tool in use


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1600, 950)
    win.show()
    icons_cad.icon("x", "Fusion")          # every drawing module loaded
    yield win
    toolbar_style.apply(win, toolbar_style.CLASSIC)
    QSettings("Kherve", "KherveCAD").remove(toolbar_style.SETTING)
    win._dirty = False
    win.close()


def _keys(act):
    text = norm(act.text()).replace("&", "")
    out = {text, text.split(" (")[0], ALIASES.get(text, "")}
    if isinstance(act.data(), str):
        out.add("d:" + act.data())
    return out - {""}


def _ribbon_actions(win):
    seen, out = set(), []
    for _k, _f, _s, panels in ribbon.TABS:
        for panel in panels:
            for act in ribbon.panel_actions(win, panel)[1]:
                if act not in seen:
                    seen.add(act)
                    out.append((panel, act))
    return out


@pytest.mark.parametrize("style", ["Fusion", "SolidWorks"])
def test_every_menu_command_is_on_the_ribbon(window, app, style):
    toolbar_style.apply(window, style)
    on = set()
    for _p, act in _ribbon_actions(window):
        on |= _keys(act)
    missing = []

    def walk(menu, path):
        for act in menu.actions():
            if act.isSeparator() or _keys(act) & on:
                continue
            here = path + " ▸ " + act.text().replace("&", "")
            if act.menu() is not None:
                if act.text().replace("&", "") not in SKIP_SUB:
                    walk(act.menu(), here)
            else:
                missing.append(here)

    for top in window.menuBar().actions():
        name = top.text().replace("&", "")
        if name in SCOPE[style]:
            walk(top.menu(), name)
    assert not missing, missing


@pytest.mark.parametrize("style", ["Fusion", "SolidWorks"])
def test_every_ribbon_icon_is_painted_in_its_style(window, app, style):
    toolbar_style.apply(window, style)
    bad = []
    for panel, act in _ribbon_actions(window):
        key = act.property("kc_paint") or act.data()
        if not (isinstance(key, str) and icons_cad.icon(key, style)):
            bad.append(f"{panel}: {act.text()} ({key!r})")
    assert not bad, bad


@pytest.fixture
def kept_settings():
    """Clicking every family's tools makes each remember its last one
    (QSettings toolbar/<family>), and other tests expect the default:
    put every key back as it was."""
    settings = QSettings("Kherve", "KherveCAD")
    before = {k: settings.value(k) for k in settings.allKeys()}
    yield
    for k in settings.allKeys():
        if k not in before:
            settings.remove(k)
    for k, v in before.items():
        settings.setValue(k, v)
    settings.sync()


def test_every_ribbon_button_does_something(window, app, monkeypatch,
                                            kept_settings):
    """Each button, clicked on a document holding a cube that is
    selected: no Python error, and something visible — the model, a
    window, a tool, a dock, a toggle, a message, a dialog asked."""
    toolbar_style.apply(window, "Fusion")
    asked, errors = [], []

    def ask(kind, result):
        def stub(*args, **kwargs):
            asked.append(kind)
            return result
        return staticmethod(stub)

    monkeypatch.setattr(QDialog, "exec_",
                        lambda self: asked.append("dialog") or 0)
    monkeypatch.setattr(QDialog, "exec",
                        lambda self: asked.append("dialog") or 0)
    monkeypatch.setattr(QMenu, "exec_",
                        lambda self, *a, **k: asked.append("menu"))
    for name in ("getOpenFileName", "getSaveFileName", "getOpenFileNames"):
        monkeypatch.setattr(QFileDialog, name, ask("file", ("", "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory",
                        ask("file", ""))
    for name in ("getInt", "getDouble", "getText", "getItem"):
        monkeypatch.setattr(QInputDialog, name, ask("input", (0, False)))
    for name in ("question", "information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, ask("message",
                                                   QMessageBox.No))
    monkeypatch.setattr(sys, "excepthook", lambda *e: errors.append(
        "".join(traceback.format_exception(*e))))

    win = window
    win.model.clear()
    win._add_primitive("cube")
    app.processEvents()
    base = win.model._serialize()

    def reset():
        for w in QApplication.topLevelWidgets():
            if w is not win and w.isVisible():
                w.close()
        win.view3d.edit_tool = None
        win.statusBar().clearMessage()
        win.model.restore_state(base)
        app.processEvents()
        obj = next(iter(win.model.all_components()))
        win.builder.open_component(obj)
        app.processEvents()
        win.builder.object_tab.tree.select_nodes([obj.children[0]])
        app.processEvents()

    def state(act):
        v3 = win.view3d
        return (win.model._serialize(),
                frozenset(id(w) for w in QApplication.topLevelWidgets()
                          if w.isVisible()),
                getattr(win.view2d.scene(), "tool", None),
                type(v3.edit_tool).__name__ if v3.edit_tool else None,
                win.statusBar().currentMessage(),
                getattr(win, "_sketching", False),
                getattr(v3, "cut", None) is not None,
                getattr(v3, "overlay", None),
                frozenset(d.objectName() for d in
                          win.findChildren(QDockWidget) if d.isVisible()),
                act.isChecked())

    silent, broken = [], []
    for panel, act in _ribbon_actions(win):
        if act.menu() is not None:           # opens its own list
            continue
        name = act.text().replace("&", "").split("\t")[0]
        reset()
        asked.clear()
        n_err = len(errors)
        before = state(act)
        act.trigger()
        for _ in range(6):
            app.processEvents()
        if len(errors) > n_err:
            broken.append(f"{panel}: {name}: "
                          + errors[-1].strip().splitlines()[-1])
        elif state(act) == before and not asked and name not in QUIET:
            silent.append(f"{panel}: {name}")
        if act.isCheckable() and act.isChecked():
            act.trigger()                    # a toggle goes back off
    assert not broken, broken
    assert not silent, silent

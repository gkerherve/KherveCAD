"""View ▸ Interface Style: the toolbars as KherveCAD, Fusion or SolidWorks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QLabel, QToolButton

from khervecad import ribbon, toolbar_style, toolbars


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1500, 900)
    win.show()
    yield win
    toolbar_style.apply(win, toolbar_style.DEFAULT)
    QSettings("Kherve", "KherveCAD").remove(toolbar_style.SETTING)
    win._dirty = False
    win.close()


def _ribbon_actions(win):
    return {b.defaultAction() for b in win.ribbon.findChildren(QToolButton)
            if b.defaultAction() is not None}


def _menu_actions(win):
    acts = set()
    for b in win.ribbon.findChildren(QToolButton):
        if b.menu() is not None:
            acts.update(b.menu().actions())
    return acts


def test_classic_is_the_default_and_has_no_ribbon(window):
    assert toolbar_style.current(window) == "KherveCAD"
    assert getattr(window, "ribbon", None) is None
    assert set(window._op_groups) == {k for k, _ops
                                      in toolbars.OPERATION_GROUPS}
    ticked = [a.data() for a in window._interface_style_group.actions()
              if a.isChecked()]
    assert ticked == ["KherveCAD"]


@pytest.mark.parametrize("style", ["Fusion", "SolidWorks"])
def test_every_bar_tool_is_on_the_ribbon(window, app, style):
    toolbar_style.apply(window, style)
    app.processEvents()
    assert QSettings("Kherve", "KherveCAD").value(
        toolbar_style.SETTING) == style
    assert window._ribbon_bar.isVisible()
    on_ribbon = _ribbon_actions(window) | _menu_actions(window)
    parts = window._bar_parts
    wanted = [a for _key, fam in parts["families"] for a in fam]
    wanted += [parts["snap"], window._edit_mesh_act, window._cut_tool_act]
    wanted += parts["docs"]
    missing = [a.text() for a in wanted if a not in on_ribbon]
    assert not missing
    # file, undo and Vibe Model stay on the quick-access row
    quick = [a.text() for a in window._options_bar.actions()
             if a.text()]
    assert quick == ["New", "Open", "Save", "Undo", "Redo", "Vibe Model"]
    assert window.ribbon.tabs.count() == len(ribbon.TABS)
    ticked = [a.data() for a in window._interface_style_group.actions()
              if a.isChecked()]
    assert ticked == [style]


def test_fusion_captions_the_vertical_bar_and_classic_removes_them(window):
    toolbar_style.apply(window, "Fusion")
    captions = [w.text() for w in window._tools_bar.findChildren(QLabel)
                if w.objectName() == "caption" and w.isVisibleTo(
                    window._tools_bar)]
    assert captions == ["SKETCH", "INSPECT", "SOLIDS", "BUILD"]
    toolbar_style.apply(window, "KherveCAD")
    assert not window._tool_captions
    assert window._tools_bar.iconSize() == toolbars.ICON_SIZE
    assert not window._ribbon_bar.isVisible()


def test_switching_back_and_forth_keeps_the_tools_working(window, app):
    """The classic group buttons are rebuilt each time; the old ones
    must leave no slot on the window's actions (a call into a deleted
    button would abort the app)."""
    for style in ("Fusion", "KherveCAD", "SolidWorks", "KherveCAD"):
        toolbar_style.apply(window, style)
        app.processEvents()
    QSettings("Kherve", "KherveCAD").remove("toolbar/transform")
    button = window._op_groups["transform"]
    scale = next(a for a in button.family if a.data() == "scale")
    scale.trigger()
    assert button.defaultAction() is scale
    QSettings("Kherve", "KherveCAD").remove("toolbar/transform")


def test_vibe_model_hides_the_ribbon_but_keeps_the_quick_row(window):
    toolbar_style.apply(window, "SolidWorks")
    window._vibe_act.trigger()
    assert window._ribbon_bar.isHidden()
    shown = {a.text() for a in window._options_bar.actions()
             if a.isVisible() and a.text()}
    assert shown == {"New", "Open", "Save", "Undo", "Redo", "Vibe Model"}
    toolbar_style.apply(window, "Fusion")        # stays in Vibe Model
    assert window._vibe_act.isChecked() and window._ribbon_bar.isHidden()
    window._vibe_act.trigger()
    assert not window._ribbon_bar.isHidden()


def test_solidworks_drops_small_names_when_narrow(window, app):
    toolbar_style.apply(window, "SolidWorks")
    window.ribbon.show_tab("features")
    window.resize(900, 700)
    app.processEvents()
    small = window.ribbon.small[0]
    assert small[0].toolButtonStyle() == 0              # icon only
    window.resize(2200, 900)
    app.processEvents()
    assert small[0].toolButtonStyle() == 2              # beside icon
    assert all("(" not in b.text() for b in small)      # short names


def test_theme_change_restyles_and_mcp_switches(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    out = ex.execute("set_render_options", {"interface_style": "Fusion"})
    assert out["interface_style"] == "Fusion"
    assert window.ribbon is not None and window.ribbon.fusion
    light = window._ribbon_bar.styleSheet()
    toolbar_style.restyle(window)
    assert window._ribbon_bar.styleSheet() == light
    out = ex.execute("set_render_options", {"interface_style": "KherveCAD"})
    assert out["interface_style"] == "KherveCAD" and window.ribbon is None


def test_every_bar_tool_has_a_painted_icon_in_both_styles(app):
    from khervecad import icons_cad
    keys = ([t[0] for t in toolbars.TOOLS + toolbars.MEASURE_TOOLS]
            + toolbars.BAR_PRIMITIVES + toolbars.OPERATIONS
            + ["house_builder", "new", "open", "save", "undo", "redo",
               "vibe_model", "snap_objects", "edit_mesh", "blueprint",
               "bom", "pid", "cut_through"] + list(ribbon._TIPS))
    for style in ("Fusion", "SolidWorks"):
        for key in keys:
            ic = icons_cad.icon(key, style)
            assert ic is not None, (style, key)
            img = ic.pixmap(32, 32).toImage()
            inked = sum(1 for x in range(0, 32, 2) for y in range(0, 32, 2)
                        if img.pixelColor(x, y).alpha() > 40)
            assert inked > 12, (style, key)        # something is drawn
    assert icons_cad.icon("no-such-tool", "Fusion") is None


def test_styles_swap_the_icons_and_classic_puts_them_back(window, app):
    act = window._bar_parts["families"][0][1][0]        # Linear extrude
    classic = act.icon().cacheKey()
    toolbar_style.apply(window, "SolidWorks")
    assert act.icon().cacheKey() != classic
    # the ribbon kept its short names although the icons changed
    names = {b.text() for b in window.ribbon.findChildren(QToolButton)}
    assert "Resize" in names and "Resize (absolute size)" not in names
    toolbar_style.apply(window, "KherveCAD")
    assert act.icon().cacheKey() == classic


@pytest.mark.parametrize("style", ["Fusion", "SolidWorks"])
def test_the_menu_bar_follows_the_style_and_loses_nothing(window, style):
    from khervecad import interface_menus
    assert not interface_menus.unresolved(window,
                                          interface_menus.LAYOUTS[style])
    toolbar_style.apply(window, style)
    titles = [interface_menus.norm(a.text())
              for a in window.menuBar().actions()]
    expected = [interface_menus.norm(t)
                for t, _i in interface_menus.LAYOUTS[style]]
    assert titles == expected
    assert not interface_menus.missing(window)
    toolbar_style.apply(window, "KherveCAD")
    assert [interface_menus.norm(a.text())
            for a in window.menuBar().actions()][:3] == \
        ["file", "edit", "insert"]
    assert not interface_menus.missing(window)


def test_windows_and_views_take_the_style_and_give_it_back(window):
    app = QApplication.instance()
    toolbar_style.apply(window, "SolidWorks")
    assert "QGroupBox::title" in app.styleSheet()
    assert window.view3d.background == "SolidWorks"
    assert window.builder.tabText(0) == ""            # icon tabs
    toolbar_style.apply(window, "Fusion")
    assert window.builder.tabText(0) == "MAIN"
    assert window.view3d.background == "Fusion"
    toolbar_style.apply(window, "KherveCAD")
    assert window.builder.tabText(0) == "Main"
    assert window.view3d.background not in ("Fusion", "SolidWorks")
    assert "QGroupBox::title" not in app.styleSheet()

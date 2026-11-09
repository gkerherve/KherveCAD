"""What going through every tool of the Features, Sketch, Surfaces and
Sheet Metal tabs by hand turned up (2026-11-09, the user: "go through
every tool that is in the ribbon, check manually how it works, explain
in detail how to use it"), and the Library tab asked for with it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import (analysis, icons_cad, mesh, ribbon, ribbon_library,
                       sheet_metal_ops as ops, toolbar_style, tooltips)
from khervecad.mcp_tools import McpToolExecutor

TABS = ("features", "sketch", "surface", "sheetmetal")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _actions(win, tabs):
    out = []
    for key, _f, _s, panels in ribbon.TABS:
        if key in tabs:
            for panel in panels:
                if panel in ribbon.SW_MOVED:      # the imports: Utilities
                    continue
                out += [a for a in ribbon.panel_actions(win, panel)[1]
                        if not a.isSeparator() and a.menu() is None]
    return out


def test_every_tool_of_the_four_tabs_says_how_to_use_it(win):
    """Not just a name and a line: numbered steps, on every tool."""
    bare = []
    for act in _actions(win, TABS):
        key = act.property("kc_paint") or act.data()
        tip = tooltips.TIPS.get(key) if isinstance(key, str) else None
        if not (tip and len(tip) > 2 and tip[2]):
            bare.append(act.text())
    assert not bare, bare


def _click(view, world):
    q = view._project(*view._camera(), world)
    p = QPoint(int(q[0]), int(q[1]))
    QApplication.sendEvent(view, QMouseEvent(
        QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.NoButton,
        Qt.NoModifier))
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(250)


def test_a_part_clicked_with_no_object_open_is_still_moved(win):
    """Add a solid (the Object tab opens on it), undo, then Move/Copy
    and a click on the part: the Object tab's tree could not select a
    part of Main, so the tool asked for the click again, for ever."""
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QTest.qWait(700)
    win._add_primitive("cylinder")
    QTest.qWait(700)
    win.model.undo_stack.undo()
    QTest.qWait(300)
    assert win.builder.active_tree() is not win.builder.tree
    win.view3d.fit()
    win._apply_operation("translate")
    assert win.view3d._pick_cb is not None
    _click(win.view3d, (20, 15, 20))
    assert win.view3d._pick_cb is None
    assert any(n.type == "translate" for n in win.model.root.walk())
    assert win.builder.active_tree() is win.builder.tree


def _volume(model):
    return analysis.mass_properties(mesh.tessellate(model.root))["volume"]


@pytest.mark.parametrize("size, where", [
    ((80, 50, 2), (0, 0, 0)), ((80, 2, 50), (5, 6, 7)),
    ((2, 50, 80), (0, 0, 0))])
def test_a_cube_converted_to_sheet_metal_keeps_its_size_and_place(
        win, size, where):
    """It read a "size" a Cube does not have: every plate became a
    10 mm cube at the origin."""
    m = win.model
    cube = m.add_node("cube", dict(width=size[0], depth=size[1],
                                   height=size[2], x=where[0], y=where[1],
                                   z=where[2]))
    QApplication.processEvents()

    def box():
        tris = mesh.tessellate(m.root)
        pts = [v for t in tris for v in t[:3]]
        return [(min(p[i] for p in pts), max(p[i] for p in pts))
                for i in range(3)]
    before = box()
    body = ops.convert(m, cube)
    QApplication.processEvents()
    assert body.params["thickness"] == 2
    after = box()
    for (a0, a1), (b0, b1) in zip(before, after):
        assert (b0, b1) == pytest.approx((a0, a1), abs=0.01)
    assert _volume(m) == pytest.approx(80 * 50 * 2, rel=0.01)


def test_a_fold_after_flanges_says_what_to_do(win):
    m = win.model
    body = ops.insert_base(m)
    ops.add_flange(m, body, 0, 1, 20.0, 90.0, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError) as err:
        ops.add_fold(m, body, (50, -1), (50, 61), 90.0, 0.0)
    assert "Fold the flat sheet first" in str(err.value)
    assert not body.params.get("folds")              # nothing left behind


# ---------------------------------------------------------- Library tab
@pytest.mark.parametrize("style", ["Fusion", "SolidWorks"])
def test_the_library_tab_holds_every_subject_of_the_library_menu(win,
                                                                 style):
    toolbar_style.apply(win, style, remember=False)
    assert "library" in [t[0] for t in ribbon.TABS]
    on_tab = []
    for key in ribbon_library.PANELS:
        title, acts = ribbon.panel_actions(win, key)
        assert title
        on_tab += acts
    in_menu = [a for a in win._library_menu.actions()
               if not a.isSeparator() and (a.isEnabled() or a.menu())]
    assert on_tab and set(on_tab) == set(in_menu)
    for act in on_tab:
        key = act.property("kc_paint") or act.data()
        assert isinstance(key, str) and icons_cad.icon(key, style), \
            act.text()
        assert "<" in act.toolTip(), act.text()       # a help card
    # the subjects wear their own drawing, not the crate
    named = {a.text().replace("&&", "&"): a.property("kc_paint")
             for a in on_tab if a.menu() is not None}
    assert named["Fasteners & brackets"] == "lib_fasteners"
    assert named["House & home"] == "lib_home"
    assert ribbon_library.GENERIC not in named.values(), named


def test_the_library_tab_shows_in_the_ribbon(win):
    win.ribbon.show_tab("library")
    QTest.qWait(50)
    index = win.ribbon.tabs.currentIndex()
    assert win.ribbon.tabs.tabText(index).replace("&", "") == "Library"

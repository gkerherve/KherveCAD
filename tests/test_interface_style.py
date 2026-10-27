"""View ▸ Interface Style: the toolbars as KherveCAD, Fusion or SolidWorks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QAction, QApplication, QLabel, QToolButton

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
    toolbar_style.apply(win, toolbar_style.CLASSIC)
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


def test_fusion_is_the_default_style(app, monkeypatch):
    monkeypatch.delenv("KHERVECAD_INTERFACE_STYLE", raising=False)
    QSettings("Kherve", "KherveCAD").remove(toolbar_style.SETTING)
    assert toolbar_style.saved() == "Fusion"


def test_fusion_puts_the_3d_nav_bar_bottom_centre(window, app):
    toolbar_style.apply(window, "Fusion")
    app.processEvents()
    bar = window.view3d.nav_bar
    assert bar.anchor == "bottom-centre"
    toolbar_style.apply(window, "KherveCAD")
    assert bar.anchor == "top-right"


def test_classic_has_no_ribbon(window):
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
    extra = ["Select", "Rebuild"] if style == "SolidWorks" else []
    assert quick == ["New", "Open", "Save", "Undo", "Redo"] + extra + \
        ["Vibe Model"]
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
    assert shown - {"Select", "Rebuild"} == {"New", "Open", "Save", "Undo",
                                             "Redo", "Vibe Model"}
    toolbar_style.apply(window, "Fusion")        # stays in Vibe Model
    assert window._vibe_act.isChecked() and window._ribbon_bar.isHidden()
    window._vibe_act.trigger()
    assert not window._ribbon_bar.isHidden()


def test_solidworks_drops_small_names_when_narrow(window, app):
    toolbar_style.apply(window, "SolidWorks")
    window.ribbon.show_tab("features")
    window.resize(900, 700)
    app.processEvents()
    small = window.ribbon.small[window.ribbon.stack.currentIndex()]
    assert small[0].toolButtonStyle() == 0              # icon only
    index = window.ribbon.stack.currentIndex()       # wide enough
    window.resize(window.ribbon._full[index] + 400, 900)
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
    names = {b.text().replace("\n", " ")
             for b in window.ribbon.findChildren(QToolButton)}
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
    assert window.builder.tabText(0) == ""            # icons too
    assert window.builder.tabToolTip(0)          # named on hover
    assert window._tools_bar.isHidden()          # tools on the ribbon
    assert window.view3d.background == "Fusion"
    toolbar_style.apply(window, "KherveCAD")
    assert window.builder.tabText(0) == "Main"
    assert window.view3d.background not in ("Fusion", "SolidWorks")
    assert "QGroupBox::title" not in app.styleSheet()


def test_fusion_shows_one_canvas_and_sketches_in_place(window, app):
    from khervecad import sketch_mode
    from khervecad.view2d import RECT
    toolbar_style.apply(window, "Fusion")
    app.processEvents()
    assert window.view3d.isVisible() and not window.view2d.isVisible()
    sketch_mode.create_action(window).trigger()
    app.processEvents()
    # nothing selected: the planes show in 3D, a click on one sketches
    from khervecad import normal_to, plane_pick
    assert plane_pick.active(window)
    plane_pick.stop(window)
    normal_to.turn_to(window, "Top (XY)")
    for _ in range(60):                        # the camera's turn
        app.processEvents()
        if window.view2d.isVisible():
            break
        import time
        time.sleep(0.02)
    assert window.view2d.isVisible() and not window.view3d.isVisible()
    # no FINISH SKETCH button (the user): another tab leaves the sketch
    assert not window._finish_sketch.isVisible()
    window.ribbon.show_tab("features")
    app.processEvents()
    assert window.view3d.isVisible() and not window.view2d.isVisible()
    window._set_tool(RECT)                     # a drawing tool sketches
    app.processEvents()
    assert window.view2d.isVisible()
    toolbar_style.apply(window, "KherveCAD")   # classic: both, always
    app.processEvents()
    assert window.view2d.isVisible() and window.view3d.isVisible()
    assert not window._finish_sketch.isVisible()


def test_sketch_shows_the_model_in_its_corner(window, app):
    from khervecad import sketch_mode
    toolbar_style.apply(window, "Fusion")
    window.model.add_node("cube")
    sketch_mode.enter(window)
    app.processEvents()
    inset = window._sketch_inset
    assert inset.isVisible() and inset.pixmap() is not None
    inset.mousePressEvent(None)                # a click: back to 3D
    assert window.view3d.isVisible() and not inset.isVisible()


def test_the_hand_pans_the_view_not_the_drawing(window, app):
    from PyQt5.QtCore import QPoint
    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import Qt
    view = window.view2d
    count = len(window.model.root.children)
    view.nav_bar.buttons["hand"].click()
    assert view.hand_pan.on
    h = view.horizontalScrollBar()
    before = h.value()
    port = view.viewport()
    QTest.mousePress(port, Qt.LeftButton, pos=QPoint(200, 150))
    view.hand_pan.eventFilter(port, type("E", (), {
        "type": lambda s: __import__("PyQt5.QtCore").QtCore.QEvent.MouseMove,
        "pos": lambda s: QPoint(120, 150)})())
    QTest.mouseRelease(port, Qt.LeftButton, pos=QPoint(120, 150))
    assert h.value() != before
    assert len(window.model.root.children) == count


def test_the_3d_view_shows_the_sketch_in_its_corner(window, app):
    from khervecad import sketch_mode
    toolbar_style.apply(window, "Fusion")
    window.model.add_node("rect")
    sketch_mode.finish(window)
    app.processEvents()
    mini = window._sketch_mini2d
    assert mini.isVisible() and mini.pixmap() is not None
    mini.mousePressEvent(None)                 # a click: sketch
    assert window.view2d.isVisible() and not mini.isVisible()
    toolbar_style.apply(window, "KherveCAD")
    assert not mini.isVisible()


def test_picking_in_the_tree_frames_it_in_the_sketch(window, app):
    a = window.model.add_node("rect")
    b = window.model.add_node("circle")
    window.model.set_param(b, "x", 900.0)
    app.processEvents()
    view = window.view2d
    for node, x in ((a, 20), (b, 900)):
        window.builder.tree.select_nodes([node])
        app.processEvents()
        centre = view.mapToScene(view.viewport().rect().center())
        assert abs(centre.x() - x) < 40, (node.name, centre.x())


def _orange_share(pixmap):
    """How much of a picture is the sketch's selection orange."""
    img = pixmap.toImage()
    hits = total = 0
    for y in range(0, img.height(), 3):
        for x in range(0, img.width(), 3):
            c = img.pixelColor(x, y)
            total += 1
            if c.red() > 200 and 110 < c.green() < 210 and c.blue() < 150:
                hits += 1
    return hits / max(total, 1)


def test_the_corner_sketch_shows_each_part_picked_in_the_object(
        window, app):
    """Visual: in Fusion's 3D mode, picking a part inside an Object in
    the tree fills the corner sketch with THAT part (an oak's bark, then
    its leaves) — it used to frame on a never-shown 100 px view and the
    corner showed empty grid."""
    from khervecad.mcp_tools import McpToolExecutor
    toolbar_style.apply(window, "Fusion")
    McpToolExecutor(window).execute(
        "apply_code", {"code": (
            "module Pair() {\n"
            "  color(\"brown\") translate([0, 0, 0]) cube([40, 10, 10]);"
            " // Bark\n"
            "  color(\"green\") translate([300, 300, 0]) cube(8);"
            " // Leaf\n"
            "}\nPair();\n")})
    app.processEvents()
    obj = next(n for n in window.model.all_components())
    window.builder.open_component(obj)
    app.processEvents()
    mini = window._sketch_mini2d
    shares = []
    for colour in obj.children:
        window.builder.object_tab.tree.select_nodes([colour])
        app.processEvents()
        mini._timer.stop()
        mini.redraw()
        shares.append(_orange_share(mini.pixmap()))
    # each part fills a good share of the corner, however small or far
    assert all(s > 0.03 for s in shares), shares


#: menu commands on the ribbon under another name (the analysis copies)
_RIBBON_ALIASES = {"check interference": "interference",
                   # the Library menu: its parts are the Part Library's
                   "library": "part library",
                   "check for 3d printing": "print check"}


def test_every_fusion_menu_command_is_on_the_ribbon(window, app):
    """Fusion keeps every Create / Modify / Assemble / Inspect / Insert
    command on a ribbon tab too (2026-10-20, the user: "does all the
    menu make sense? are they all together where they should be?").
    A submenu whose own button is on the ribbon covers its items."""
    from khervecad.interface_menus import norm
    toolbar_style.apply(window, "Fusion")

    def keys(act):
        text = norm(act.text()).replace("&", "")  # "P&ID" either way
        out = {text, text.split(" (")[0], _RIBBON_ALIASES.get(text, "")}
        if isinstance(act.data(), str):
            out.add("d:" + act.data())
        return out - {""}

    on = set()
    for _key, _f, _s, panels in ribbon.TABS:
        for panel in panels:
            for act in ribbon.panel_actions(window, panel)[1]:
                on |= keys(act)
    missing = []

    def walk(menu, path):
        for act in menu.actions():
            if act.isSeparator():
                continue
            here = path + " ▸ " + act.text().replace("&", "")
            if keys(act) & on:
                continue                   # its button (or the submenu's)
            if act.menu() is not None:
                walk(act.menu(), here)
            else:
                missing.append(here)

    for top in window.menuBar().actions():
        name = top.text().replace("&", "")
        if name in ("Create", "Modify", "Assemble", "Inspect", "Insert"):
            walk(top.menu(), name)
    assert not missing, missing


def test_solidworks_also_shows_one_canvas_with_the_other_small(window, app):
    from khervecad import sketch_mode
    toolbar_style.apply(window, "SolidWorks")
    app.processEvents()
    assert window.view3d.isVisible() and not window.view2d.isVisible()
    assert window._sketch_mini2d.isVisible()          # 2D in the corner
    sketch_mode.enter(window)
    app.processEvents()
    assert window.view2d.isVisible() and not window.view3d.isVisible()
    assert window._sketch_inset.isVisible()           # 3D in the corner
    sketch_mode.finish(window)


def test_leaving_the_sketch_keeps_its_size_and_place_in_3d(window, app):
    """Leaving the sketch, the 3D view shows what the sketch showed, at
    the sketch's size — it only turns (the user, 2026-10-21; before, it
    re-framed the picked part, 2026-10-20)."""
    from khervecad import sketch_mode
    from khervecad.mcp_tools import McpToolExecutor
    toolbar_style.apply(window, "Fusion")
    McpToolExecutor(window).execute("apply_code", {"code": (
        "module Pair() {\n"
        "  color(\"brown\") cube([40, 10, 10]); // Bark\n"
        "  color(\"green\") translate([300, 300, 0]) cube(8); // Leaf\n"
        "}\nPair();\n")})
    app.processEvents()
    obj = next(iter(window.model.all_components()))
    window.builder.open_component(obj)
    app.processEvents()
    window.builder.object_tab.tree.select_nodes([obj.children[1]])
    sketch_mode.enter(window)
    app.processEvents()
    v2 = window.view2d
    centre = v2.mapToScene(v2.viewport().rect().center())
    scale = v2.px_per_mm()
    window._sketch_inset.mousePressEvent(None)      # back to 3D
    for _ in range(5):
        app.processEvents()
    view = window.view3d
    plane = v2.scene().plane
    from khervecad import normal_to
    a, b = normal_to.AXES.get(plane, (0, 1))
    assert view.target[a] == pytest.approx(centre.x(), abs=0.5)
    assert view.target[b] == pytest.approx(centre.y(), abs=0.5)
    assert view.distance == pytest.approx(view._focal() / scale, rel=1e-6)


def _selection_box(pixmap):
    """(left, right, width) of the selected shape's blue in a picture,
    or None when there is none."""
    img = pixmap.toImage()
    xs = [x for y in range(0, img.height(), 2)
          for x in range(0, img.width(), 2)
          if (lambda c: c.blue() > 150 and c.blue() - c.red() > 25
              and c.green() > 100)(img.pixelColor(x, y))]
    if not xs:
        return None
    return min(xs), max(xs), img.width()


def test_the_corner_keeps_the_part_after_a_round_trip(window, app):
    """The user's door handle: pick the spring cassette's housing
    cylinder, open the sketch from the corner, come back to 3D — the
    corner must still show that cylinder, whole. It copied the sketch's
    own zoom, squashed in its splitter, and showed a cropped patch."""
    import os
    from khervecad import sketch_mode
    path = os.path.join(os.path.dirname(__file__), "..", "khervecad",
                        "parts", "Detailed parts",
                        "Golden English lever door handle set.kcad")
    toolbar_style.apply(window, "Fusion")
    window.open_any(os.path.abspath(path))
    for _ in range(10):
        app.processEvents()
    obj = next(c for c in window.model.all_components()
               if "cassette" in c.name.lower())
    window.builder.open_component(obj)
    app.processEvents()
    cyl = next(n for n in obj.walk() if n.type == "cylinder")
    window.builder.object_tab.tree.select_nodes([cyl])
    for _ in range(5):
        app.processEvents()
    mini = window._sketch_mini2d
    mini.mousePressEvent(None)                       # open the sketch
    for _ in range(5):
        app.processEvents()
    window._sketch_inset.mousePressEvent(None)       # back to 3D
    for _ in range(5):
        app.processEvents()
    mini._timer.stop()
    mini.redraw()
    box = _selection_box(mini.pixmap())
    assert box is not None                           # the part is there
    left, right, width = box
    assert left > 4 and right < width - 4            # whole, not cropped
    window._dirty = False


def test_closing_the_window_leaves_nothing_keeping_the_app_alive(app):
    """The corner sketch's off-screen twin view was a 'shown' top-level
    window, so KherveCAD kept running after its window closed and could
    not be opened again (the user, 2026-10-20)."""
    from PyQt5.QtCore import Qt
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1400, 850)
    win.show()
    toolbar_style.apply(win, "Fusion")
    win.model.add_node("cube")
    app.processEvents()
    win._sketch_mini2d.redraw()
    win._dirty = False
    win.close()
    app.processEvents()
    keeping = [type(w).__name__ for w in app.topLevelWidgets()
               if w.isVisible() and w.testAttribute(Qt.WA_QuitOnClose)]
    assert not keeping, keeping
    toolbar_style.apply(win, toolbar_style.CLASSIC)


def test_vibe_model_off_keeps_the_solidworks_tool_column_away(window, app):
    """Turning Vibe Model off brought the left tool column back in the
    SolidWorks layout (the user)."""
    toolbar_style.apply(window, "SolidWorks")
    assert not window._tools_bar.isVisibleTo(window)
    window.set_vibe_model(True)
    window.set_vibe_model(False)
    assert not window._tools_bar.isVisibleTo(window)
    toolbar_style.apply(window, "KherveCAD")
    window.set_vibe_model(True)
    window.set_vibe_model(False)
    assert window._tools_bar.isVisibleTo(window)


def test_styles_use_the_programs_own_command_names(window):
    """SolidWorks says Extruded Boss/Base, Fusion Extrude; the classic
    style keeps KherveCAD's names, and every menu path still resolves."""
    from khervecad import interface_menus
    toolbar_style.apply(window, "SolidWorks", remember=False)
    names = {b.text().replace("\n", " ")
             for b in window.ribbon.findChildren(QToolButton)}
    for name in ("Extruded Boss/Base", "Revolved Boss/Base",
                 "Swept Boss/Base", "Lofted Boss/Base", "Trim Entities"):
        assert name in names
    assert interface_menus.unresolved(
        window, interface_menus.SOLIDWORKS) == []
    toolbar_style.apply(window, "Fusion", remember=False)
    names = {b.text().replace("\n", " ")
             for b in window.ribbon.findChildren(QToolButton)}
    assert {"Extrude", "Revolve", "Sweep", "Loft"} <= names
    toolbar_style.apply(window, "KherveCAD", remember=False)
    acts = [a for a in window.findChildren(QAction)
            if a.data() == "rotate_extrude"]
    assert acts and all(a.text() == "Rotate extrude" for a in acts)


def test_large_names_wrap_and_help_follows_the_style(window):
    """A long name under a large icon takes two lines, and the help
    speaks the style's name ("Click Extruded Boss/Base")."""
    from khervecad import ribbon, tooltips
    assert ribbon.two_lines("Extruded Boss/Base") == "Extruded\nBoss/Base"
    assert ribbon.two_lines("Shell") == "Shell"
    toolbar_style.apply(window, "SolidWorks", remember=False)
    tip = tooltips.rich("linear_extrude")
    assert "Extruded Boss/Base" in tip and "Click Linear extrude" not in tip
    act = next(a for a in window.findChildren(QAction)
               if a.data() == "linear_extrude")
    assert "Extruded Boss/Base" in act.toolTip()
    toolbar_style.apply(window, "KherveCAD", remember=False)
    assert "Click Linear extrude" in tooltips.rich("linear_extrude")


def test_tree_rows_and_sketch_panel_follow_solidworks(window):
    """A default-named node reads as SolidWorks' feature ("Boss-Extrude"),
    a typed name is kept; the tabs have no Select button and Smart
    Dimension sits beside Sketch."""
    from khervecad import interface_names, ribbon
    from khervecad.model import CadNode
    toolbar_style.apply(window, "SolidWorks", remember=False)
    node = CadNode("linear_extrude")
    assert interface_names.tree_text(node) == "Boss-Extrude"
    node.name = "Linear extrude 2 [Body]"
    assert interface_names.tree_text(node) == "Boss-Extrude 2 [Body]"
    node.name = "Plate"
    assert interface_names.tree_text(node) == "Plate"
    keys = [a.data() for a in ribbon.panel_actions(window, "sketch")[1]]
    assert keys[:2] == ["create_sketch", "con_dimension"]
    cons = [a.data() for a in ribbon.panel_actions(window,
                                                   "sketch_constrain")[1]]
    assert "con_dimension" not in cons
    large = [b.defaultAction().data()
             for b in window.ribbon.findChildren(QToolButton)
             if b.objectName() == "large" and b.defaultAction()]
    assert "con_dimension" in large and "create_sketch" in large
    from khervecad import stop_tool
    stop = stop_tool.action(window)
    assert all(b.defaultAction() is not stop
               for b in window.ribbon.findChildren(QToolButton))
    toolbar_style.apply(window, "KherveCAD", remember=False)
    node.name = ""
    node.name = "Linear extrude"
    assert interface_names.tree_text(node) == "Linear extrude"


def test_cut_icons_are_painted_when_the_style_is_applied_once(app):
    """The user saw red glyphs: actions made while the ribbon is built
    (the Cut panel) came after the icons were restyled. A fresh window,
    the style applied once, has them painted."""
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        toolbar_style.apply(win, "SolidWorks", remember=False)
        acts = [a for a in win.findChildren(QAction)
                if a.data() in ("extruded_cut", "revolved_cut",
                                "swept_cut", "lofted_cut", "boundary_cut",
                                "hole_wizard")]
        assert len(acts) == 6
        assert all(a.property("kc_painted") == "SolidWorks" for a in acts)
    finally:
        win._dirty = False
        win.close()


def test_solidworks_orders_tabs_like_its_command_manager():
    from khervecad import ribbon
    sw = [t[0] for t in ribbon.tab_order(False)]
    assert sw[:5] == ["features", "sketch", "surface", "sheetmetal",
                      "inspect"]
    assert sorted(sw) == sorted(t[0] for t in ribbon.TABS)
    fusion = [t[0] for t in ribbon.tab_order(True)]
    assert fusion.index("sheetmetal") < fusion.index("character")

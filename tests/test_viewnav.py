"""The floating zoom / pan / focus bars and Vibe Model.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import viewnav


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, s):
    """Two triangles per face of an axis-aligned cube."""
    x1, y1, z1 = x0 + s, y0 + s, z0 + s
    quads = [((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]


def test_3d_bar_zooms_pans_turns_and_focuses(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    far = _box(200, 0, 0, 10)
    view.set_mesh(_box(0, 0, 0, 10) + far, "test")
    view.fit()
    bar = viewnav.attach_3d(view)
    dist = view.distance
    bar.actions["zoom_in"].trigger()
    assert view.distance < dist and view.user_moved
    target = list(view.target)
    viewnav.pan_3d(view, 1, 0)
    assert view.target != target
    assert "right" not in bar.buttons and bar.buttons["hand"].isCheckable()
    yaw = view.yaw
    bar.actions["orbit_left"].trigger()
    assert view.yaw != yaw
    view.set_highlight_mesh(far)                # the far part selected
    bar.actions["focus"].trigger()
    assert abs(view.target[0] - 205) < 1.0
    close_up = view.distance
    view.set_highlight_mesh([])
    bar.actions["focus"].trigger()                # nothing: the whole model
    assert view.distance > 5 * close_up         # both boxes in frame
    assert 0 < view.target[0] < 200


def test_3d_bar_toggles_the_platform_stage(app):
    from PyQt5.QtCore import QSettings
    from khervecad.view3d import View3D
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("render_stage")
    try:
        view = View3D()
        view.set_stage(False)
        bar = viewnav.attach_3d(view)
        button = bar.actions["stage"]           # in View settings
        assert button in bar.buttons["display"].menu().actions()
        assert not button.isChecked()
        button.trigger()
        assert view.stage and button.isChecked()
        view.set_stage(False)                   # the menu, say
        assert not button.isChecked()
    finally:
        if saved is None:
            settings.remove("render_stage")
        else:
            settings.setValue("render_stage", saved)


def test_3d_bar_sits_bottom_centre_and_hides_for_a_pick(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    bar = viewnav.attach_3d(view)
    view.show()                 # Qt holds resize events until shown
    view.resize(800, 500)
    app.processEvents()
    geo = bar.geometry()
    assert abs(geo.center().x() - 400) <= 2 and geo.bottom() > 500 - 30
    # six buttons, not nineteen: the rest are under the arrows
    assert list(bar.buttons) == ["orientation", "fit", "hand", "display"]
    view.start_pick(lambda _d: None, banner="pick")
    assert bar.isHidden()
    view.cancel_pick()
    assert not bar.isHidden()
    view.close()


def test_exploded_view_and_cut_through_left_the_3d_bar(app):
    """2026-11-10, the user: off the view's bar — they are the ribbon's
    (and the View menu's)."""
    from khervecad import toolbar_style
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        bar = win.view3d.nav_bar
        assert "explode" not in bar.buttons and "cut" not in bar.buttons
        assert set(bar.buttons) == {"wireframe", "orientation", "fit",
                                    "hand", "show", "display"}
        assert bar.layout().itemAt(0).widget() is bar.buttons["wireframe"]
        toolbar_style.apply(win, "SolidWorks")
        acts = {a for b in win.findChildren(type(bar.buttons["hand"]))
                for a in [b.defaultAction()] if a is not None}
        assert win._cut_tool_act in acts                # Evaluate
        assert win._explode_act in acts or any(
            a.menu() is win._explode_menu for a in acts)
        # the bar stands above the Cut Through bar while that shows
        win.show()
        win.set_cut(True)
        app.processEvents()
        assert bar.geometry().bottom() < win.view3d.cut_bar.y()
        win.set_cut(False)
        toolbar_style.apply(win, "KherveCAD")
    finally:
        win._dirty = False
        win.close()


def test_hide_show_holds_the_dimensions_planes_axes_and_scale_bar(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        bar = win.view3d.nav_bar
        assert bar.buttons["show"].menu().actions() == [
            win._smart_dims_act, win._ref_planes_act, win._axes_act,
            win._scale_bar_act]
    finally:
        win._dirty = False
        win.close()


def test_3d_bar_carries_the_display_options_menu(app):
    """Platform & shadow, cavity shading, edge lines, scale bar, smooth
    shading, reference overlay and hardware rendering — the View
    menu's own actions, opened from one button on the 3D bar."""
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        bar = win.view3d.nav_bar
        display = bar.buttons["display"]
        expected = [win._stage_act, bar.actions["lighting"],
                    win._cavity_act, win._edges_act, win._smooth_act,
                    win._overlay_act, win._gl_act]
        assert display.menu().actions() == expected
        assert win._cavity_act.isChecked()
        win._cavity_act.trigger()               # on by default: switch off
        assert not win.view3d.cavity
        win.view3d.set_cavity(True)             # the toolbar, say
        assert win._cavity_act.isChecked()
    finally:
        win._dirty = False
        win.close()


def test_2d_bar_zooms_and_focuses_an_offset_part(app):
    from khervecad.model import DocumentModel
    from khervecad.view2d import SketchScene, SketchView
    model = DocumentModel()
    scene = SketchScene(model)
    view = SketchView(scene)
    view.resize(600, 400)
    view.show()
    bar = viewnav.attach_2d(view)
    ppm = view.px_per_mm()
    bar.buttons["zoom_in"].click()
    assert view.px_per_mm() > ppm
    node = model.add_node("rect")
    for key, value in (("x", 500.0), ("y", 300.0), ("width", 40.0),
                       ("height", 20.0)):
        model.set_param(node, key, value)
    app.processEvents()
    bar.buttons["focus"].click()               # nothing selected: all
    centre = view.mapToScene(view.viewport().rect().center())
    assert abs(centre.x() - 520) < 5 and abs(centre.y() - 310) < 5
    h = view.horizontalScrollBar()
    before = h.value()
    bar.buttons["zoom_in"].click()
    viewnav.pan_2d(view, 0.12, 0)
    assert h.value() != before
    assert "right" not in bar.buttons
    view.close()


def test_vibe_model_folds_the_panels_away_and_back(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        assert not win._left_column.isHidden()
        win._vibe_act.trigger()
        assert win._vibe_act.isChecked()
        assert win._left_column.isHidden() and win.view2d.isHidden()
        assert win._tools_bar.isHidden() and not win.view3d.isHidden()
        # the main toolbar keeps file, undo and the toggle itself
        shown = {a.text() for a in win._options_bar.actions()
                 if a.isVisible() and not a.isSeparator()}
        # (and the Options gear, which sits before Vibe Model in every
        # style since 2026-10-29)
        assert shown == {"New", "Open", "Save", "Undo", "Redo",
                         "&Options...", "Vibe Model"}
        win._vibe_act.trigger()
        assert not win._left_column.isHidden()
        assert not win.view2d.isHidden() and not win._tools_bar.isHidden()
        assert all(a.isVisible() for a in win._options_bar.actions())
        win.set_vibe_model(True)                # programmatic: tick follows
        assert win._vibe_act.isChecked()
        win.set_vibe_model(False)
    finally:
        win._dirty = False
        win.close()


def test_sketch_bar_holds_plane_and_grid(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        assert not hasattr(win, "_plane_combo")
        win._plane_buttons["Front (XZ)"].click()
        assert win.scene.plane == "Front (XZ)"
        win._on_plane_auto_changed("Side (YZ)")
        assert win._plane_buttons["Side (YZ)"].isChecked()
        win._grid_step_acts[0.2].trigger()
        assert win.scene.grid_size == 0.2
        win.view2d.nav_bar.buttons["grid"].click()
        assert win.scene.show_grid == win._grid_act.isChecked()
    finally:
        win.close()


def test_view_bar_buttons_have_rich_help(app):
    from khervecad import tooltips
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        for bar in (win.view2d.nav_bar, win.view3d.nav_bar):
            for key, button in bar.buttons.items():
                assert "How to use" in button.toolTip() \
                    or "<b>" in button.toolTip(), key
        assert "Cut through" in tooltips.rich("nav3d_cut")
        acts = [a.data() for a in win.findChildren(type(win._grid_act))]
        assert "fit_sketch" not in acts
    finally:
        win.close()


def test_3d_bar_view_cubes(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        bar = win.view3d.nav_bar
        menu = bar.buttons["orientation"].menu().actions()
        assert [a.text() for a in menu if not a.isSeparator()][:7] == [
            "Isometric", "Front", "Back", "Left", "Right", "Top", "Bottom"]
        bar.actions["view_top"].trigger()
        assert win.view3d.pitch > 80
        bar.actions["view_front"].trigger()
        assert win.view3d.yaw == win.view3d.VIEWS["Front"][0]
    finally:
        win.close()


def test_the_3d_hand_slides_the_camera(app):
    from PyQt5.QtCore import QEvent, QPoint
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    view.set_mesh(_box(0, 0, 0, 10), "test")
    view.fit()
    bar = viewnav.attach_3d(view)
    bar.buttons["hand"].click()
    yaw, target = view.yaw, list(view.target)

    class _E:
        def __init__(self, kind, pos):
            self._k, self._p = kind, pos

        def type(self):
            return self._k

        def pos(self):
            return self._p

        def button(self):
            from PyQt5.QtCore import Qt
            return Qt.LeftButton
    hand = view.hand_pan
    hand.eventFilter(view, _E(QEvent.MouseButtonPress, QPoint(300, 200)))
    hand.eventFilter(view, _E(QEvent.MouseMove, QPoint(360, 200)))
    hand.eventFilter(view, _E(QEvent.MouseButtonRelease, QPoint(360, 200)))
    assert view.target != target and view.yaw == yaw


def test_the_3d_bar_shows_and_hides_the_lighting_panel(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    view.show()
    bar = viewnav.attach_3d(view)
    button = bar.actions["lighting"]
    assert button.isCheckable() and button.isChecked()
    assert view.lighting_bar.isVisible()
    button.trigger()                                # hide
    assert not view.lighting_bar.isVisible() and not view.lighting_wanted
    button.trigger()                                # back
    assert view.lighting_bar.isVisible()
    view.close()


def test_the_xyz_axes_can_be_hidden(app):
    """View ▸ 3D Axes (and the 3D bar's display menu) hides the red X,
    green Y and blue Z lines at the origin; the menu tick, the view and
    the MCP option stay in step."""
    from PyQt5.QtGui import QColor, QImage
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        view = win.view3d
        view.resize(400, 300)

        drawn = []
        real = view._draw_axes
        view._draw_axes = lambda *a: (drawn.append(1), real(*a))

        def red_pixels():
            drawn.clear()
            img = QImage(view.size(), QImage.Format_ARGB32)
            view.render(img)
            return len(drawn)

        view.set_axes(True)
        assert win._axes_act.isChecked()
        assert red_pixels() > 0
        win._axes_act.trigger()                 # the menu tick
        assert not view.axes
        assert red_pixels() == 0
        result = McpToolExecutor(win).execute("set_render_options",
                                              {"axes": True})
        assert result["axes"] is True and win._axes_act.isChecked()
    finally:
        win._dirty = False
        win.close()

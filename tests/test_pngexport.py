"""File ▸ Export PNG, and the standard still set it shares with the
Printables bundle.

The engine is disabled in the suite, so everything here goes through
the built-in renderer (View3D.snapshot) — including the Printables
fallback that used to publish the back of the model as its cover.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from khervecad import engine, pngexport, printables
from khervecad.mcp_schema import BY_NAME, DEFAULT_VIEWS, STILL_VIEWS
from khervecad.mcp_tools import McpToolExecutor
from khervecad.view3d import View3D

#: A grey block with a red plate on its FRONT (-Y) face and a blue one
#: on its BACK (+Y) face: the colour in a picture says which side the
#: camera saw.
TWO_FACED = """
color("lightgrey") cube([40, 30, 20], center=true);
color([1, 0, 0]) translate([-12, -17, -6]) cube([24, 2, 12]);
color([0, 0, 1]) translate([-12, 15, -6]) cube([24, 2, 12]);
"""


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad import scadparse
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(640, 480)
    root, _warnings = scadparse.parse_scad(TWO_FACED)
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    assert win.view3d.mesh
    return win


@pytest.fixture
def settings(tmp_path):
    """A private settings file, so the suite never touches the user's."""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)


def _count(image, hues):
    """Saturated, opaque pixels whose hue falls in one of *hues*."""
    found = 0
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            c = image.pixelColor(x, y)
            if c.alpha() < 128 or c.saturationF() < 0.5 \
                    or c.valueF() < 0.15:
                continue
            if any(lo <= c.hueF() <= hi for lo, hi in hues):
                found += 1
    return found


RED = ((0.0, 0.05), (0.95, 1.0))
BLUE = ((0.58, 0.72),)


def _eye(yaw, pitch):
    """Where View3D's camera sits, as a unit vector from the target."""
    y, p = math.radians(yaw), math.radians(pitch)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y),
            math.sin(p))


# ── the view set ──────────────────────────────────────────────────

def test_the_still_set_is_every_side_with_the_cover_first():
    names, unknown = pngexport.ordered_views(DEFAULT_VIEWS)
    assert unknown == []
    assert names[0] == "Isometric"
    assert set(names) == set(STILL_VIEWS) == {
        "Isometric", "Isometric back", "Front", "Back", "Left", "Right",
        "Top", "Bottom"}


def test_ordering_puts_the_cover_first_and_reports_unknowns():
    names, unknown = pngexport.ordered_views(
        ("Front", "Isometric", "Sideways", "Front"))
    assert names == ["Isometric", "Front"]
    assert unknown == ["Sideways"]


def test_both_renderers_share_one_camera_table():
    """OpenSCAD's rotation and the 3D view's preset of the same name
    must look from the same side — the mismatch that put the back of
    the model on the cover when OpenSCAD was missing."""
    for name in STILL_VIEWS:
        assert name in engine.CAMERA_ROTATIONS
    for name, (yaw, pitch) in View3D.VIEWS.items():
        y, p = engine.view_angles(engine.CAMERA_ROTATIONS[name])
        assert (y - yaw + 180.0) % 360.0 - 180.0 == pytest.approx(0.0), \
            name
        assert abs(p - pitch) <= 2.0, name


def test_the_cover_looks_at_the_front_right_corner():
    x, y, z = _eye(*pngexport.camera("Isometric"))
    assert y < 0 and x > 0 and z > 0         # front (-Y), right, above
    x, y, z = _eye(*pngexport.camera("Isometric back"))
    assert y > 0 and x < 0 and z > 0         # the opposite corner
    x, y, _z = _eye(*View3D.VIEWS["Isometric"])
    assert y < 0, "the 3D view's own Isometric preset shows the back"


def test_the_cover_picture_shows_the_front_not_the_back(window):
    cover = pngexport.render(window.view3d, 320, 240, "Isometric",
                             transparent=True)
    assert _count(cover, RED) > 50
    assert _count(cover, BLUE) == 0
    back = pngexport.render(window.view3d, 320, 240, "Isometric back",
                            transparent=True)
    assert _count(back, BLUE) > 50
    assert _count(back, RED) == 0


# ── File ▸ Export PNG ────────────────────────────────────────────────

def test_current_view_export_keeps_the_users_camera(window, tmp_path):
    view = window.view3d
    view.set_view("Right")
    before = view.camera_state()
    path = pngexport.export_current(view, tmp_path / "shot.png",
                                    (320, 200))
    image = QImage(str(path))
    assert (image.width(), image.height()) == (320, 200)
    assert view.camera_state() == before


def test_window_size_times_two_keeps_the_framing(window):
    view = window.view3d
    assert pngexport.resolve_size(view, "window2") == (
        view.width() * 2, view.height() * 2)
    assert pngexport.resolve_size(view, "3840x2160") == (3840, 2160)


def test_all_views_write_one_distinct_file_each(window, tmp_path):
    paths = pngexport.export_views(window.view3d, tmp_path / "views",
                                   "part", (160, 120))
    assert len(paths) == len(STILL_VIEWS)
    names = [p.name for p in paths]
    assert names[0] == "part-1-isometric.png"
    assert "part-2-isometric-back.png" in names
    assert "part-8-bottom.png" in names
    contents = {p.read_bytes() for p in paths}
    assert len(contents) == len(paths)       # every view is its own


def test_transparent_export_clears_the_background(window, tmp_path):
    opaque = pngexport.render(window.view3d, 200, 150, "Front")
    assert opaque.pixelColor(0, 0).alpha() == 255
    path = tmp_path / "clear.png"
    pngexport._save(pngexport.render(window.view3d, 200, 150, "Front",
                                     transparent=True), path)
    image = QImage(str(path))
    assert image.hasAlphaChannel()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(199, 149).alpha() == 0
    assert image.pixelColor(100, 75).alpha() == 255   # the model


def test_the_dialog_remembers_its_choices(window, settings, tmp_path):
    dialog = pngexport.PngExportDialog(window, settings=settings)
    dialog.all_radio.setChecked(True)
    dialog.size_combo.setCurrentIndex(
        dialog.size_combo.findData("1280x720"))
    dialog.transparent_box.setChecked(True)
    dialog.path_edit.setText(str(tmp_path / "out" / "views"))
    paths = dialog.export()
    assert [p.name for p in paths][0] == "model-1-isometric.png"
    assert len(paths) == len(STILL_VIEWS)
    first = QImage(str(paths[0]))
    assert (first.width(), first.height()) == (1280, 720)

    again = pngexport.PngExportDialog(window, settings=settings)
    assert again.is_all()
    assert again.size_combo.currentData() == "1280x720"
    assert again.transparent_box.isChecked()
    assert Path(again.path_edit.text()).parent == tmp_path / "out"


def test_the_dialog_writes_a_single_picture(window, settings, tmp_path):
    dialog = pngexport.PngExportDialog(window, settings=settings)
    dialog.current_radio.setChecked(True)
    dialog.size_combo.setCurrentIndex(
        dialog.size_combo.findData("window2"))
    dialog.path_edit.setText(str(tmp_path / "shot"))    # no suffix
    (path,) = dialog.export()
    assert path.name == "shot.png"
    image = QImage(str(path))
    assert (image.width(), image.height()) == pngexport.window_size_x2(
        window.view3d)


def test_the_file_menu_offers_it(window):
    file_menu = next(a.menu() for a in window.menuBar().actions()
                     if a.text() == "&File")
    action = next(a for a in file_menu.actions() if "PN&G" in a.text())
    assert action.shortcut().toString() == "Ctrl+Alt+E"


# ── the MCP tool ───────────────────────────────────────────────────

def test_export_document_writes_a_png(window, tmp_path):
    ex = McpToolExecutor(window)
    before = window.view3d.camera_state()
    result = ex.execute("export_document", {
        "path": str(tmp_path / "front.png"), "view": "Front",
        "width": 300, "height": 200, "transparent": True})
    assert "error" not in result, result.get("error")
    image = QImage(result["exported"])
    assert (image.width(), image.height()) == (300, 200)
    assert image.pixelColor(0, 0).alpha() == 0
    assert window.view3d.camera_state() == before


def test_export_document_all_views(window, tmp_path):
    result = McpToolExecutor(window).execute("export_document", {
        "path": str(tmp_path / "box.png"), "view": "all",
        "width": 120, "height": 90})
    assert "error" not in result, result.get("error")
    assert len(result["exported"]) == len(STILL_VIEWS)
    assert Path(result["exported"][0]).name == "box-1-isometric.png"


def test_export_document_rejects_a_bad_png_request(window, tmp_path):
    ex = McpToolExecutor(window)
    bad_view = ex.execute("export_document", {
        "path": str(tmp_path / "x.png"), "view": "Sideways"})
    assert "Sideways" in bad_view["error"]
    too_big = ex.execute("export_document", {
        "path": str(tmp_path / "x.png"), "width": 100000})
    assert "between" in too_big["error"]


def test_the_schema_offers_png():
    tool = BY_NAME["export_document"]
    assert ".png" in tool["description"]
    enum = tool["input_schema"]["properties"]["view"]["enum"]
    assert enum[0] == "current" and "all" in enum
    assert set(STILL_VIEWS) <= set(enum)


# ── Printables without OpenSCAD ─────────────────────────────────────

def test_printables_fallback_renders_every_view_cover_first(window,
                                                            tmp_path):
    before = window.view3d.camera_state()
    bundle = printables.build_bundle(
        window, tmp_path / "bundle", title="Box", formats=("scad",),
        image_size=(200, 150))
    names = [Path(p).name for p in bundle["images"]]
    assert len(names) == len(STILL_VIEWS)
    assert names[0] == "Box-1-isometric.png"
    assert "Box-2-isometric-back.png" in names
    assert window.view3d.camera_state() == before   # never moved
    assert any("built-in renderer" in w for w in bundle["warnings"])
    cover = QImage(bundle["images"][0])
    assert _count(cover, RED) > 20 and _count(cover, BLUE) == 0

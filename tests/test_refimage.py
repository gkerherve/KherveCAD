"""Tests for reference images: document storage, undo, the 2D and 3D
backdrops, and the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, mcp_bridge, refimage
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def red_png(app, tmp_path):
    from PyQt5.QtGui import QColor, QImage
    image = QImage(40, 20, QImage.Format_ARGB32)
    image.fill(QColor("#ff0000"))
    path = tmp_path / "ref.png"
    image.save(str(path))
    return str(path)


def _ref(path, **extra):
    ref = dict(path=path, plane="Top (XY)", x=-10.0, y=-5.0, width=20.0,
               height=10.0, offset=0.0, opacity=1.0, visible=True)
    ref.update(extra)
    return ref


def _red(colour) -> bool:
    return colour.red() > colour.green() + 60 and \
        colour.red() > colour.blue() + 60


def test_references_are_undoable(app, red_png):
    model = DocumentModel()
    model.add_reference_image(_ref(red_png))
    model._capture()
    assert len(model.reference_images) == 1
    model.undo_stack.undo()
    assert model.reference_images == []
    model.undo_stack.redo()
    assert model.reference_images[0]["path"] == red_png


def test_references_are_saved_and_loaded(app, red_png, tmp_path):
    model = DocumentModel()
    model.add_reference_image(_ref(red_png, plane="Front (XZ)",
                                   offset=40.0))
    path = tmp_path / "doc.kcad"
    document.save_kcad(model, str(path))
    fresh = DocumentModel()
    document.load_kcad(fresh, str(path))
    assert fresh.reference_images == model.reference_images


def test_corners_lie_on_the_chosen_plane(app):
    ref = dict(plane="Front (XZ)", x=1.0, y=2.0, width=10.0, height=4.0,
               offset=7.0)
    assert refimage.corners(ref) == [(1.0, 7.0, 2.0), (11.0, 7.0, 2.0),
                                     (11.0, 7.0, 6.0), (1.0, 7.0, 6.0)]
    side = refimage.corners(dict(plane="Side (YZ)", width=2.0,
                                 height=3.0))
    assert side[2] == (0.0, 2.0, 3.0)


def test_aspect_reads_the_picture(app, red_png):
    assert refimage.aspect(red_png) == pytest.approx(0.5)
    assert refimage.aspect("/no/such/image.png") is None


def test_the_3d_view_draws_the_picture_behind_the_model(app, red_png):
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(160, 160)
    view.set_reference_images([_ref(red_png, x=-50.0, y=-25.0,
                                    width=100.0, height=50.0)])
    view.yaw, view.pitch = view.VIEWS["Top"]
    view.target, view.distance = [0.0, 0.0, 0.0], 150.0
    img = QImage(QSize(160, 160), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    # on the picture, clear of the axis gizmo drawn at the origin
    assert _red(img.pixelColor(60, 95))
    assert not _red(img.pixelColor(80, 8))        # above the picture


def test_the_2d_view_draws_the_picture_on_its_plane(app, red_png):
    from khervecad.view2d import SketchScene, SketchView
    model = DocumentModel()
    model.add_reference_image(_ref(red_png))
    scene = SketchScene(model)
    scene.show_grid = False              # grid and axis lines drawn on top
    view = SketchView(scene)
    view.resize(200, 200)
    # a view never shown keeps a stale viewport size, and centres (and
    # maps) against it: show it so the geometry settles, then aim
    # through the view's own mapping at a point on the picture
    # (-10..10 x -5..5 mm), clear of the origin gizmo
    from PyQt5.QtCore import QPointF
    view.show()
    QApplication.processEvents()
    view.centerOn(0, 0)
    QApplication.processEvents()
    at = view.mapFromScene(QPointF(-6.0, 3.0))
    probe = (at.x(), at.y())
    try:
        shot = view.viewport().grab().toImage()
        assert _red(shot.pixelColor(*probe))
        scene.set_plane("Front (XZ)")           # not on this plane
        shot = view.viewport().grab().toImage()
        assert not _red(shot.pixelColor(*probe))
    finally:
        view.hide()


def test_the_mcp_tool_places_removes_and_clears(app, red_png):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(MainWindow())
    out = ex.execute("set_reference_image", {"path": red_png,
                                             "plane": "Front",
                                             "width": 80})
    refs = out["reference_images"]
    assert refs[0]["plane"] == "Front (XZ)"
    assert refs[0]["size"] == [80.0, 40.0]
    assert refs[0]["at"] == [-40.0, -20.0]          # centred by default
    info = ex.execute("get_document_info", {})
    assert info["reference_images"][0]["path"] == red_png
    ex.execute("set_reference_image", {"path": red_png})
    left = ex.execute("set_reference_image", {"remove": 0})
    assert len(left["reference_images"]) == 1
    assert ex.execute("set_reference_image",
                      {"clear": True})["reference_images"] == []
    missing = ex.execute("set_reference_image", {"path": "/no/such.png"})
    assert "Could not read" in missing["error"]


def test_naming_a_file_needs_full_access():
    assert mcp_bridge._names_a_path("set_reference_image", {"path": "a"})
    assert not mcp_bridge._names_a_path("set_reference_image",
                                        {"clear": True})

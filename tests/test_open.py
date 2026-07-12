"""Tests for unified open / import (by extension) and file drag-drop.

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
from PyQt5.QtCore import QMimeData, QPoint, Qt, QUrl
from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import QApplication

from khervecad import document


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w._confirm_discard = lambda: True          # never prompt in tests
    return w


def test_open_any_opens_kcad(window, tmp_path):
    window.model.add_node("sphere")
    p = tmp_path / "Doc.kcad"
    document.save_kcad(window.model, str(p))
    window.model.clear()
    window.open_any(str(p))
    assert window._path == str(p)
    assert any(n.type == "sphere" for n in window.model.root.walk())


def test_open_any_imports_scad_as_objects(window, tmp_path):
    p = tmp_path / "plate.scad"
    p.write_text("plate = [100, 50, 5];\ncube(plate);\n", encoding="utf-8")
    window.open_any(str(p))
    assert any(n.type == "cube" for n in window.model.root.walk())
    assert str(p) in window._recent_files()    # re-openable from Recent


def test_open_any_imports_stl_as_node(window, tmp_path):
    # a tiny valid ASCII STL
    p = tmp_path / "m.stl"
    p.write_text(
        "solid s\nfacet normal 0 0 1\nouter loop\n"
        "vertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\n"
        "endloop\nendfacet\nendsolid s\n", encoding="utf-8")
    window.open_any(str(p))
    stl = [n for n in window.model.root.walk() if n.type == "stl_import"]
    assert len(stl) == 1
    assert stl[0].params["path"] == str(p)


_OBJ = "v 0 0 0\nv 10 0 0\nv 0 20 0\nf 1 2 3\n"
_OFF = "OFF\n3 1 0\n0 0 0\n10 0 0\n0 20 0\n3 0 1 2\n"


def _write_3mf(path):
    import zipfile
    model = (
        '<?xml version="1.0"?>'
        '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/'
        'core/2015/02"><resources><object id="1" type="model"><mesh>'
        '<vertices><vertex x="0" y="0" z="0"/><vertex x="10" y="0" z="0"/>'
        '<vertex x="0" y="20" z="0"/></vertices>'
        '<triangles><triangle v1="0" v2="1" v3="2"/></triangles>'
        '</mesh></object></resources><build><item objectid="1"/></build>'
        '</model>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("3D/3dmodel.model", model)


def test_parse_mesh_reads_obj_off_3mf(tmp_path):
    from khervecad import engine
    (tmp_path / "t.obj").write_text(_OBJ, encoding="utf-8")
    (tmp_path / "t.off").write_text(_OFF, encoding="utf-8")
    _write_3mf(tmp_path / "t.3mf")
    for name in ("t.obj", "t.off", "t.3mf"):
        tris = engine.parse_mesh(str(tmp_path / name))
        assert len(tris) == 1, name
        assert set(tris[0]) == {(0, 0, 0), (10, 0, 0), (0, 20, 0)}, name


def test_open_any_imports_off_and_3mf(window, tmp_path):
    (tmp_path / "m.off").write_text(_OFF, encoding="utf-8")
    _write_3mf(tmp_path / "m.3mf")
    for name in ("m.off", "m.3mf"):
        window.model.clear()
        window.open_any(str(tmp_path / name))
        nodes = [n for n in window.model.root.walk()
                 if n.type == "stl_import"]
        assert len(nodes) == 1, name
        assert nodes[0].params["path"] == str(tmp_path / name)


def test_obj_import_converts_to_sibling_stl(window, tmp_path):
    """OBJ isn't renderable by OpenSCAD, so it is converted to an STL the
    engine can render, and the node points at that STL."""
    (tmp_path / "part.obj").write_text(_OBJ, encoding="utf-8")
    window.open_any(str(tmp_path / "part.obj"))
    node = next(n for n in window.model.root.walk()
                if n.type == "stl_import")
    assert node.params["path"].endswith("part_from_obj.stl")
    assert (tmp_path / "part_from_obj.stl").exists()


def test_dropping_a_file_opens_it(window, tmp_path):
    p = tmp_path / "plate.scad"
    p.write_text("cube([10, 10, 10]);\n", encoding="utf-8")
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(p))])
    event = QDropEvent(QPoint(5, 5), Qt.CopyAction, md,
                       Qt.LeftButton, Qt.NoModifier)
    window.dropEvent(event)
    assert event.isAccepted()
    assert any(n.type == "cube" for n in window.model.root.walk())


def test_dropped_file_filters_unsupported(window, tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello", encoding="utf-8")
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(p))])
    event = QDropEvent(QPoint(5, 5), Qt.CopyAction, md,
                       Qt.LeftButton, Qt.NoModifier)
    assert window._dropped_file(event) is None

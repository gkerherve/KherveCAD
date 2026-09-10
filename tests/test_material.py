"""Tests for colour materials: the color node's `material`, how the 3D
view shades it, and how it survives export and import.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, mcp_schema, mesh, scadparse, view3d
from khervecad.model import MATERIALS, DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _metal_cube(doc, material="Metal", color="#b0b0b0"):
    cube = doc.add_node("cube")
    doc.set_color([cube], color, 1.0, material)
    return next(n for n in doc.root.walk() if n.type == "color")


def test_every_material_has_a_shading_and_one_name_list(app):
    assert set(MATERIALS) - {"Default"} == set(view3d.MATERIAL_STYLES)
    assert mcp_schema.MATERIALS == MATERIALS


def test_the_preview_carries_the_material_per_face(app):
    doc = DocumentModel()
    _metal_cube(doc)
    colours = {c for _t, c in mesh.tessellate_colored(doc.root)}
    assert colours == {("#b0b0b0", 1.0, "Metal")}
    plain = DocumentModel()
    _metal_cube(plain, material="Default")
    assert {c for _t, c in mesh.tessellate_colored(plain.root)} \
        == {("#b0b0b0", 1.0)}


def test_codegen_records_the_material_as_a_harmless_prefix(app):
    doc = DocumentModel()
    _metal_cube(doc)
    code = doc.to_scad()
    assert 'kcad_material("Metal") color("#b0b0b0") {' in code
    assert code.count("module kcad_material(") == 1
    plain = DocumentModel()
    _metal_cube(plain, material="Default")
    assert "kcad_material" not in plain.to_scad()


def test_the_material_round_trips_and_nested_colours_stay_apart(
        app, tmp_path):
    doc = DocumentModel()
    glass = _metal_cube(doc, material="Glass", color="#88ccff")
    inner = doc.add_node("sphere", parent=glass)
    doc.wrap_nodes([inner], "color").params.update(color="#ff0000")
    code1 = doc.to_scad()
    path = tmp_path / "material.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    colours = [n for n in other.root.walk() if n.type == "color"]
    assert [c.params.get("material") for c in colours] \
        == ["Glass", "Default"]


def test_an_old_file_without_materials_still_loads(app, tmp_path):
    doc = DocumentModel()
    _metal_cube(doc, material="Default")
    path = tmp_path / "old.kcad"
    document.save_kcad(doc, str(path))
    data = json.loads(path.read_text())
    colour = data["tree"]["children"][0]
    del colour["params"]["material"]           # as version 5 wrote it
    path.write_text(json.dumps(data))
    fresh = DocumentModel()
    document.load_kcad(fresh, str(path))
    node = next(n for n in fresh.root.walk() if n.type == "color")
    assert node.params["material"] == "Default"


def _face_pixel(app, material):
    """Render one flat face of a given material; return the centre."""
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    quad = [((-50, -50, 0), (50, -50, 0), (50, 50, 0)),
            ((-50, -50, 0), (50, 50, 0), (-50, 50, 0))]
    view = view3d.View3D()
    view.resize(120, 120)
    view.style = "Shaded"
    colour = ("#b04040", 1.0) + ((material,) if material else ())
    view.set_mesh(quad, "test", [colour, colour])
    view.yaw, view.pitch = 0.0, 89.0
    view.target, view.distance = [0.0, 0.0, 0.0], 60.0
    img = QImage(QSize(120, 120), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    return img.pixelColor(60, 60)


def test_materials_shade_the_same_colour_differently(app):
    plastic = _face_pixel(app, None)
    rubber = _face_pixel(app, "Rubber")
    emissive = _face_pixel(app, "Emissive")
    assert rubber.valueF() < plastic.valueF() - 0.1        # dull, dark
    assert emissive.valueF() >= plastic.valueF()           # self-lit
    assert rubber.name() != plastic.name() != emissive.name()


def test_set_color_takes_a_material(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(MainWindow())
    cube = ex.execute("add_node", {"type": "cube"})["created"]
    out = ex.execute("set_color", {"ids": [cube], "color": "#ffd700",
                                   "material": "Gold"})
    assert out["material"] == "Gold"
    node = ex._model.find(out["colored"][0])
    assert node.params["material"] == "Gold"
    bad = ex.execute("set_color", {"ids": [cube], "color": "#fff",
                                   "material": "Velvet"})
    assert "Velvet" in bad["error"]

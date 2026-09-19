"""Wireframe (wireframe.py): real edges only, one closed lattice.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import analysis, csg, document, mesh, scadparse, wireframe
from khervecad.model import DocumentModel, validate

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="manifold3d not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tris(code, fn=16):
    root, _w = scadparse.parse_scad(code)
    return mesh.tessellate(root, fn=fn)


def test_a_cube_has_twelve_struts_not_its_diagonals():
    cube = _tris("cube(20);")
    assert len(wireframe.edges(cube)) == 12
    assert len(wireframe.edges(cube, 0)) == 18


@pytest.mark.parametrize("code, angle", [("cube(20);", 1),
                                         ("sphere(30);", 0),
                                         ("sphere(30);", 1)])
def test_the_lattice_is_one_closed_solid(code, angle):
    out = wireframe.wireframe(_tris(code), 1.5, 6, angle)
    assert analysis.watertight(out)["ok"]


def test_a_cube_frame_weighs_twelve_bars_plus_corners():
    out = wireframe.wireframe(_tris("cube(20);"), 2, 24)
    vol = analysis.mass_properties(out)["volume"]
    bars = 12 * math.pi * 20
    assert bars * 0.85 < vol < bars * 1.15


def test_the_node_bakes_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    cube = doc.add_node("cube", dict(width=20.0, depth=20.0, height=20.0))
    node = doc.wrap_nodes([cube], "wireframe")
    node.params["thickness"] = 2.0
    assert validate(doc.root) == {}
    assert analysis.watertight(mesh.tessellate(doc.root))["ok"]
    code = doc.to_scad()
    assert "kcad_wireframe(thickness = 2, sides = 6, angle = 1, " \
        "joints = true," in code
    path = tmp_path / "w.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]

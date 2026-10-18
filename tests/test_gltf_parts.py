"""Named, coloured parts: OBJ / GLB in, GLB out (gltf_parts.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx, cadexchange_ui, gltf_parts, scadparse
from khervecad.model import DocumentModel

PLATE = """
color("red") cube([40, 30, 10]);   // Plate
color("#0000ff", 0.5) translate([60, 0, 0]) cube([10, 10, 10]);   // Glass
"""

OBJ = """mtllib car.mtl
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
o body
usemtl paint
f 1 2 3 4
o wheel_fl
usemtl tyre
f 1/1/1 2/2/2 5/5/5
"""

MTL = """newmtl paint
Kd 1 0 0
newmtl tyre
Kd 0.1 0.1 0.1
"""


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _gltf(path):
    data = Path(path).read_bytes()
    assert struct.unpack_from("<I", data, 0)[0] == 0x46546C67
    length = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + length])


def test_obj_groups_and_mtl_colours_become_parts(tmp_path):
    (tmp_path / "car.obj").write_text(OBJ)
    (tmp_path / "car.mtl").write_text(MTL)
    parts = gltf_parts.read_parts(tmp_path / "car.obj")
    assert [p.name for p in parts] == ["body", "wheel_fl"]
    assert parts[0].color == "#ff0000" and parts[1].color == "#1a1a1a"
    assert len(parts[0].tris) == 2          # the quad, fanned


def test_glb_out_and_back_in_keeps_names_colours_and_millimetres(tmp_path):
    root, _w = scadparse.parse_scad(PLATE)
    out = tmp_path / "m.glb"
    report = cx.export_model(root, out)
    assert report.parts == 2
    g = _gltf(out)
    assert [n["name"] for n in g["nodes"]] == ["Plate", "Glass"]
    glass = g["materials"][g["meshes"][1]["primitives"][0]["material"]]
    assert glass["alphaMode"] == "BLEND"
    # metres, Y up: the 40 mm plate is 0.04 m along x
    pos = g["accessors"][g["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    assert abs(pos["max"][0] - pos["min"][0] - 0.04) < 1e-6
    assert abs(pos["max"][1] - pos["min"][1] - 0.01) < 1e-6   # height (z) is glTF y
    parts = gltf_parts.read_parts(out)
    assert [p.name for p in parts] == ["Plate", "Glass"]
    assert parts[0].color == "#ff0000"
    zs = [v[2] for t in parts[0].tris for v in t]
    assert abs(max(zs) - min(zs) - 10) < 1e-6             # back in mm, z up


def test_an_object_at_the_origin_exports_as_its_parts(tmp_path, app):
    (tmp_path / "car.obj").write_text(OBJ)
    (tmp_path / "car.mtl").write_text(MTL)
    model = DocumentModel()
    parts = gltf_parts.read_parts(tmp_path / "car.obj")
    cadexchange_ui.place_parts(model, str(tmp_path / "car.obj"), parts)
    out = tmp_path / "car.glb"
    cx.export_model(model.root, out)
    assert [n["name"] for n in _gltf(out)["nodes"]] == ["body", "wheel_fl"]

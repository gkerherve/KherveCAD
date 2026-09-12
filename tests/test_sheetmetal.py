"""Sheet metal: the node, its preview and OpenSCAD, the flat pattern.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse, sheetmetal
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _bounds(tris):
    pts = [v for t in tris for v in t]
    return [(round(min(p[i] for p in pts), 3),
             round(max(p[i] for p in pts), 3)) for i in range(3)]


def test_a_channel_previews_with_both_flanges_up(model):
    node = model.add_node("sheet_metal", dict(
        width=80.0, depth=60.0, thickness=1.5, radius=1.5,
        n_length=20.0, s_length=20.0, e_length=0.0, w_length=0.0))
    assert validate(model.root) == {}
    tris = mesh.tessellate(model.root)
    lo_hi = _bounds(tris)
    assert lo_hi[0] == (0.0, 80.0)
    # each 90° flange reaches r + t out from its edge and 20 mm up from
    # the bend's centre line (t + r), so about 23 high
    assert lo_hi[1][0] == pytest.approx(-3.0, abs=0.05)
    assert lo_hi[1][1] == pytest.approx(63.0, abs=0.05)
    assert lo_hi[2][1] == pytest.approx(1.5 + 1.5 + 20.0, abs=0.05)


def test_a_flange_bent_down_goes_below_the_plate(model):
    node = model.add_node("sheet_metal", dict(
        n_length=0.0, s_length=0.0, e_length=15.0, e_angle=-90.0))
    tris = mesh.tessellate(model.root)
    z = _bounds(tris)[2]
    assert z[0] == pytest.approx(-(1.5 + 15.0), abs=0.05)
    assert z[1] == pytest.approx(1.5)


def test_codegen_and_import_round_trip(model):
    model.add_node("sheet_metal", dict(width=50.0, depth=40.0,
                                       e_length=10.0, e_angle=45.0))
    code = model.to_scad()
    assert "module kcad_sheet" in code
    assert ("kcad_sheet(size = [50, 40], t = 1.5, r = 1.5, k = 0.44, "
            "flanges = [[20, 90], [10, 45], [20, 90], [0, 90]])") in code
    root, warnings = scadparse.parse_scad(code)
    [node] = [n for n in root.walk() if n.type == "sheet_metal"]
    assert node.params["e_angle"] == 45.0 and node.params["width"] == 50.0
    again = DocumentModel()
    again.root = root
    assert again.to_scad() == code


def test_flat_pattern_uses_the_bend_allowance():
    p = dict(sheetmetal.NODE_TYPES["sheet_metal"]["params"])
    p.update(width=80.0, depth=60.0, thickness=2.0, radius=2.0, kfactor=0.5,
             n_length=20.0, n_angle=90.0, s_length=0.0, e_length=0.0,
             w_length=0.0)
    pat = sheetmetal.flat_pattern(p)
    ba = (2.0 + 0.5 * 2.0) * math.pi / 2          # 4.712
    setback = (2.0 + 2.0) * math.tan(math.pi / 4)  # 4
    [fl] = pat["flanges"]
    assert fl["allowance"] == pytest.approx(ba)
    assert fl["leg"] == pytest.approx(20.0 - setback)
    assert pat["width"] == pytest.approx(80.0)
    assert pat["height"] == pytest.approx(60.0 + ba + 16.0)
    # two bend lines across the north edge, BA apart
    ys = sorted(a[1] for a, _b in pat["bend_lines"])
    assert ys == pytest.approx([60.0, 60.0 + ba])
    # the outline is one closed polygon with the flange's tab on it
    assert (80.0, 60.0 + ba + 16.0) in [tuple(q) for q in pat["outline"]]


def test_flat_dxf_and_unfold(model, tmp_path):
    node = model.add_node("sheet_metal", dict(n_length=10.0, s_length=0.0))
    pat = sheetmetal.flat_pattern(node.params)
    path = sheetmetal.flat_dxf(pat, str(tmp_path / "flat.dxf"))
    text = Path(path).read_text()
    assert text.count("CUT") == len(pat["outline"])
    assert text.count("BEND") == 2
    poly, _p = sheetmetal.unfold_node(node)
    assert poly.type == "polygon" and len(poly.params["points"]) >= 6


def test_validation_catches_bad_values(model):
    node = model.add_node("sheet_metal", dict(thickness=0.0))
    assert "thickness" in validate(model.root)[node.id]
    node.params["thickness"] = 1.0
    node.params["n_angle"] = 200.0
    assert "n_angle" in validate(model.root)[node.id]


@pytest.mark.skipif(not os.path.exists("/opt/homebrew/bin/openscad"),
                    reason="needs the OpenSCAD binary")
def test_helper_matches_the_preview(model, tmp_path):
    """The OpenSCAD helper and the Python preview agree on the extent
    of a two-flange channel."""
    from khervecad import engine
    model.add_node("sheet_metal", dict(n_length=20.0, s_length=20.0,
                                       e_length=12.0, e_angle=-60.0))
    scad = tmp_path / "s.scad"
    scad.write_text(model.to_scad(), encoding="utf-8")
    stl = tmp_path / "s.stl"
    subprocess.run(["/opt/homebrew/bin/openscad", "-o", str(stl),
                    str(scad)], check=True, capture_output=True)
    exact = _bounds(engine.parse_mesh(str(stl)))
    preview = _bounds(mesh.tessellate(model.root))
    for a, b in zip(exact, preview):
        assert a[0] == pytest.approx(b[0], abs=0.2)
        assert a[1] == pytest.approx(b[1], abs=0.2)

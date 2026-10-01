"""Surface age: the numpy blend, the crease / ridge brushes and skin
noise of the sculpt, and the weathering node that colours by shape.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import bake, mesh, scadparse, sculpt, sdf, weathering
from khervecad.model import CadNode, DocumentModel, validate


def _volume(tris):
    return sum(a[0] * (b[1] * c[2] - b[2] * c[1])
               - a[1] * (b[0] * c[2] - b[2] * c[0])
               + a[2] * (b[0] * c[1] - b[1] * c[0]) for a, b, c in tris) / 6


def _closed(tris):
    points, faces = bake.to_polyhedron(tris)
    return bake._check_polyhedron(dict(points=points, faces=faces)) is None


def _ball(detail=60):
    b = CadNode("blend", "b", dict(radius=1.0, detail=detail))
    b.add(CadNode("sphere", "s", dict(x=0, y=0, z=0, radius=20)))
    return sdf.blend(b, {}, 1.0, detail)


# --------------------------------------------------------------- blend

def test_the_numpy_blend_matches_the_python_one():
    b = CadNode("blend", "b", dict(radius=4.0, detail=30))
    b.add(CadNode("sphere", "s", dict(x=0, y=0, z=0, radius=10)))
    b.add(CadNode("capsule", "c", dict(x1=0, y1=0, z1=0, x2=0, y2=0, z2=30,
                                       radius=4)))
    b.add(CadNode("ellipsoid", "e", dict(x=12, y=0, z=20, rx=6, ry=4,
                                         rz=3)))
    b.add(CadNode("cube", "k", dict(x=-5, y=-5, z=25, width=10, depth=8,
                                    height=6, center=False)))
    b.add(CadNode("cylinder", "y", dict(x=-10, y=0, z=0, height=20,
                                        radius_bottom=3, radius_top=1,
                                        center=False)))
    parts = sdf.leaves(b, {})
    lo = [min(p.lo[i] for p in parts) - 7 for i in range(3)]
    hi = [max(p.hi[i] for p in parts) + 7 for i in range(3)]
    slow = sdf.polygonize(sdf.field(parts, 4.0), lo, hi, 1.5)
    fast = sdf.polygonize_np(parts, 4.0, lo, hi, 1.5)
    assert len(fast) == len(slow)
    assert _volume(fast) == pytest.approx(_volume(slow), rel=1e-6)
    assert _closed(fast)


def test_a_fine_blend_is_allowed_and_closed():
    tris = _ball(130)
    assert len(tris) > 100000          # past the old pure-Python grid cap
    assert _volume(tris) == pytest.approx(4 / 3 * 3.14159265 * 20 ** 3,
                                          rel=0.01)
    assert _closed(tris)


# -------------------------------------------------------------- sculpt

def test_crease_cuts_a_groove_and_ridge_raises_one():
    tris = _ball(80)
    base = _volume(tris)
    row = [-6.0, -19.0, 0.0, 2.0, 0.8, 12.0, 0.0, 0.0]
    creased = sculpt.sculpt(tris, [[5] + row])
    ridged = sculpt.sculpt(tris, [[6] + row])
    assert _volume(creased) < base - 3 and _closed(creased)
    assert _volume(ridged) > base + 3 and _closed(ridged)
    # the groove is ON the line, not elsewhere
    deepest = min(creased, key=lambda t: sum(v[0] ** 2 + v[1] ** 2
                                             + v[2] ** 2 for v in t))
    assert abs(sum(v[2] for v in deepest) / 3) < 2.5


def test_a_line_tapers_at_its_ends():
    mid = sculpt.line_weight(0.0, 6.0, 12.0, 2.0)
    end = sculpt.line_weight(0.0, 0.0, 12.0, 2.0)
    edge = sculpt.line_weight(1.0, 6.0, 12.0, 2.0)
    assert mid == pytest.approx(1.0) and 0.0 < end < mid and edge == 0.0


def test_noise_roughens_the_whole_surface_repeatably():
    tris = _ball(60)
    a = sculpt.sculpt(tris, [], noise=0.4, noise_scale=3.0, seed=4)
    b = sculpt.sculpt(tris, [], noise=0.4, noise_scale=3.0, seed=4)
    c = sculpt.sculpt(tris, [], noise=0.4, noise_scale=3.0, seed=5)
    assert a == b and a != c and _closed(a)
    radii = [sum(v[k] ** 2 for k in range(3)) ** 0.5 for t in a for v in t]
    assert max(radii) - min(radii) > 0.3


def test_numpy_and_python_sculpts_agree():
    tris = _ball(30)
    rows = [[1, 0, -20, 0, 6, 1.5, 0, 0, 0],
            [5, -10, -18, 0, 2.5, 0.8, 20, 0, 0],
            [2, 0, -20, 0, 8, 1, 0, 0, 0],
            [3, 0, 20, 0, 6, 0.5, 0, 0, 0],
            [4, 20, 0, 0, 5, 0.3, 0, 0, 0],
            [0, 0, 0, 20, 5, 2, 0, 0, 1]]
    fast = sculpt.sculpt(tris, rows)
    saved, sculpt._np = sculpt._np, None
    try:
        slow = sculpt.sculpt(tris, rows)
    finally:
        sculpt._np = saved
    # consecutive lines may share normals in the fast path (a hair)
    assert _volume(fast) == pytest.approx(_volume(slow), rel=1e-6)


def test_new_sculpt_params_round_trip_as_code():
    code = ('color("#6f8545") kcad_sculpt(strokes = [[5, 0, -20, 0, 2, '
            '0.5, 8, 0, 0]], noise = 0.1, noise_scale = 1.5, seed = 3) '
            'kcad_blend(radius = 1, detail = 24) sphere(r = 20);')
    root, warnings = scadparse.parse_scad(code)
    node = next(n for n in root.walk() if n.type == "sculpt")
    assert node.params["noise"] == pytest.approx(0.1)
    assert node.params["noise_scale"] == pytest.approx(1.5)
    assert node.params["seed"] == 3
    model = DocumentModel()
    model.root = root
    again, _w = scadparse.parse_scad(model.to_scad())
    back = next(n for n in again.walk() if n.type == "sculpt")
    assert back.params["strokes"] == node.params["strokes"]
    assert back.params["noise"] == pytest.approx(0.1)
    assert not validate(root)


# ---------------------------------------------------------- weathering

_AGED = '''
kcad_weathering(cavity_color = "#202810", cavity = 0.9,
                edge_color = "#e0dca8", edge = 0.4, depth = 0.4, reach = 3,
                mottle = 0, spots = 0,
                tints = [[0, 20, 0, 6, 200, 40, 40, 1]])
  color("#6f8545") kcad_sculpt(strokes = [
        [5, -6, -19, 0, 2, 0.8, 12, 0, 0], [6, -6, -19, 6, 1.5, 0.6, 12, 0, 0]])
    kcad_blend(radius = 1, detail = 100) sphere(r = 20);
'''


def _faces_near(out, x, y, z, r=2.0):
    return Counter(c[0] for t, c in out
                   if sum((sum(v[k] for v in t) / 3 - p) ** 2
                          for k, p in enumerate((x, y, z))) < r * r)


def test_weathering_darkens_creases_lightens_crests_keeps_the_rest():
    root, _w = scadparse.parse_scad(_AGED)
    out = mesh.tessellate_colored(root)
    base = weathering._rgb("#6f8545")

    def lum(hexcol):
        r, g, b = weathering._rgb(hexcol)
        return r + g + b
    crease = _faces_near(out, 0, -19.6, 0, 1.0).most_common(1)[0][0]
    ridge = _faces_near(out, 0, -19.9, 6, 1.0).most_common(1)[0][0]
    plain = _faces_near(out, 0, 0, -20, 3.0).most_common(1)[0][0]
    tinted = _faces_near(out, 0, 20, 0, 1.5).most_common(1)[0][0]
    assert lum(crease) < sum(base) - 20
    assert lum(ridge) > sum(base) + 20
    assert plain == "#6f8545"
    assert weathering._rgb(tinted)[0] > 150         # the red tint
    assert all(c[2] for _t, c in out)                # a material rides on


def test_weathering_round_trips_and_validates():
    # coarse: the program writes every baked point out
    root, warnings = scadparse.parse_scad(
        _AGED.replace("detail = 80", "detail = 24"))
    node = next(n for n in root.walk() if n.type == "weathering")
    assert node.params["cavity_color"] == "#202810"
    assert node.params["tints"] == [[0, 20, 0, 6, 200, 40, 40, 1]]
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert "module kcad_weathering" in code
    again, _w = scadparse.parse_scad(code)
    back = next(n for n in again.walk() if n.type == "weathering")
    assert back.params == node.params
    assert not validate(root)
    node.params["edge_color"] = "green-ish"
    assert "edge_color" in validate(root)[node.id]


def test_weathering_is_an_operation_with_a_tip():
    from khervecad import toolbars, tooltips
    assert "weathering" in dict(toolbars.OPERATION_GROUPS)["character"]
    assert "weathering" in tooltips.TIPS
    from khervecad import mcp_schema
    assert "weathering" in mcp_schema.WRAP_TYPES


# ----------------------------------------------------------------- MCP

@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_mcp_sculpt_stroke_draws_a_crease_from_at_to_to(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        r = ex.execute("apply_code", {"code": "kcad_blend(radius = 1, "
                                      "detail = 60) sphere(r = 20);"})
        assert "error" not in r, r
        blend = next(n for n in win.model.root.walk() if n.type == "blend")
        out = ex.execute("sculpt_stroke", {
            "node_id": blend.id, "kind": "crease", "at": [-6, -19.5, 0],
            "to": [6, -19.5, 0], "radius": 2, "strength": 0.6,
            "noise": 0.05, "noise_scale": 1.5})
        assert "error" not in out, out
        node = win.model.find(out["sculpt"])
        row = node.params["strokes"][0]
        assert row[0] == sculpt.KINDS.index("crease")
        assert row[6] == pytest.approx(12.0, abs=0.01)   # the line's run
        assert node.params["noise"] == pytest.approx(0.05)
        bad = ex.execute("sculpt_stroke", {"node_id": node.id,
                                           "kind": "ridge", "at": [0, 0, 20],
                                           "radius": 2, "strength": 1})
        assert "error" in bad and "to" in bad["error"]
    finally:
        win._dirty = False
        win.close()

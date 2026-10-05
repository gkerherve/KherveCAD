"""Surfaces from curves (curve_surface.py): loft, sweep, two-rail sweep,
patch, revolve and extrude — exact, closed and thickened.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cadexchange as cx, curve_surface as cs, \
    mesh, scadparse
from khervecad.model import DocumentModel, validate

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def ring(r, z, n=8):
    return [[r * math.cos(2 * math.pi * i / n),
             r * math.sin(2 * math.pi * i / n), z] for i in range(n)]


def open_edges(tris):
    c = Counter()

    def k(v):
        return (round(v[0], 4), round(v[1], 4), round(v[2], 4))
    for t in tris:
        for i in range(3):
            c[(k(t[i]), k(t[(i + 1) % 3]))] += 1
    return sum(1 for (a, b), n in c.items() if c.get((b, a), 0) != n)


def _vase(model, capped=True, thickness=1.0):
    curves = [model.add_node("curve", dict(points=ring(r, z), closed=True))
              for r, z in ((20, 0), (30, 40), (15, 80))]
    surf = cs.make_surface(model, curves, "loft")
    surf.params.update(capped=capped, thickness=thickness)
    return surf


def _build(app, kind):
    model = DocumentModel()
    if kind in ("sweep", "sweep2"):
        rail = model.add_node("curve", dict(points=[[0, 0, 0], [0, 40, 10],
                                                    [0, 80, 0]]))
        nodes = [rail]
        if kind == "sweep2":
            nodes.append(model.add_node("curve", dict(
                points=[[20, 0, 0], [25, 40, 10], [20, 80, 0]])))
        nodes.append(model.add_node("curve", dict(
            points=[[-10, 0, 0], [0, 0, 5], [10, 0, 0]] if kind == "sweep"
            else [[0, 0, 0], [10, 0, 6], [20, 0, 0]])))
    elif kind == "patch":
        nodes = [model.add_node("curve", dict(points=[[0, 0, 0], [40, 0, 0],
                                                      [40, 40, 0],
                                                      [0, 40, 0]],
                                              closed=True)),
                 model.add_node("curve", dict(points=[[10, 20, 0],
                                                      [20, 20, 12],
                                                      [30, 20, 0]]))]
    elif kind == "revolve":
        nodes = [model.add_node("curve", dict(
            points=[[10, 0, 0], [20, 0, 10], [12, 0, 30], [15, 0, 40]]))]
    else:
        nodes = [model.add_node("curve", dict(points=ring(10, 0),
                                              closed=True))]
    surf = cs.make_surface(model, nodes, kind)
    return model, surf


@pytest.mark.parametrize("kind", cs.KINDS)
def test_every_kind_is_one_closed_solid(app, kind):
    if kind == "loft":
        model = DocumentModel()
        surf = _vase(model)
    else:
        model, surf = _build(app, kind)
    assert validate(model.root) == {}
    tris = mesh.tessellate(model.root)
    assert tris and open_edges(tris) == 0
    assert analysis.mass_properties(tris)["volume"] > 0


def test_extrude_of_a_closed_curve_is_a_prism(app):
    model, surf = _build(app, "extrude")
    vol = analysis.mass_properties(mesh.tessellate(model.root))["volume"]
    # an 8-point smooth ring of radius 10 is close to a circle
    assert vol == pytest.approx(math.pi * 100 * 20, rel=0.02)


def test_an_open_loft_is_a_wall_of_the_thickness(app):
    closed = DocumentModel()
    _vase(closed)
    shell = DocumentModel()
    _vase(shell, capped=False, thickness=2.0)
    v_closed = analysis.mass_properties(mesh.tessellate(closed.root))[
        "volume"]
    v_shell = analysis.mass_properties(mesh.tessellate(shell.root))["volume"]
    assert 0 < v_shell < v_closed * 0.4


def test_open_surface_with_no_thickness_says_so(app):
    model, surf = _build(app, "patch")
    surf.params["thickness"] = 0.0
    assert "needs a thickness" in validate(model.root)[surf.id]


def test_too_few_curves_says_what_it_needs(app):
    model = DocumentModel()
    c = model.add_node("curve")
    surf = cs.make_surface(model, [c], "sweep")
    assert "rail" in validate(model.root)[surf.id]


def test_round_trips_through_openscad_code(app):
    model = DocumentModel()
    surf = _vase(model, capped=False, thickness=2.0)
    code = model.to_scad()
    assert "kcad_curve_surface(" in code
    root, warnings = scadparse.parse_scad(code)
    got = [n for n in root.walk() if n.type == "curve_surface"]
    assert got and got[0].params["capped"] is False
    assert len([c for c in got[0].children if c.type == "curve"]) == 3


def test_step_keeps_the_surface_exact(app, tmp_path):
    model = DocumentModel()
    _vase(model)
    report = cx.export_model(model.root, tmp_path / "v.step")
    assert report.faceted == 0 and report.exact == 1
    assert "B_SPLINE_SURFACE" in (tmp_path / "v.step").read_text(
        errors="replace")


def test_curves_from_separate_objects_come_together_in_place(app):
    model = DocumentModel()
    objs = []
    for r, z in ((20, 0), (15, 40)):
        c = model.add_node("curve", dict(points=ring(r, 0), closed=True))
        comp = model.enclose_as_part(c)
        comp.params["z"] = float(z)          # the Object is placed
        objs.append(comp)
    surf = cs.make_surface(model, objs, "loft")
    zs = sorted({round(p[2], 6) for c in cs.curves(surf)
                 for p in c.params["points"]})
    assert zs == [-0.0, 40.0] or zs == [0.0, 40.0]
    # the second, now empty, Object is gone; the first holds the surface
    tops = [n for n in model.root.children if n.type == "component"]
    assert len(tops) == 1 and surf.parent is tops[0]


def test_mcp_make_surface(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    ids = []
    for r, z in ((20, 0), (30, 40), (15, 80)):
        got = ex.execute("add_node", {"type": "curve", "params": {
            "points": ring(r, z), "closed": True}})
        ids.append(got["created"])
    got = ex.execute("make_surface", {"curve_ids": ids, "kind": "loft",
                                      "capped": False, "thickness": 1.5})
    assert "error" not in got and "problem" not in got, got
    surf = win.model.find(got["created"]) if hasattr(win.model, "find") \
        else None
    assert got["curves"] == ids or len(got["curves"]) == 3
    win._dirty = False
    win.deleteLater()

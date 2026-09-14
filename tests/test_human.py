"""The human figure: MakeHuman's base mesh and macro targets as one
parametric, baked node.

Run with: python -m pytest tests/  (offscreen Qt).

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
from PyQt5.QtWidgets import QApplication

from khervecad import document, human, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    edges = Counter()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    return all(edges[(v, u)] == n for (u, v), n in edges.items())


def _extent(tris, axis):
    values = [v[axis] for t in tris for v in t]
    return min(values), max(values)


def test_the_data_ships_and_the_body_is_closed_and_to_size():
    assert human.available()
    assert (human.DATA / "LICENSE.txt").read_text().count("CC0") >= 1
    body = human.build(stature=1700)
    assert 20000 < len(body) < 40000
    assert _closed(body)
    lo, hi = _extent(body, 2)
    assert lo == pytest.approx(0) and hi == pytest.approx(1700)
    x0, x1 = _extent(body, 0)
    assert x0 == pytest.approx(-x1, abs=1e-6)              # centred
    y0, y1 = _extent(body, 1)
    assert y0 < -200 and y1 < 150                           # faces -Y
    tall = human.build(stature=1850)
    assert _extent(tall, 2)[1] == pytest.approx(1850)


def test_gender_age_build_and_proportions_change_the_shape():
    female = human.build(gender=0, age=0)
    male = human.build(gender=1, age=0)
    old = human.build(gender=0, age=1)
    heavy = human.build(gender=0, weight=1)
    thin = human.build(gender=0, weight=-1)
    leggy = human.build(gender=0, height=1)
    assert female != male and female != old
    # the waist front to back (clear of the arms): heavy > average > thin
    def depth(tris, z_lo, z_hi):
        ys = [v[1] for t in tris for v in t
              if z_lo <= v[2] <= z_hi and abs(v[0]) < 60]
        return max(ys) - min(ys)
    assert depth(heavy, 1000, 1100) > depth(female, 1000, 1100) \
        > depth(thin, 1000, 1100)
    assert leggy != female
    # the weights behind it: a blend, never more than the sliders ask
    w = human.weights(gender=0.25, age=0.5, weight=0.5, height=-1)
    assert w["female-young"] == pytest.approx(0.375)
    assert w["male-old"] == pytest.approx(0.125)
    assert w["female-maxweight"] == pytest.approx(0.375)
    assert w["male-minheight"] == pytest.approx(0.25)
    assert "female-minweight" not in w


def test_the_human_node_previews_bakes_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    node = doc.add_node("human", dict(gender=1.0, weight=0.5,
                                      stature=1750.0))
    assert not node.is_container()
    tris = mesh.tessellate(doc.root)
    assert _extent(tris, 2)[1] == pytest.approx(1750)
    assert node.id not in validate(doc.root)
    code = doc.to_scad()
    assert ("kcad_human(gender = 1, age = 0, weight = 0.5, height = 0, "
            "stature = 1750,") in code
    assert "module kcad_human(gender = 0, age = 0, weight = 0, height = 0, " \
           "stature = 1700, points = [], faces = [])" in code
    path = tmp_path / "human.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    back = next(n for n in other.root.walk() if n.type == "human")
    assert back.params["gender"] == 1 and back.params["stature"] == 1750
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["stature"] = 0.0
    assert "height" in validate(doc.root)[node.id]


def test_human_is_a_toolbar_primitive_with_a_tip_and_a_tool(app):
    from khervecad import toolbars, tooltips
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    assert "human" in toolbars.PRIMITIVES
    assert "Human" in tooltips.TIPS["human"][0]
    win = MainWindow()
    ex = McpToolExecutor(win)
    out = ex.execute("add_node", {"type": "human",
                                  "params": {"age": 0.8, "stature": 1600}})
    assert "error" not in out, out
    bounds = ex.execute("get_node_bounds", {"node_ids": [out["created"]]})
    assert bounds["nodes"][0]["size"][2] == pytest.approx(1600, abs=0.01)

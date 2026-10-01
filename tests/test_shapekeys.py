"""shapekeys.py: morph targets made of sculpt strokes, blended by values
that may be Customizer variables; the shape_key MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc():
    doc = DocumentModel()
    var = doc.add_node("assign", dict(variable="jaw", value="0"))
    ball = doc.add_node("sphere", dict(radius=20.0))
    node = doc.wrap_nodes([ball], "shape_keys")
    node.params.update(
        detail=2.0, keys=[["jaw", "jaw"], ["puff", 0.0]],
        strokes=[[0, 0, 0, -20, 0, 8, 10, 0, -1, 0],
                 [1, 1, 0, 0, 20, 10, 5, 0, 0, 0]])
    return doc, var, node


def _ymin(doc):
    return np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)[:, 1].min()


def test_a_key_blends_in_linearly_with_its_variable(app):
    doc, var, node = _doc()
    assert node.id not in validate(doc.root)
    assert _ymin(doc) == pytest.approx(-20.0, abs=0.01)
    var.params["value"] = "0.5"
    assert _ymin(doc) == pytest.approx(-25.0, abs=0.05)
    var.params["value"] = "1"
    assert _ymin(doc) == pytest.approx(-30.0, abs=0.05)


def test_a_slider_tick_reuses_the_key_offsets(app):
    doc, var, _node = _doc()
    _ymin(doc)
    var.params["value"] = "0.3"
    _ymin(doc)                                  # the key sculpted once
    var.params["value"] = "0.7"
    t = time.perf_counter()
    _ymin(doc)
    assert time.perf_counter() - t < 0.5


def test_keys_add_up_and_round_trip(app):
    doc, var, node = _doc()
    var.params["value"] = "1"
    node.params["keys"][1][1] = 1.0
    a = np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)
    assert a[:, 1].min() < -29.0 and a[:, 2].max() > 24.0
    root, warnings = scadparse.parse_scad(doc.to_scad())
    assert not warnings
    back = next(n for n in root.walk() if n.type == "shape_keys")
    assert back.params["keys"] == [["jaw", "jaw"], ["puff", 1.0]]
    assert back.params["strokes"] == node.params["strokes"]


def test_validation(app):
    doc, _var, node = _doc()
    node.params["strokes"] = [[5, 0, 0, 0, 0, 1, 1, 0, 0, 0]]
    assert "key 5" in validate(doc.root)[node.id]
    node.params["strokes"] = [[0, 7, 0, 0, 0, 1, 1, 0, 0, 1]]
    assert "snake hook" in validate(doc.root)[node.id]
    node.params["strokes"] = []
    node.params["keys"] = [["a", 0], ["a", 1]]
    assert "same name" in validate(doc.root)[node.id]


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_shape_key_tool_adds_a_key_with_a_slider(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    doc = window.model
    ball = doc.add_node("sphere", dict(radius=20.0))
    out = ex.execute("shape_key", {
        "node_id": ball.id, "key": "Jaw open", "slider": True,
        "detail": 2,
        "strokes": [{"kind": "grab", "at": [0, -20, 0], "radius": 8,
                     "to": [0, -30, 0]}]})
    assert "error" not in out, out
    assert out["keys"] == [["Jaw open", "jaw_open"]]
    var = next(n for n in doc.root.walk() if n.type == "assign"
               and n.params["variable"] == "jaw_open")
    assert var.params["options"] == "0:0.01:1"
    var.params["value"] = "1"
    assert _ymin(doc) < -29.0
    out = ex.execute("shape_key", {"node_id": out["shape_keys"],
                                   "values": {"Jaw open": 0}})
    assert _ymin(doc) == pytest.approx(-20.0, abs=0.05)
    assert "error" in ex.execute("shape_key", {
        "node_id": out["shape_keys"], "values": {"blink": 1}})
    assert "error" in ex.execute("shape_key", {
        "node_id": out["shape_keys"], "key": "horn",
        "strokes": [{"kind": "snake_hook", "at": [0, 0, 20]}]})

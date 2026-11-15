"""MCP surface tools: make_surface sheet / direction / draft and
surface_edit (pieces, trim, knit, thicken).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ex(app):
    w = MainWindow()
    yield McpToolExecutor(w)
    w._dirty = False
    w.close()


def ring(axis, c, r=20, n=24):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        p = [r * math.cos(a), r * math.sin(a)]
        out.append({"y": [c + p[0], -50, p[1]],
                    "x": [-50, c + p[0], p[1]]}[axis])
    return out


def sheet(ex, pts, direction, **kw):
    cid = ex.execute("add_node", {"type": "curve", "params": {
        "points": pts, "closed": True}})["created"]
    return ex.execute("make_surface", dict(
        curve_ids=[cid], kind="extrude", height=100, sheet=True,
        direction=direction, **kw))["created"]


def test_two_tubes_trim_then_thicken_by_the_tools(ex):
    a = sheet(ex, ring("y", 0), "+Y")
    b = sheet(ex, ring("x", 0), "+X")
    pieces = ex.execute("surface_edit", {
        "op": "trim", "action": "pieces", "node_ids": [a, b],
        "mutual": True})["pieces"]
    assert len(pieces) > 2
    smallest = min(pieces, key=lambda p: p["area"])
    made = ex.execute("surface_edit", {
        "op": "trim", "node_ids": [a, b], "mutual": True,
        "remove": [smallest["point"]]})
    assert "problem" not in made
    th = ex.execute("surface_edit", {"op": "thicken",
                                     "node_ids": [made["created"]],
                                     "thickness": 1.5})
    assert th["op"] == "thicken"


def test_the_schema_names_the_new_keys():
    from khervecad import mcp_schema
    names = {t["name"] for t in mcp_schema.TOOLS}
    assert "surface_edit" in names
    ms = next(t for t in mcp_schema.TOOLS if t["name"] == "make_surface")
    props = ms["input_schema"]["properties"]
    assert {"sheet", "direction", "draft"} <= set(props)

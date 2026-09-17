"""The OpenSCAD language coverage through MCP: what an assistant writes
with apply_code comes back as editable nodes (or kept code), get_code
gives the same program back, and the library tools answer.

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
from PyQt5.QtWidgets import QApplication

from khervecad import mcp_bridge
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ex(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    yield McpToolExecutor(win)
    win._dirty = False
    win.close()


def call(ex, _tool, **params):
    result = ex.execute(_tool, params)
    assert "error" not in result, f"{_tool} failed: {result.get('error')}"
    return result


PROGRAM = """\
w = 12;
module twice(gap = 20) { children(); translate([gap, 0, 0]) children(); }
twice(30) resize([w, 0, 0], auto = true) sphere(3);  // Balls
let (h = w / 2) translate([0, 40, 0]) cylinder(h = h, r = 2);  // Post
multmatrix([[1, 0.3, 0, 0], [0, 1, 0, 60], [0, 0, 1, 0]]) cube(5);  // Shear
assert(w > 2, "w must be above 2");
frobnicate(3);
"""


def test_apply_code_takes_the_whole_language(ex):
    result = call(ex, "apply_code", code=PROGRAM, mode="replace")
    kinds = {n.type for n in ex._w.model.root.walk()}
    for kind in ("resize", "let", "multmatrix", "assert", "scad_raw"):
        assert kind in kinds, kind
    # the unknown call is kept as code, and said so
    assert any("frobnicate" in w for w in result.get("warnings", []))


def test_get_code_gives_the_same_program_back(ex):
    call(ex, "apply_code", code=PROGRAM, mode="replace")
    once = call(ex, "get_code")["code"]
    call(ex, "apply_code", code=once, mode="replace")
    assert call(ex, "get_code")["code"] == once


def test_check_code_reports_the_new_statements(ex):
    out = call(ex, "check_code", code=PROGRAM)
    assert out["would_apply"] is True
    for kind in ("resize", "let", "multmatrix", "assert"):
        assert out["types"].get(kind), kind


def test_new_node_types_are_listed_and_addable(ex):
    types = {t["type"] for t in call(ex, "list_node_types")["types"]}
    for kind in ("resize", "multmatrix", "render", "intersection_for",
                 "let", "echo", "assert", "scad_use"):
        assert kind in types
    let = call(ex, "add_node", type="let",
               params={"bindings": "r = 3"})["created"]
    call(ex, "add_node", type="sphere", parent_id=let,
         params={"radius": "r"})
    assert "let (r = 3)" in call(ex, "get_code")["code"]


def test_library_tools(ex, monkeypatch, tmp_path):
    from khervecad import scadlib
    listing = call(ex, "list_scad_libraries")
    keys = {lib["key"] for lib in listing["libraries"]}
    assert {"BOSL2", "MCAD", "NopSCADlib"} <= keys
    assert listing["library_folder"]

    monkeypatch.setattr(scadlib, "install",
                        lambda lib: str(tmp_path / lib.key))
    out = call(ex, "install_scad_library", key="bosl2")
    assert out["installed"] == "BOSL2"
    assert "error" in ex.execute("install_scad_library", {"key": "nope"})


def test_library_install_needs_full_access():
    assert mcp_bridge._names_a_path("install_scad_library", {"key": "BOSL2"})
    assert mcp_bridge.tool_allowed("list_scad_libraries", "read")

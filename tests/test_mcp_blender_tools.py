"""The Blender-style tools as an MCP assistant uses them: OpenSCAD with
kcad_* calls through apply_code, then the checks and tools on the
result — so the MCP side of every new tool is proven, not assumed.

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

from khervecad import csg, mcp_server, mcp_schema
from khervecad.mcp_server import IMAGE_KEY
from khervecad.mcp_tools import McpToolExecutor

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="manifold3d not installed")

PROGRAM = """
kcad_bevel(width = 2, segments = 4) {   // Plate
  difference() {
    cube([40, 30, 10]);
    translate([20, 15, -1]) cylinder(r = 4, h = 20);
  }
}
translate([60, 0, 0]) kcad_remesh(voxel = 0.8) {   // Soup
  cube(12);
  translate([12, 6, 6]) sphere(7);
}
translate([0, 50, 0]) kcad_wireframe(thickness = 1.5) cube(20);   // Cage
translate([60, 50, 0]) kcad_decimate(ratio = 0.25) sphere(10);   // Ball
translate([0, 100, 0]) kcad_subdivide(levels = 2, sharp = 40)   // Smooth
  cylinder(r = 8, h = 16);
translate([60, 100, 0]) kcad_push_pull(pushes = [[10, 10, 10, -3, 2]])
  cube([20, 20, 10]);   // Tray
translate([0, 150, 0]) kcad_bisect(pz = 5, keep = "below")   // Dome
  sphere(12);
translate([60, 150, 0]) kcad_shrinkwrap(offset = 1, keep = "all") {
  sphere(6);   // Cap
  sphere(12);   // Head
}
translate([0, 200, 0]) kcad_cloth(lift = 10, detail = 6, steps = 60) {
  square([60, 60], center = true);   // Cloth
  translate([-12, -12, 0]) cube([24, 24, 30]);   // Stand
}
"""

TYPES = ("bevel", "remesh", "wireframe", "decimate", "subdivide",
         "push_pull", "bisect", "shrinkwrap", "cloth")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def session(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    ex = McpToolExecutor(win)

    def call(_tool, **params):
        out = ex.execute(_tool, params)
        assert "error" not in out, f"{_tool}: {out.get('error')}"
        return out
    call("apply_code", code=PROGRAM)
    return win, ex, call


def _node(win, kind):
    return next(n for n in win.model.root.walk() if n.type == kind)


def test_every_new_node_parses_from_an_assistants_program(session):
    win, _ex, _call = session
    kinds = {n.type for n in win.model.root.walk()}
    assert set(TYPES) <= kinds
    from khervecad.model import validate
    bad = {k: v for k, v in validate(win.model.root).items()}
    assert not bad, bad


def test_the_document_reports_what_is_available(session):
    _win, _ex, call = session
    info = call("get_document_info")
    assert info["exact_preview_booleans"]["available"] is True
    assert "available" in info["blender"]


def test_the_schema_offers_the_nodes_and_tools(session):
    assert set(TYPES) <= set(mcp_schema.WRAP_TYPES)
    names = {t["name"] for t in mcp_schema.TOOLS}
    assert {"reach", "drop_parts", "push_pull_face",
            "render_photo"} <= names


def test_the_instructions_teach_each_tool():
    text = mcp_server._INSTRUCTIONS
    for word in ("kcad_bevel", "kcad_decimate", "kcad_remesh",
                 "kcad_shrinkwrap", "kcad_wireframe", "kcad_cloth",
                 "push_pull_face", "kcad_bisect", "sharp = ", "reach",
                 "drop_parts", "heatmap", "render_photo"):
        assert word in text, word
    assert "APPROXIMATES booleans (it shows the first" not in text


def test_bevel_removed_material_and_the_hole_is_cut(session):
    win, _ex, call = session
    plate = _node(win, "bevel")
    out = call("mass_properties", node_ids=[plate.id])
    full = 40 * 30 * 10 - math.pi * 16 * 10
    assert 0.9 * full < out["volume_mm3"] < full


def test_remesh_output_passes_the_print_check(session):
    win, _ex, call = session
    soup = _node(win, "remesh")
    out = call("check_printability", node_ids=[soup.id])
    water = next(c for c in out["checks"] if c["name"] == "Watertight")
    assert water["status"] == "pass"


def test_push_pull_cut_its_pocket(session):
    win, _ex, call = session
    tray = _node(win, "push_pull")
    out = call("mass_properties", node_ids=[tray.id])
    assert out["volume_mm3"] == pytest.approx(4000 - 16 * 16 * 3, rel=1e-6)


def test_heatmap_and_render_view(session):
    _win, _ex, call = session
    out = call("set_render_options", heatmap="thickness",
               heat_min_wall=1.2)
    assert out["heatmap"]["thinnest"] is not None
    picture = call("render_view", wait_for_exact=False)
    assert picture[IMAGE_KEY]
    call("set_render_options", heatmap="off")


def test_push_pull_face_by_a_probed_point(session):
    win, _ex, call = session
    call("apply_code", code="translate([200, 0, 0]) cube([30, 30, 10]);")
    part = [n for n in win.model.root.walk() if n.type == "cube"][-1]
    hit = call("probe_surface", **{"from": [215, 15, 50],
                                   "direction": [0, 0, -1]})
    point = hit["hits"][0]["point"]
    out = call("push_pull_face", node_id=part.id, point=point,
               distance=5)
    node = win.model.find(out["node"]) if hasattr(win.model, "find") \
        else next(n for n in win.model.root.walk() if n.id == out["node"])
    vol = call("mass_properties", node_ids=[node.id])["volume_mm3"]
    assert vol == pytest.approx(30 * 30 * 15, rel=1e-6)


def test_drop_parts_and_reach(session):
    win, _ex, call = session
    call("apply_code", code="""
translate([300, 0, 40]) rotate([0, 35, 0]) cube([4, 4, 30]);  // Post
translate([400, 0, 0]) kcad_joint(pivot = [2, 2, 0]) {
  cube([4, 4, 50]);   // Upper
  kcad_joint(pivot = [2, 2, 50]) {
    translate([0, 0, 50]) cube([4, 4, 40]);   // Fore
    translate([0, 0, 90]) cube([4, 4, 4]);    // Grip
  }
}""")
    post = next(n for n in win.model.root.walk() if "Post" in n.name)
    top = post
    while top.parent is not win.model.root:
        top = top.parent
    dropped = call("drop_parts", node_ids=[top.id])["dropped"][0]
    assert dropped["tipped_deg"] > 30
    grip = next(n for n in win.model.root.walk() if "Grip" in n.name)
    out = call("reach", node_id=grip.id, target=[430, 10, 60])
    assert out["reached"] and out["miss"] < 1.0

"""Sculpting: brush strokes on a mesh, the sculpt node, the click panel
and the sculpt_stroke MCP tool.

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

from khervecad import deform, document, mesh, scadparse, sculpt
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, x1, y1, z1):
    quads = [((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)),
             ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]


def _closed(tris) -> bool:
    edges = Counter()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    return all(edges[(v, u)] == n for (u, v), n in edges.items())


def _top(tris, x, y):
    return max(v[2] for t in tris for v in t
               if abs(v[0] - x) < 1e-6 and abs(v[1] - y) < 1e-6)


def _fine_cube():
    return deform.split_long_edges(_box(0, 0, 0, 20, 20, 20), 2.0)


# ── geometry ───────────────────────────────────────────────────────

def test_inflate_raises_a_bump_that_falls_off_to_the_radius():
    out = sculpt.sculpt(_fine_cube(), [[1, 10, 10, 20, 6, 3, 0, 0, 0]])
    assert _closed(out)
    assert _top(out, 10, 10) == pytest.approx(23)          # full strength
    assert 20 < _top(out, 12.5, 10) < 23                     # falling off
    assert _top(out, 0, 0) == pytest.approx(20)            # outside
    pulled = sculpt.sculpt(_fine_cube(), [[1, 10, 10, 20, 6, -2, 0, 0, 0]])
    assert _top(pulled, 10, 10) == pytest.approx(18)


def test_grab_drags_along_the_direction_and_smooth_relaxes():
    out = sculpt.sculpt(_fine_cube(), [[0, 10, 10, 20, 6, 4, 1, 0, 0]])
    xs = [v[0] for t in out for v in t if v[2] > 19.9 and abs(v[1] - 10) < 1e-6]
    assert any(abs(x - 14) < 1e-6 for x in xs)             # centre moved +4
    assert all(x <= 20 + 1e-6 for x in xs)                 # the rim stayed
    bumped = sculpt.sculpt(_fine_cube(), [[1, 10, 10, 20, 4, 3, 0, 0, 0]])
    relaxed = sculpt.sculpt(_fine_cube(), [[1, 10, 10, 20, 4, 3, 0, 0, 0],
                                           [2, 10, 10, 23, 6, 3, 0, 0, 0]])
    assert _top(relaxed, 10, 10) < _top(bumped, 10, 10)
    assert _closed(relaxed)


def test_flatten_and_pinch():
    bumped = [[1, 10, 10, 20, 6, 3, 0, 0, 0]]
    flat = sculpt.sculpt(_fine_cube(), bumped + [[3, 10, 10, 23, 8, 1, 0, 0, 0]])
    assert _top(flat, 10, 10) < 23
    pinched = sculpt.sculpt(_fine_cube(), [[4, 10, 10, 20, 6, 0.5, 0, 0, 0]])
    # the top vertices beside the centre were 1.25 mm apart: pinched in
    row = sorted({v[0] for t in pinched for v in t
                  if abs(v[2] - 20) < 1e-6 and abs(v[1] - 10) < 1e-6
                  and 10 < v[0] < 12.4})
    assert row == pytest.approx([10.695, 11.720], abs=0.01)   # from 11.25, 12.5


def test_mirror_repeats_the_stroke_across_the_plane():
    # a box centred on the origin (its vertices sit 1.25 mm apart)
    box = deform.split_long_edges(_box(-10, -10, 0, 10, 10, 20), 2.0)
    out = sculpt.sculpt(box, [[1, 3.75, 0, 20, 3, 2, 0, 0, 0]], "x")
    assert _top(out, 3.75, 0) == pytest.approx(22)
    assert _top(out, -3.75, 0) == pytest.approx(22)
    plain = sculpt.sculpt(box, [[1, 3.75, 0, 20, 3, 2, 0, 0, 0]])
    assert _top(plain, -3.75, 0) == pytest.approx(20)


def test_bad_rows_are_skipped_and_kinds_resolve():
    out = sculpt.sculpt(_fine_cube(), [[1, 10, 10], "nonsense", [9, 1, 1, 1, 1, 1, 0, 0, 0]])
    assert _top(out, 10, 10) == pytest.approx(20)
    assert sculpt.kind_index("Inflate") == 1 and sculpt.kind_index(4) == 4
    assert sculpt.kind_index("dig") == -1 and sculpt.kind_index(7) == -1
    assert sculpt.sculpt([], [[1, 0, 0, 0, 1, 1, 0, 0, 0]]) == []


def test_to_local_maps_a_placed_part_back_to_its_frame():
    local = _box(0, 0, 0, 10, 10, 10)
    # placed: rotated 90° about z then moved +50 x
    def place(v):
        return (-v[1] + 50, v[0], v[2])
    world = [tuple(place(v) for v in t) for t in local]
    p, d = sculpt.to_local(world, local, (45, 5, 10), (0, 1, 0))
    assert p == pytest.approx([5, 5, 10])
    assert d == pytest.approx([1, 0, 0])
    assert sculpt.to_local(world, local[:-1], (0, 0, 0)) == (None, None)


# ── the node ───────────────────────────────────────────────────────

def _sculpted_cube(app):
    doc = DocumentModel()
    cube = doc.add_node("cube")
    node = doc.wrap_nodes([cube], "sculpt")
    node.params["strokes"] = [[1, 10, 10, 20, 6, 3, 0, 0, 0]]
    return doc, node


def test_the_sculpt_node_previews_bakes_and_round_trips(app, tmp_path):
    doc, node = _sculpted_cube(app)
    tris = mesh.tessellate(doc.root)
    assert _closed(tris) and max(v[2] for t in tris for v in t) == pytest.approx(23)
    code = doc.to_scad()
    assert ('kcad_sculpt(strokes = [[1, 10, 10, 20, 6, 3, 0, 0, 0]], '
            'detail = 1.5, mirror = "none",') in code
    path = tmp_path / "sculpt.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    back = next(n for n in other.root.walk() if n.type == "sculpt")
    assert back.params["strokes"] == [[1, 10, 10, 20, 6, 3, 0, 0, 0]]
    assert back.params["mirror"] == "none"


def test_sculpt_validation_names_the_bad_stroke(app):
    doc, node = _sculpted_cube(app)
    assert node.id not in validate(doc.root)
    node.params["strokes"] = [[7, 1, 1, 1, 1, 1, 0, 0, 0]]
    assert "kind" in validate(doc.root)[node.id]
    node.params["strokes"] = [[1, 1, 1, 1, 0, 1, 0, 0, 0]]
    assert "radius" in validate(doc.root)[node.id]
    node.params["strokes"] = [[1, 1, 1]]
    assert "9 values" in validate(doc.root)[node.id]
    node.params["strokes"] = []
    node.params["mirror"] = "w"
    assert "mirror" in validate(doc.root)[node.id]


def test_sculpt_is_a_deform_family_tool_with_a_tip(app):
    from khervecad import toolbars, tooltips
    assert "sculpt" in dict(toolbars.OPERATION_GROUPS)["deform"]
    assert "Sculpt" in tooltips.TIPS["sculpt"][0]


# ── the panel and the MCP tool ─────────────────────────────────────

@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_the_panel_lands_a_stroke_per_click_in_the_local_frame(window):
    from khervecad import sculpt_ui
    doc = window.model
    move = doc.add_node("translate", dict(x=50.0))
    cube = doc.add_node("cube", parent=move)
    node = doc.wrap_nodes([cube], "sculpt")
    panel = sculpt_ui.start(window, node)
    assert window.view3d._pick_cb is not None
    panel.radius.setValue(6.0)
    panel.strength.setValue(2.0)
    window.view3d._pick_cb(dict(kind="face", point=[60.0, 10.0, 20.0],
                                normal=[0.0, 0.0, 1.0]), node)
    rows = node.params["strokes"]
    assert len(rows) == 1
    assert rows[0][0] == 1 and rows[0][1:4] == pytest.approx([10, 10, 20])
    assert rows[0][4:6] == [6.0, 2.0]
    assert window.view3d._pick_cb is not None           # re-armed
    panel.mirror.setCurrentText("x")
    assert node.params["mirror"] == "x"
    panel.undo_last()
    assert node.params["strokes"] == []
    panel.close()


def test_sculpt_stroke_tool_wraps_maps_and_batches(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    doc = window.model
    move = doc.add_node("translate", dict(x=50.0))
    cube = doc.add_node("cube", parent=move)
    out = ex.execute("sculpt_stroke", {
        "node_id": cube.id, "kind": "inflate", "at": [60, 10, 20],
        "radius": 6, "strength": 3, "mirror": "none"})
    assert "error" not in out, out
    node = doc.find(out["sculpt"]) if hasattr(doc, "find") else \
        next(n for n in doc.root.walk() if n.id == out["sculpt"])
    assert node.type == "sculpt" and out["strokes"] == 1
    assert node.params["strokes"][0][1:4] == pytest.approx([10, 10, 20])
    out = ex.execute("sculpt_stroke", {
        "node_id": node.id,
        "strokes": [{"kind": "grab", "at": [60, 10, 23], "radius": 4,
                     "strength": 1, "direction": [0, 1, 0]},
                    {"kind": "smooth", "at": [60, 10, 23], "radius": 8,
                     "strength": 1}]})
    assert out["added"] == 2 and out["strokes"] == 3
    tris = mesh.tessellate(doc.root)
    assert max(v[2] for t in tris for v in t) > 20.5
    assert "error" in ex.execute("sculpt_stroke", {"node_id": node.id})
    assert "error" in ex.execute("sculpt_stroke", {
        "node_id": node.id, "kind": "dig", "at": [0, 0, 0]})
    assert "error" in ex.execute("sculpt_stroke", {
        "node_id": node.id, "kind": "grab", "at": [0, 0]})

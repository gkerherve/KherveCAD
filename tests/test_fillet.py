"""Fillet / chamfer chosen edges: geometry (fillet.py), the node, the
pick flow, the MCP tools and the real OpenSCAD engine.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import document, fillet, fillet_pick, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(u, w)] += 1
    return all(n == 1 and count[(w, u)] == 1
               for (u, w), n in count.items())


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def _box(w=40.0, d=30.0, h=20.0):
    doc = DocumentModel()
    doc.set_global_fn(False)
    cube = doc.add_node("cube", dict(width=w, depth=d, height=h))
    return doc, cube


# ------------------------------------------------------------ geometry
def test_a_box_has_twelve_convex_creases_and_a_cylinder_two_rims(app):
    doc, _cube = _box()
    edges = fillet.crease_edges(mesh.tessellate(doc.root))
    assert len(edges) == 12 and all(e.convex for e in edges)
    assert all(abs(e.angle - 90) < 1e-6 for e in edges)
    other = DocumentModel()
    other.set_global_fn(False)
    other.add_node("cylinder", dict(radius_bottom=10.0, radius_top=10.0,
                                    height=20.0, segments=24))
    chains = fillet.chains(mesh.tessellate(other.root))
    assert [(c["segments"], c["closed"], c["convex"]) for c in chains] \
        == [(24, True, True), (24, True, True)]     # facets are not edges


def test_a_chain_stops_at_a_box_corner(app):
    doc, _cube = _box()
    chains = fillet.chains(mesh.tessellate(doc.root))
    assert len(chains) == 12
    assert all(c["segments"] == 1 and not c["closed"] for c in chains)


def test_an_extruded_l_profile_has_a_concave_edge(app):
    doc = DocumentModel()
    doc.set_global_fn(False)
    ext = doc.add_node("linear_extrude", dict(height=30.0))
    doc.add_node("polygon", dict(points=[[0, 0], [40, 0], [40, 10],
                                         [10, 10], [10, 30], [0, 30]]),
                 parent=ext)
    edges = fillet.crease_edges(mesh.tessellate(doc.root))
    concave = [e for e in edges if not e.convex]
    assert len(concave) == 1
    assert sorted([round(v, 3) for v in concave[0].a][:2]) == [10.0, 10.0]


def test_profile_is_tangent_to_both_faces():
    e = fillet.Edge((0.0, 0.0, 20.0), (40.0, 0.0, 20.0),
                    (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), 90.0, True)
    u, v, pts = fillet.profile(e, 4.0, "round", 8)
    assert len(pts) == 2 + 8                     # E, TL, 7 arc pts, TR
    # a 90° corner: tangent points one radius from the edge, the arc
    # midpoint at radius * (sqrt2 - 1) from it along the bisector
    assert math.hypot(*pts[1]) == pytest.approx(4.0)
    assert math.hypot(*pts[-1]) == pytest.approx(4.0)
    assert math.hypot(*pts[1 + 4]) == pytest.approx(4.0 * (math.sqrt(2) - 1))
    _u, _v, cham = fillet.profile(e, 4.0, "chamfer", 8)
    assert len(cham) == 3


def test_strips_are_closed_solids_and_cut_the_right_volume(app):
    doc, cube = _box()
    tris = mesh.tessellate(doc.root)
    result = fillet.compute(tris, [[0, 0, 20, 40, 0, 20]], 5.0)
    assert len(result["cuts"]) == 1 and not result["adds"]
    cut = result["cuts"][0]
    assert _closed(cut)
    # the kite prism minus the quarter cylinder, (1 - pi/4) r² L, plus
    # the six circular segments the chords leave inside the circle
    ideal = (1 - math.pi / 4) * 25 * 40
    theta = math.pi / 2 / 6
    segments = 6 * 12.5 * (theta - math.sin(theta)) * 40
    assert _volume(cut) == pytest.approx(ideal + segments, rel=0.005)


def test_one_seed_takes_a_whole_rim_and_seeds_dedupe(app):
    doc = DocumentModel()
    doc.set_global_fn(False)
    doc.add_node("cylinder", dict(radius_bottom=10.0, radius_top=10.0,
                                  height=20.0, segments=24))
    tris = mesh.tessellate(doc.root)
    rim = [c for c in fillet.chains(tris) if c["centre"][2] > 10][0]
    seeds = [rim["seed"], rim["seed"]]         # twice: one chain
    result = fillet.compute(tris, seeds, 3.0)
    assert result["chains"] == 1 and len(result["cuts"]) == 1
    assert _closed(result["cuts"][0])


def test_a_remembered_edge_survives_a_resize_but_not_removal(app):
    doc, cube = _box()
    tris = mesh.tessellate(doc.root)
    seed = [0, 0, 20, 40, 0, 20]
    assert not fillet.compute(tris, [seed], 2.0)["missing"]
    # the same edge, nudged a little: still found
    assert not fillet.compute(tris, [[0.2, 0.1, 20.1, 40.1, 0, 20]],
                              2.0)["missing"]
    # an edge that is not there any more
    assert fillet.compute(tris, [[0, 15, 20, 40, 15, 20]], 2.0)["missing"]


# ---------------------------------------------------------- the node
def test_the_node_validates_previews_and_compiles(app):
    doc, cube = _box()
    node = doc.wrap_nodes([cube], "fillet")
    assert validate(doc.root) == {}               # no edges yet: fine
    node.params.update(radius=4.0, edges=[[0, 0, 20, 40, 0, 20]])
    assert validate(doc.root) == {}
    tris = mesh.tessellate(doc.root)
    assert tris and _closed(tris)                 # preview: the child
    code = doc.to_scad()
    assert "module kcad_fillet(" in code
    assert "kcad_fillet(radius = 4" in code and "cuts = [" in code
    assert "cube(" in code
    assert mesh.uses_booleans(doc.root)           # badge: approximated


def test_the_fillet_round_trips_through_its_program(app, tmp_path):
    doc, cube = _box()
    node = doc.wrap_nodes([cube], "fillet")
    node.params.update(radius=3.0, kind="chamfer", detail=4,
                       edges=[[0, 0, 20, 40, 0, 20], [40, 0, 20, 40, 30, 20]])
    code1 = doc.to_scad()
    path = tmp_path / "fillet.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    other.set_global_fn(False)
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code1.splitlines()[3:]
    back = next(n for n in other.root.walk() if n.type == "fillet")
    assert back.params["kind"] == "chamfer" and back.params["detail"] == 4
    assert len(back.params["edges"]) == 2
    assert [c.type for c in back.children] == ["cube"]


def test_fillet_validation(app):
    doc = DocumentModel()
    doc.set_global_fn(False)
    empty = doc.add_node("fillet")
    flat = doc.add_node("fillet")
    doc.add_node("circle", parent=flat)
    loop = doc.add_node("for_loop")
    nested = doc.add_node("fillet", parent=loop)
    doc.add_node("cube", parent=nested)
    gone = doc.add_node("fillet", dict(edges=[[0, 15, 20, 40, 15, 20]]))
    doc.add_node("cube", parent=gone)
    short = doc.add_node("fillet", dict(edges=[[0, 0, 0]]))
    doc.add_node("cube", parent=short)
    errors = validate(doc.root)
    assert "empty" in errors[empty.id]
    assert "2D" in errors[flat.id]
    assert "for" in errors[nested.id]
    assert "not found" in errors[gone.id]
    assert "6 values" in errors[short.id]


def test_the_example_loads_and_validates(app):
    from khervecad import examples
    doc = DocumentModel()
    build = next(b for n, _c, b in examples.EXAMPLES if "fillet" in n)
    examples.load_example(doc, build)
    assert validate(doc.root) == {}
    assert len(mesh.tessellate(doc.root)) > 100


# ---------------------------------------------------------- picking
@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_picking_an_edge_and_a_face_adds_local_seeds(window):
    model = window.model
    model.set_global_fn(False)
    move = model.add_node("translate", dict(x=100.0, y=0.0, z=0.0))
    cube = model.add_node("cube", dict(width=40.0, depth=30.0,
                                       height=20.0), parent=move)
    node = model.wrap_nodes([cube], "fillet")
    assert fillet_pick.start(window, node)
    assert window.view3d._pick_cb is not None
    world, local = fillet_pick.meshes(window, node)
    assert len(world) == len(local)
    # the world edge sits at x = 100..140; the seed is stored local
    seg = [[100.0, 0.0, 20.0], [140.0, 0.0, 20.0]]
    seeds = fillet_pick.seeds_from_pick(dict(kind="edge", seg=seg),
                                        world, local)
    assert seeds == [[0.0, 0.0, 20.0, 40.0, 0.0, 20.0]]
    # a face: every crease round the top
    top = [t for t in world if all(abs(v[2] - 20.0) < 1e-9 for v in t)]
    seeds = fillet_pick.seeds_from_pick(dict(kind="face", tris=top),
                                        world, local)
    assert len(seeds) == 4
    # the live flow: a click adds, Esc finishes and selects the fillet
    window.view3d._pick_cb(dict(kind="edge", seg=seg), node)
    assert node.params["edges"] == [[0.0, 0.0, 20.0, 40.0, 0.0, 20.0]]
    assert window.view3d._pick_cb is not None         # re-armed
    window.view3d._pick_cb(dict(kind="edge", seg=seg), node)  # dup
    assert len(node.params["edges"]) == 1
    window.view3d.cancel_pick()
    assert window.view3d._pick_cb is None
    assert validate(model.root) == {}


def test_the_toolbar_wraps_and_starts_the_pick(window):
    model = window.model
    cube = model.add_node("cube")
    window.builder.active_tree().select_nodes([cube])
    window._apply_operation("fillet")
    assert cube.parent.type == "fillet"
    assert window.view3d._pick_cb is not None
    window.view3d.cancel_pick()


# ---------------------------------------------------------- MCP tools
def test_mcp_lists_edges_and_fillets_by_chain(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    model = window.model
    model.set_global_fn(False)
    cyl = model.add_node("cylinder", dict(radius_bottom=10.0,
                                          radius_top=10.0, height=20.0,
                                          segments=24))
    listed = ex.execute("list_edges", {"node_id": cyl.id})
    assert len(listed["edges"]) == 2
    assert all(e["closed"] and e["segments"] == 24 for e in listed["edges"])
    top = next(i for i, e in enumerate(listed["edges"])
               if e["centre"][2] > 10)
    out = ex.execute("fillet_edges", {"node_id": cyl.id, "chains": [top],
                                      "radius": 2.5})
    node = model.find(out["fillet"])
    assert node.type == "fillet" and cyl.parent is node
    assert out["edges"] == 1 and "error" not in out
    # adding by seed row to the same fillet, through the child
    bottom = [e for e in listed["edges"] if e["centre"][2] <= 10][0]
    again = ex.execute("fillet_edges", {"node_id": cyl.id,
                                        "edges": [bottom["seed"]]})
    assert again["fillet"] == node.id and again["edges"] == 2


# ---------------------------------------------------------- the engine
def _openscad_binary():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def test_the_cut_follows_the_document_segment_count(app, tmp_path):
    """The rim was picked on a 24-segment cylinder, but the document's
    common $fn renders it with 45: the cut must be built for the rim
    OpenSCAD draws, or it straddles the wrong facets and misses."""
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc = DocumentModel()
    doc.set_global_fn(False)
    cyl = doc.add_node("cylinder", dict(radius_bottom=10.0, radius_top=10.0,
                                        height=12.0, segments=24))
    rim = [c for c in fillet.chains(mesh.tessellate(doc.root))
           if c["centre"][2] > 6][0]
    node = doc.wrap_nodes([cyl], "fillet")
    node.params.update(radius=2.0, edges=[rim["seed"]])
    doc.set_global_fn(True, 45)                  # now everything is 45
    assert validate(doc.root) == {}
    scad, stl = tmp_path / "rim.scad", tmp_path / "rim.stl"
    scad.write_text(doc.to_scad())
    assert "$fn=45" in scad.read_text() or "$fn = 45" in scad.read_text()
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    plain = math.pi * 100 * 12 * (math.sin(2 * math.pi / 45) * 45
                                  / (2 * math.pi))
    removed = (1 - math.pi / 4) * 4 * 2 * math.pi * 9   # torus corner
    assert _volume(exact) == pytest.approx(plain - removed, rel=0.02)


def test_openscad_rounds_the_edge_to_the_analytic_volume(app, tmp_path):
    binary = _openscad_binary()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    from khervecad import engine
    doc, cube = _box()
    node = doc.wrap_nodes([cube], "fillet")
    node.params.update(radius=5.0, edges=[[0, 0, 20, 40, 0, 20]])
    scad, stl = tmp_path / "fillet.scad", tmp_path / "fillet.stl"
    scad.write_text(doc.to_scad())
    run = subprocess.run([binary, "-o", str(stl), str(scad)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr[-1500:]
    exact = engine.parse_stl(str(stl))
    assert _volume(exact) == pytest.approx(
        40 * 30 * 20 - (1 - math.pi / 4) * 25 * 40, rel=0.002)

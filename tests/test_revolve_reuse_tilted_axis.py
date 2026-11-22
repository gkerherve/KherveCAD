# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Two things the "Model Mania" pipe body needed (2026-11-22): a Revolved
Cut made from the INNER region of the sketch Revolve1 already turned
(one sketch, several features), and a revolve about a construction line
that is neither vertical nor through the origin — its profile came out
of OpenSCAD as "children of rotate_extrude() may not lie across the Y
axis" (the baked points are rounded, the axis is not), so the pipe
vanished from the exact render."""

import math
import shutil
import subprocess

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ex(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    w.show()
    QApplication.processEvents()
    w._test_ex = McpToolExecutor(w)
    w._test_ex.win = w
    return w._test_ex


def _seg(ex, sk, a, b, bulge=0):
    p = dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=0.01)
    if bulge:
        p["bulge"] = bulge
    return ex.execute("add_node", dict(type="line", parent_id=sk,
                                       params=p))["created"]


def _volume(win):
    from khervecad import analysis, csg, mesh
    tris = mesh.tessellate(win.model.root)
    u = csg.to_manifold([(t, None, False) for t in tris], {})
    return u.volume() if u is not None else analysis.mass_properties(
        tris)["volume"]


def test_cut_revolve_from_the_inner_region_of_a_revolved_sketch(ex):
    t = math.tan(math.radians(22.5))
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]
    # outer wall x = 2 up to a quarter dome R2; inner wall x = 1.5, dome R1.5
    for a, b in (((0, 0), (2, 0)), ((2, 0), (2, 2)), ((0, 4), (0, 0)),
                 ((0, 0), (1.5, 0)), ((1.5, 0), (1.5, 2))):
        _seg(ex, sk, a, b)
    _seg(ex, sk, (2, 2), (0, 4), t)
    _seg(ex, sk, (1.5, 2), (0, 3.5), t)
    ex.execute("sketch_feature", dict(
        node_id=sk, kind="revolved_boss",
        regions=[[1.75, 1.0], [0.5, 1.0]]))
    outer = _volume(ex.win)
    assert outer == pytest.approx(
        math.pi * 4 * 2 + 2 / 3 * math.pi * 8, rel=0.03)
    part = ex.win.model.wrap_nodes(
        [c for c in ex.win.model.root.children if c.visible], "union")
    made = ex.execute("sketch_feature", dict(
        node_id=sk, kind="revolved_cut", regions=[[0.5, 1.0]],
        part_id=part.id))
    assert made["kind"] == "revolved_cut" and made["regions"] == 1
    cavity = math.pi * 1.5 ** 2 * 2 + 2 / 3 * math.pi * 1.5 ** 3
    assert _volume(ex.win) == pytest.approx(outer - cavity, rel=0.03)


def test_revolved_cut_button_takes_a_region_of_the_used_sketch(ex):
    """The ribbon's Revolved Cut: the click on a region (feature_pick's
    own dispatch) of the sketch Revolve1 used makes the cut."""
    from khervecad import feature_pick, sketch_regions
    t = math.tan(math.radians(22.5))
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]
    for a, b in (((0, 0), (2, 0)), ((2, 0), (2, 2)), ((0, 4), (0, 0)),
                 ((0, 0), (1.5, 0)), ((1.5, 0), (1.5, 2))):
        _seg(ex, sk, a, b)
    _seg(ex, sk, (2, 2), (0, 4), t)
    _seg(ex, sk, (1.5, 2), (0, 3.5), t)
    ex.execute("sketch_feature", dict(
        node_id=sk, kind="revolved_boss",
        regions=[[1.75, 1.0], [0.5, 1.0]]))
    outer = _volume(ex.win)
    win = ex.win
    source = next(n for n in win.model.root.walk() if n.type == "regions")
    faces = sketch_regions.faces(sketch_regions.shapes_of(source))
    inner = sketch_regions.face_at(faces, (0.5, 1.0))
    win._feature_pick = None
    feature_pick.start(win, "revolved_cut")
    win._feature_pick["sketches"] = [source]
    feature_pick.picked(win, {"kind": "face"}, ("region", 0, inner))
    QApplication.processEvents()
    cavity = math.pi * 1.5 ** 2 * 2 + 2 / 3 * math.pi * 1.5 ** 3
    assert _volume(win) == pytest.approx(outer - cavity, rel=0.03)


def test_revolve_about_a_tilted_construction_line_renders_in_openscad(ex):
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]
    a = math.radians(6)
    nrm = (-math.sin(a), math.cos(a))
    c0 = (0.0, 2.76)
    c1 = (2.40, 2.76 + 2.40 * math.tan(a))
    top0 = (c0[0] + 0.41 * nrm[0], c0[1] + 0.41 * nrm[1])
    top1 = (c1[0] + 0.60 * nrm[0], c1[1] + 0.60 * nrm[1])
    for p, q in ((c0, top0), (top0, top1), (top1, c1), (c1, c0)):
        _seg(ex, sk, p, q)
    axis = _seg(ex, sk, c0, c1)
    ex.execute("sketch_modify", dict(action="construction", node_id=axis))
    ex.execute("sketch_feature", dict(node_id=sk, kind="revolved_boss",
                                      regions=[[1.2, 3.1]]))
    length = math.hypot(*(c1[i] - c0[i] for i in (0, 1)))
    want = math.pi / 3 * length * (0.41 ** 2 + 0.41 * 0.6 + 0.6 ** 2)
    assert _volume(ex.win) == pytest.approx(want, rel=0.04)
    exe = shutil.which("openscad")
    if exe is None:
        pytest.skip("OpenSCAD not installed")
    import os
    import tempfile
    d = tempfile.mkdtemp()
    scad, stl = os.path.join(d, "a.scad"), os.path.join(d, "a.stl")
    open(scad, "w").write(ex.execute("get_code", {})["code"])
    out = subprocess.run([exe, "-o", stl, scad], capture_output=True,
                         text=True).stderr
    assert "across the Y axis" not in out, out[-400:]
    assert os.path.getsize(stl) > 500

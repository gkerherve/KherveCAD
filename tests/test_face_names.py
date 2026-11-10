# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Faces named by what made them, and fillets that find their edges by
those names after the history is rebuilt (2026-11-10, the user: redo the
process, don't guess where the edge went)."""
import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import face_names, fillet
from khervecad.anchors import doc_env
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _forget_coordinates(fil):
    """Only the names may find the edge from here on."""
    fil.params[fillet.PLACES] = {}


def test_an_extrude_names_its_sides_and_caps(app):
    m = DocumentModel()
    ext = m.add_node("linear_extrude", dict(height=10))
    m.add_node("rect", dict(x=0, y=0, width=40, height=20), parent=ext)
    from khervecad import mesh
    tris = mesh.tessellate(ext, {})
    got = set(face_names.names(m.root, {}, tris))
    key = face_names._key(ext)
    assert {key + ":cap0", key + ":cap1"} <= got
    assert {key + ":0.e%d" % i for i in range(4)} <= got
    assert None not in got


def test_an_inside_corner_found_by_name_however_far_it_moved(app):
    m = DocumentModel()
    fil = m.add_node("fillet", dict(radius=2, kind="round", detail=6,
                                     edges=[[10, 10, 0, 10, 10, 10]]))
    ext = m.add_node("linear_extrude", dict(height=10), parent=fil)
    poly = m.add_node("polygon", dict(x=0, y=0, points=[
        [0, 0], [40, 0], [40, 10], [10, 10], [10, 30], [0, 30]]),
        parent=ext)
    env = doc_env(m)
    assert not fillet.baked(fil, env)["missing"]
    assert len(fil.params[fillet.NAMES]["10,10,0,10,10,10"]) == 2
    _forget_coordinates(fil)
    m.set_param(poly, "points", [[0, 0], [90, 0], [90, 45], [35, 45],
                                  [35, 80], [0, 80]])
    got = fillet.baked(fil, env)
    assert not got["missing"] and got["adds"]


def test_a_sloped_face_found_by_name(app):
    m = DocumentModel()
    a = math.atan2(14, 25)
    fil = m.add_node("fillet", dict(radius=2, kind="round", detail=6,
                                     edges=[], faces=[[-7.5, 0, 17,
                                                       math.sin(a), 0,
                                                       math.cos(a)]]))
    base = m.add_node("translate", dict(x=-30, y=-15, z=0), parent=fil)
    m.add_node("cube", dict(width=60, depth=30, height=10), parent=base)
    rot = m.add_node("rotate", dict(x=90, y=0, z=0), parent=fil)
    ext = m.add_node("linear_extrude", dict(height=20, center=True),
                     parent=rot)
    tri = m.add_node("polygon", dict(x=0, y=0, points=[
        [-20, 10], [-20, 24], [5, 10]]), parent=ext)
    env = doc_env(m)
    assert not fillet.baked(fil, env)["missing"]
    assert fil.params[fillet.NAMES]
    _forget_coordinates(fil)
    # a much steeper, longer rib: the old direction is 30 degrees off
    m.set_param(tri, "points", [[-20, 10], [-20, 40], [28, 10]])
    got = fillet.baked(fil, env)
    assert not got["missing"]
    assert got["cuts"] or got["adds"]


def test_a_cylinder_rim_found_by_name(app):
    m = DocumentModel()
    fil = m.add_node("fillet", dict(radius=1, kind="chamfer", detail=6,
                                     edges=[]))
    cyl = m.add_node("cylinder", dict(height=10, r1=8, r2=8,
                                      segments=32), parent=fil)
    # the top rim's first facet edge
    from khervecad import mesh
    edges = fillet.crease_edges(mesh.tessellate(cyl, {}))
    top = next(e for e in edges if abs(e.a[2] - 10) < 1e-6
               and abs(e.b[2] - 10) < 1e-6)
    fil.params["edges"] = [list(top.a) + list(top.b)]
    env = doc_env(m)
    first = fillet.baked(fil, env)
    assert not first["missing"]
    _forget_coordinates(fil)
    m.set_param(cyl, "height", 25)          # the rim is now 15 mm higher
    got = fillet.baked(fil, env)
    assert not got["missing"] and got["cuts"]


def test_the_users_rib_of_sketch_lines_keeps_its_round(app):
    """The user's part: a rib drawn as three sketch LINES in a Regions
    on the Front plane, its sloped face rounded; its 25 mm dimension made
    35. The slope is named after the line that swept it (a band: the
    outline runs along its edge, not its centre)."""
    from pathlib import Path
    from khervecad import scadparse
    from khervecad import sketch_constraints as sc
    m = DocumentModel()
    scadparse.import_scad(m, str(Path(__file__).parent / "data" /
                                 "rib_on_block.scad"))
    fil = next(n for n in m.root.walk() if n.type == "fillet")
    reg = next(n for n in m.root.walk() if n.type == "regions")
    env = doc_env(m)
    assert not fillet.baked(fil, env)["missing"]
    (name,), = fil.params[fillet.NAMES].values()
    assert name.endswith("/1.l")             # the sloped line
    _forget_coordinates(fil)
    i = next(k for k, r in enumerate(sc.rows(reg)) if r.get("value") == 25)
    sc.set_value(m, reg, i, 35.0)
    got = fillet.baked(fil, env)
    assert not got["missing"]
    assert got["cuts"] or got["adds"]


def _bracket():
    """The user's bracket (Object 3): base with an upright, a rib of
    sketch lines fused to both, its slope rounded, chamfers round it."""
    import json
    from pathlib import Path
    from khervecad import document
    m = DocumentModel()
    m.root.add(document.node_from_dict(json.load(open(
        Path(__file__).parent / "data" / "rib_bracket_object.json"))))
    rib = [n for n in m.root.walk() if n.type == "fillet"
           and n.params.get("faces")][0]
    return m, rib


def _box(body):
    pts = [v for t in body for v in t]
    return [(min(p[i] for p in pts), max(p[i] for p in pts))
            for i in range(3)]


def test_a_fused_rib_runs_into_the_wall_and_the_base(app):
    """2026-11-10, the user: the rib's rounding stood up the wrong way at
    its foot and left a lip at the wall. The fused area stopped 0.05 mm
    short of both (the outline is grown) with mitred spikes above the
    slope; now its slope runs on, one face, into them."""
    from khervecad import mesh
    m, rib = _bracket()
    env = doc_env(m)
    src = fillet._merged(mesh._children_mesh(rib, env, None, frozenset(),
                                             False))
    names = face_names.names(rib, env, src)
    got = fillet.baked(rib, env)
    assert not got["missing"]
    # nothing between the slope's foot and the base but the base itself:
    # every crease of the slope's face meets a named face of a feature
    (slope,), = rib.params[fillet.NAMES].values()
    for e in fillet.crease_edges(src):
        if slope in (names[e.il], names[e.ir]):
            other = names[e.ir] if names[e.il] == slope else names[e.il]
            assert other is not None, e.mid
    # no cutter reaches into the base (top z = 10) or the upright (x = -20)
    for body in got["cuts"]:
        (x0, _x1), _y, (z0, _z1) = _box(body)
        assert z0 > 10 - 1e-3 and x0 > -20 - 1e-3, _box(body)

"""skin.py: a smooth body round a stick skeleton, posed before it is
grown; the round cone distance; code round trip.

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

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import armature, bake, mesh, scadparse, skin
from khervecad.model import DocumentModel, validate

ARM = [[0, 0, 0, 10, -1], [0, 0, 40, 5, 0], [30, 0, 40, 4, 1]]


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_the_round_cone_distance():
    pts = np.array([[0, 0, -10.0], [0, 0, 50.0], [10.0, 0, 0], [5, 0, 20]])
    d = skin.round_cone(pts, [0, 0, 0], [0, 0, 40], 10, 5)
    assert d[0] == pytest.approx(0.0, abs=1e-9)        # below the base
    assert d[1] == pytest.approx(5.0, abs=1e-9)        # above the tip
    assert d[2] == pytest.approx(0.0, abs=0.1)         # on the side
    assert d[3] < 0                                    # inside


def test_a_skeleton_grows_one_closed_body(app):
    doc = DocumentModel()
    node = doc.add_node("skin")
    node.params["nodes"] = [list(r) for r in ARM]
    assert node.id not in validate(doc.root)
    tris = mesh.tessellate(doc.root)
    points, faces = bake.to_polyhedron(tris)
    assert bake._check_polyhedron(dict(points=points, faces=faces)) is None
    a = np.asarray(tris).reshape(-1, 3)
    assert a[:, 0].max() == pytest.approx(34.0, abs=1.5)
    assert a[:, 2].min() == pytest.approx(-10.0, abs=1.5)


def test_a_pose_regrows_the_body_round_the_bent_skeleton(app):
    pts = skin.posed(ARM, [[1, 0, 90, 0]])
    assert pts[2] == pytest.approx([0, 0, 10], abs=1e-6)   # swung down
    assert pts[1] == pytest.approx([0, 0, 40])            # the joint stays
    doc = DocumentModel()
    node = doc.add_node("skin")
    node.params.update(nodes=[list(r) for r in ARM], pose=[[1, 0, 90, 0]])
    a = np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)
    assert a[:, 0].max() < 15.0


def test_round_trip_validation_and_the_armature_link(app):
    doc = DocumentModel()
    node = doc.add_node("skin")
    node.params.update(nodes=[list(r) for r in ARM], pose=[[1, 0, 30, 0]],
                       smooth=4.0, detail=60)
    root, warnings = scadparse.parse_scad(doc.to_scad())
    assert not warnings
    back = next(n for n in root.walk() if n.type == "skin")
    assert back.params["nodes"] == [[float(v) for v in r] for r in ARM]
    assert back.params["pose"] == [[1.0, 0.0, 30.0, 0.0]]
    assert back.params["detail"] == 60
    node.params["nodes"] = [[0, 0, 0, 5, 1], [0, 0, 1, 5, 0]]
    assert "ancestor" in validate(doc.root)[node.id]
    node.params["nodes"] = [[0, 0, 0, 0, -1]]
    assert "radius" in validate(doc.root)[node.id]
    rows = armature.bones_from_skin(ARM)
    assert [r[0] for r in rows] == ["b1", "b2"] and rows[1][1] == "b1"


def test_skin_is_a_primitive_with_a_tip(app):
    from khervecad import toolbars, tooltips
    assert "skin" in toolbars.PRIMITIVES
    assert "Skin" in tooltips.TIPS["skin"][0]

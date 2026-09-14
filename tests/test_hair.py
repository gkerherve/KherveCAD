"""The hair cap: a closed curly skin grown over selected faces.

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

from khervecad import document, hair, mesh, scadparse
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    edges = Counter()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    return all(edges[(v, u)] == n for (u, v), n in edges.items())


def _volume(tris) -> float:
    total = 0.0
    for a, b, c in tris:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return total / 6.0


def _sphere():
    root = CadNode("root", "root")
    root.add(CadNode("sphere", "s", dict(radius=50.0, segments=32)))
    return mesh.tessellate(root)


def test_the_cap_is_closed_lifted_and_keeps_the_face_clear():
    tris = _sphere()
    cap = hair.cap(tris, thickness=10.0, noise=0.0, clear="-y",
                   clear_angle=60.0)
    assert cap and _closed(cap)
    assert _volume(cap) > 0
    # nothing of the cap over the face: faces looking within 60° of -y
    # are skipped, so the cap stops well short of the sphere's front
    assert min(v[1] for t in cap for v in t) > -40
    # the top rises by the thickness
    assert max(v[2] for t in cap for v in t) == pytest.approx(60, abs=0.5)
    # curls: bumps push the skin in and out around the thickness
    curly = hair.cap(tris, thickness=10.0, noise=5.0, curl=20.0, seed=3,
                     clear="-y")
    tops = [v[2] for t in curly for v in t if v[2] > 55]
    assert max(tops) > 60.3 and min(tops) < 59.7 and _closed(curly)
    other = hair.cap(tris, thickness=10.0, noise=5.0, curl=20.0, seed=4,
                     clear="-y")
    assert other != curly
    # a box keeps the cap to the crown
    crown = hair.cap(tris, 10.0, 0.0, within=[[-60, -60, 20], [60, 60, 60]])
    assert _closed(crown) and min(v[2] for t in crown for v in t) > 15
    assert hair.cap([], 10.0) == [] and hair.cap(tris, 0.0) == []


def test_the_bump_field_is_smooth_bounded_and_seeded():
    values = [hair.bumps((x, 0.0, 0.0), 20.0, 1) for x in range(0, 40)]
    assert all(-1.0 <= v <= 1.0 for v in values)
    assert max(abs(a - b) for a, b in zip(values, values[1:])) < 0.5
    assert hair.bumps((3, 4, 5), 20.0, 1) != hair.bumps((3, 4, 5), 20.0, 2)
    assert hair.bumps((3, 4, 5), 0.0, 1) == 0.0


def test_the_hair_cap_node_bakes_validates_and_round_trips(app, tmp_path):
    doc = DocumentModel()
    head = doc.add_node("sphere", dict(radius=50.0))
    node = doc.wrap_nodes([head], "hair_cap")
    node.params.update(thickness=8.0, noise=3.0, clear="-y")
    assert node.id not in validate(doc.root)
    tris = mesh.tessellate(doc.root)
    assert max(v[2] for t in tris for v in t) > 55
    code = doc.to_scad()
    assert ('kcad_hair_cap(thickness = 8, noise = 3, curl = 25, seed = 1, '
            'within = [], clear = "-y", clear_angle = 60,') in code
    path = tmp_path / "hair.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["clear"] = "sideways"
    assert "clear" in validate(doc.root)[node.id]
    node.params["clear"] = "-y"
    node.params["within"] = [[1, 2, 3]]
    assert "two corners" in validate(doc.root)[node.id]
    from khervecad import toolbars, tooltips
    assert "hair_cap" in dict(toolbars.OPERATION_GROUPS)["character"]
    assert "Hair" in tooltips.TIPS["hair_cap"][0]

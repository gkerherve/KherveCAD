# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""An On Edge relation is adopted only by a section edge ALONG it
(2026-11-22, Exercise 010's tilted tube: the tube's centreline started
on the dome's axis, drawn On the axis guide; leaving the sketch gave it
a 0.0002 in sliver of the arm's section lying across the axis for
owner — a nearly level edge — and the revolve then pulled the point up
onto that level: the 6 degree sketch swung over into a cone)."""

from khervecad import plane_refs, sketch_constraints as sc


class _Node:
    def __init__(self, k):
        self.params = {"feature_order": k}


class _Box:
    def __init__(self, rows):
        self.params = {sc.KEY: rows}
        self.id = 1


def _adopt(monkeypatch, rows, segs):
    node = _Node(11)
    monkeypatch.setattr(plane_refs, "_candidates", lambda w, c: [node])
    monkeypatch.setattr(plane_refs, "_frame", lambda w, c: None)
    monkeypatch.setattr(plane_refs, "section", lambda w, c, n, f=None: segs)
    monkeypatch.setattr(plane_refs, "_remember", lambda *a: None)
    box = _Box(rows)
    return plane_refs.adopt(None, box), box


def test_a_sliver_across_the_axis_is_not_the_axis(monkeypatch):
    rows = [{"kind": "on_edge", "refs": ["0.p1"],
             "edge": [0.0, 3.35, 0.0, 0.0]}]
    sliver = ((-0.001218, 2.574992), (-0.001, 2.575))
    n, box = _adopt(monkeypatch, rows, [sliver])
    row = sc.rows(box)[0]
    assert n == 0
    assert row["edge"] == [0.0, 3.35, 0.0, 0.0]
    assert "owner" not in row


def test_an_edge_along_it_is_still_adopted(monkeypatch):
    rows = [{"kind": "on_edge", "refs": ["0.p1"],
             "edge": [1.35, 0.0, 1.35, 2.0]}]
    wall = ((1.35, 0.0), (1.35, 2.0))
    n, box = _adopt(monkeypatch, rows, [wall])
    assert n == 1 and sc.rows(box)[0]["owner"] == 11

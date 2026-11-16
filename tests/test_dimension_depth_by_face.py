# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""A Smart Dimension click on the face an extrude ends on types the
extrude's depth (2026-11-16, the user: "when extruding boss or cut, we
cannot add a smart dimension to those extrusion")."""
import pytest

from test_stacked_features import app, win  # noqa


def test_smart_dimension_on_the_extrudes_end_face_types_the_depth(
        win, monkeypatch):
    from khervecad import face_dim
    from test_dimension_while_extruding import _extruding, _smart_dimension
    part, ext = _extruding(win)
    tool = _smart_dimension(win)
    monkeypatch.setattr(tool, "model_face", lambda x, y: dict(
        pos=[0, 0, 0], dir=[0, 0, 1], tris=[]))
    monkeypatch.setattr(face_dim, "sketch_line", lambda t, f: None)
    monkeypatch.setattr(face_dim, "reference", lambda t, p, f: None)
    hit, used = tool._face_pick(300, 300, tool._working_on())
    assert hit is None and used
    box = win.view3d._dim3d_editor
    assert box is not None
    box.setText("17")
    box._done()
    assert ext.params["height"] == pytest.approx(17)

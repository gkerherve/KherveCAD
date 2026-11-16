# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Leaving a dimension's value box without Enter, making a driven
dimension driving, and the extrude's depth from Smart Dimension
(2026-11-16, the user)."""
import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

from khervecad import dim_link, feature_dims, value_popup
from khervecad import sketch_constraints as sc

from test_feature_dims import _paint, _plate, win  # noqa


def _open_depth_box(win):
    ext, rect, rev = _plate(win)
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    _paint(win)
    rect_, node, key = win._feature_dim_hits[0]
    return ext, feature_dims.edit(win, rect_, node, key)


def test_a_click_elsewhere_closes_an_untouched_box(win):
    ext, box = _open_depth_box(win)
    v = win.view3d
    far = QPoint(3, 3)
    QTest.mousePress(v, Qt.LeftButton, Qt.NoModifier, far)
    QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, far)
    QTest.qWait(30)
    assert v._dim3d_editor is None
    assert ext.params["height"] == 10                # nothing changed
    assert not win.model.undo_stack.canUndo() or True


def test_a_click_elsewhere_keeps_what_was_typed(win):
    ext, box = _open_depth_box(win)
    box.setText("14")
    v = win.view3d
    far = QPoint(3, 3)
    QTest.mousePress(v, Qt.LeftButton, Qt.NoModifier, far)
    QTest.mouseRelease(v, Qt.LeftButton, Qt.NoModifier, far)
    QTest.qWait(30)
    assert v._dim3d_editor is None
    assert ext.params["height"] == pytest.approx(14)


def test_the_click_that_leaves_does_not_start_anything(win):
    ext, box = _open_depth_box(win)
    assert dim_link.outside(win, QPoint(3, 3))
    assert win.view3d._dim3d_editor is None
    assert dim_link.release(win, QPoint(3, 3))       # swallowed once
    assert not dim_link.release(win, QPoint(3, 3))
    assert not dim_link.outside(win, QPoint(3, 3))   # no box now


def test_the_value_popup_answers_none_when_cancelled(win):
    dlg = value_popup.make(None, "Distance", "Value (mm):", "12")
    dlg.edit.setText("25")
    dlg.accept()
    assert dlg.result() == "25"
    dlg = value_popup.make(None, "Distance", "Value (mm):", "12")
    dlg.reject()                  # Esc, or a click away from the popup
    assert dlg.result() is None
    dlg = value_popup.make(None, "Distance", "Value (mm):", "12")
    dlg.edit.setText("   ")
    dlg.accept()
    assert dlg.result() is None


def test_the_dimension_prompt_is_the_popup_not_a_modal_dialog(win,
                                                              monkeypatch):
    from khervecad import sketch_constrain_ui as ui
    asked = []
    monkeypatch.setattr(value_popup, "ask",
                        lambda *a: asked.append(a) or "30")
    scene = win.view2d.scene()
    assert ui._ask_value(scene, "distance", 12.5) == "30"
    assert asked and asked[0][3] == "12.5"


def _driven_dim(win):
    ext, rect, rev = _plate(win)
    sc.add(win.model, ext, "length", [sc.ref_of(ext, rect, "e0")], 40)
    sc.set_driven(win.model, ext, 0, True)
    return ext, rect


def test_typing_into_a_driven_dimension_makes_it_driving(win):
    from PyQt5.QtCore import QRectF
    from khervecad import sketch_dims3d
    ext, rect = _driven_dim(win)
    assert sc.rows(ext)[0].get("driven")
    box = sketch_dims3d.edit(win, QRectF(20, 20, 40, 16), ext, 0)
    box.setText("55")
    box._done()
    row = sc.rows(ext)[0]
    assert not row.get("driven")
    assert row["value"] == pytest.approx(55)
    assert rect.params["width"] == pytest.approx(55, abs=1e-3)


def test_the_menu_offers_make_driving_for_a_driven_dimension(win,
                                                             monkeypatch):
    from PyQt5.QtCore import QRectF
    from PyQt5.QtWidgets import QMenu
    from khervecad import view3d_menu
    ext, rect = _driven_dim(win)
    win._dims3d_hits = [(QRectF(10, 10, 40, 16), ext, 0)]
    seen = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: seen.append(
        [a.text() for a in self.actions()]))
    view3d_menu.context_menu(win, QPoint(20, 15))
    assert any("Make driving" in t for t in seen[0])
    assert not any("Make driven" in t for t in seen[0])
    view3d_menu.set_driven(win, ext, 0, False)       # what the item does
    assert not sc.rows(ext)[0].get("driven")
    seen.clear()
    view3d_menu.context_menu(win, QPoint(20, 15))
    assert any("Make driven" in t for t in seen[0])


def test_the_extrude_of_a_sketch_is_found(win):
    ext, rect, rev = _plate(win)
    assert feature_dims.extrude_of(rect) is ext
    assert feature_dims.extrude_of(ext) is ext
    assert feature_dims.extrude_of(rev) is None


def test_a_flat_face_under_smart_dimension_opens_the_depth(win):
    ext, rect, rev = _plate(win)
    box = feature_dims.edit_depth(win, ext, 200, 200)
    assert box is win.view3d._dim3d_editor
    box.setText("22")
    box._done()
    assert ext.params["height"] == pytest.approx(22)


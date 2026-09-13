"""Every Blueprint tool, end to end, the way a user drives it: real
mouse events on the sheet to make the item, then select it, edit every
field in Properties through the editor widgets themselves, double-click
it, drag it, delete it with the keyboard, undo and redo — with an
exception collector installed, because an error inside a Qt callback
used to abort the whole application.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox,
                             QDoubleSpinBox, QFormLayout, QLineEdit,
                             QPlainTextEdit, QSpinBox)

from khervecad import blueprint, document
from khervecad import blueprint_items as bi
from khervecad.model import DocumentModel

PART = """
cube([80, 50, 10]);
translate([0, 0, 10]) cube([10, 50, 40]);
translate([45, 25, 10]) cylinder(h=20, r=9, $fn=48);
translate([20, 12, 10]) cylinder(h=6, r=3, $fn=32);
translate([70, 12, 10]) cylinder(h=6, r=3, $fn=32);
translate([70, 38, 10]) cylinder(h=6, r=3, $fn=32);
"""

#: how each tool is driven: (view, u, v) clicks — F front, T top, or S
#: a point on the bare paper (sheet mm)
PLANS = {
    "dim_smart": [("F", 0, 0), ("F", 80, 0), ("F", 40, -30)],
    "dim_horizontal": [("F", 0, 0), ("F", 80, 50), ("F", 40, -30)],
    "dim_vertical": [("F", 0, 0), ("F", 80, 50), ("F", 110, 25)],
    "dim_aligned": [("F", 0, 0), ("F", 80, 50), ("F", 60, 70)],
    "dim_diameter": [("T", 45, 34), ("T", 75, 60)],
    "dim_radius": [("T", 45, 34), ("T", 75, 60)],
    "dim_angle": [("F", 40, 0), ("F", 0, 30), ("F", 15, 15)],
    "leader": [("F", 80, 5), ("F", 95, 20)],
    "balloon": [("F", 80, 5), ("F", 95, 20)],
    "datum": [("F", 40, 0), ("F", 40, -15)],
    "fcf": [("F", 80, 30), ("F", 100, 45)],
    "finish": [("F", 40, 10)],
    "centre_mark": [("T", 20, 15)],
    "centre_line": [("F", 45, 10), ("F", 45, 30)],
    "text": [("S", 30, 24)],
    "sketch_line": [("S", 25, 40), ("S", 60, 45)],
    "sketch_rect": [("S", 25, 40), ("S", 60, 55)],
    "sketch_circle": [("S", 40, 50), ("S", 46, 50)],
    "detail": [("F", 45, 20), ("F", 57, 20)],
}


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def errors():
    """Exceptions raised inside Qt callbacks (PyQt hands them to
    sys.excepthook; without one it aborts the process)."""
    caught = []
    saved = sys.excepthook
    sys.excepthook = lambda k, v, tb: caught.append(
        "".join(traceback.format_exception(k, v, tb)))
    yield caught
    sys.excepthook = saved


@pytest.fixture
def bp(app, errors, monkeypatch):
    from khervecad import scadparse
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1000, 700)
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad(PART)
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    board = blueprint.open_blueprint(win)
    board.resize(1400, 900)
    board.sheet.resetTransform()
    board.sheet.scale(4.0, 4.0)
    monkeypatch.setattr(board, "ask_text", lambda *a, **k: "EDITED")
    monkeypatch.setattr(board, "ask_choice", lambda *a, **k: "Ra 1.6")
    monkeypatch.setattr(board, "ask_fcf", lambda: {
        "symbol": "perpendicularity", "tolerance": "0.02", "datums": "A"})
    yield board
    board.close()
    win._dirty = False
    win.close()


# ── driving the sheet like a user ────────────────────────────────────

def _scene_point(bp, where, u, v):
    if where == "S":
        return QPointF(u, v)
    view = bp.scene.projected({"F": "Front", "T": "Top"}[where])
    return view.mapToScene(QPointF(*view.to_local((u, v))))


def _mouse(bp, kind, pos, buttons=Qt.NoButton):
    """A mouse event on the sheet at scene point *pos*. The screen
    position must be the real one: QGraphicsScene finds the item under
    the click from it, and the short QMouseEvent constructor fills it
    with wherever the cursor happens to be."""
    view = bp.sheet
    viewport = view.viewport()
    at = QPointF(view.mapFromScene(pos))
    window = QPointF(viewport.mapTo(viewport.window(), at.toPoint()))
    screen = QPointF(viewport.mapToGlobal(at.toPoint()))
    etype = {"press": QEvent.MouseButtonPress, "move": QEvent.MouseMove,
             "release": QEvent.MouseButtonRelease,
             "double": QEvent.MouseButtonDblClick}[kind]
    button = Qt.NoButton if kind == "move" else Qt.LeftButton
    held = Qt.LeftButton if kind in ("press", "double") else buttons
    QApplication.sendEvent(viewport, QMouseEvent(
        etype, at, window, screen, button, held, Qt.NoModifier))


def _click(bp, pos):
    _mouse(bp, "move", pos)
    _mouse(bp, "press", pos)
    _mouse(bp, "release", pos)


def _drag(bp, start, end):
    _mouse(bp, "press", start)
    mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
    for p in (mid, end):
        _mouse(bp, "move", p, Qt.LeftButton)
    _mouse(bp, "release", end)


def _key(bp, key):
    for kind in (QEvent.KeyPress, QEvent.KeyRelease):
        QApplication.sendEvent(bp.sheet, QKeyEvent(kind, key, Qt.NoModifier))


def _grab_point(item):
    """A sheet point on the item itself: the middle of a view's drawing,
    the middle of a note's first line, or its text's box."""
    if isinstance(item, bi.ViewItem):
        return item.mapToScene(item.content_rect().center())
    for p in item.prims:
        if p[0] == "line":
            (ax, ay), (bx, by) = p[2], p[3]
            return item.mapToScene(QPointF((ax + bx) / 2, (ay + by) / 2))
    rect = item.shape().boundingRect()
    return item.mapToScene(rect.center())


def _everything(bp):
    return list(bp.scene.views.values()) + bp.scene.notes()


def _edit_every_field(bp):
    """Change each editor Properties shows, the way typing would."""
    form = bp.panel.form
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.FieldRole)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QComboBox):
            if widget.isEditable():
                widget.setCurrentText("Steel")
                widget.lineEdit().editingFinished.emit()
            else:
                widget.setCurrentIndex(widget.count() - 1)
        elif isinstance(widget, QLineEdit):
            widget.setText(widget.text() + "1")
            widget.editingFinished.emit()
        elif isinstance(widget, QPlainTextEdit):
            widget.setPlainText(widget.toPlainText() + "\nMORE")
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            widget.setValue(min(widget.value() + 1, widget.maximum()))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(not widget.isChecked())
    bp.panel._flush()


def _saved(bp):
    return bp.model.drawing


# ── each tool ────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", list(PLANS))
def test_each_tool_adds_edits_moves_deletes_and_undoes(bp, errors, key):
    before = _everything(bp)
    bp.set_tool(key)
    for where, u, v in PLANS[key]:
        _click(bp, _scene_point(bp, where, u, v))
    bp.set_tool("select")
    added = [i for i in _everything(bp) if i not in before]
    assert len(added) == 1, (key, errors)
    item = added[0]
    notes, views = len(_saved(bp)["notes"]), len(_saved(bp)["views"])

    # Properties: every field, through its editor
    bp.scene.clearSelection()
    item.setSelected(True)
    assert bp.panel.item is item
    _edit_every_field(bp)
    assert item in _everything(bp)
    # double-click edits text straight away
    _mouse(bp, "double", _grab_point(item))
    # drag it by itself
    start = _grab_point(item)
    _drag(bp, start, QPointF(start.x() + 6.0, start.y() + 4.0))
    # the edits are in the document
    assert (len(_saved(bp)["notes"]), len(_saved(bp)["views"])) == \
        (notes, views)

    # delete with the keyboard
    bp.scene.clearSelection()
    item.setSelected(True)
    _key(bp, Qt.Key_Delete)
    assert item not in _everything(bp)
    assert len(_saved(bp)["notes"]) + len(_saved(bp)["views"]) == \
        notes + views - 1 - (len(item.childItems()) and 0)
    bp.undo_stack.undo()
    assert len(_everything(bp)) == len(before) + 1
    bp.undo_stack.redo()
    assert len(_everything(bp)) == len(before)
    bp.undo_stack.undo()
    assert len(_everything(bp)) == len(before) + 1
    assert errors == [], errors[0] if errors else ""


def test_views_title_block_and_parts_list_edit_and_delete(bp, errors):
    for make in (lambda: bp.add_projected("Left"),
                 lambda: bp.add_section("x"), bp.add_shaded):
        view = make()
        bp.scene.clearSelection()
        view.setSelected(True)
        _edit_every_field(bp)
        start = view.mapToScene(view.content_rect().center())
        _drag(bp, start, QPointF(start.x() + 5, start.y() + 5))
        bp.scene.clearSelection()
        view.setSelected(True)
        _key(bp, Qt.Key_Delete)
        assert view not in bp.scene.views.values()
        bp.undo_stack.undo()
    bp.add_bom()
    (bom,) = [n for n in bp.scene.notes() if n.KIND == "bom"]
    bom.setSelected(True)
    _edit_every_field(bp)
    bp.edit_title()
    assert bp.panel.item is bp.scene.title
    _edit_every_field(bp)
    assert bp.scene.fields["material"] == "Steel"
    assert _saved(bp)["fields"]["material"] == "Steel"
    assert errors == [], errors[0] if errors else ""


def test_undo_with_an_unfinished_edit_does_not_break(bp, errors):
    front = bp.scene.projected("Front")
    note = bp.add_note({"type": "leader", "tip": [80.0, 5.0],
                        "text": "FIRST"}, front)
    note.setSelected(True)
    editor = next(bp.panel.form.itemAt(r, QFormLayout.FieldRole).widget()
                  for r in range(bp.panel.form.rowCount())
                  if isinstance(bp.panel.form.itemAt(
                      r, QFormLayout.FieldRole).widget(), QPlainTextEdit))
    editor.setPlainText("TYPED")                  # still pending
    steps = bp.undo_stack.count()
    bp.undo_stack.undo()
    assert bp.undo_stack.count() == steps         # nothing pushed mid-undo
    bp.undo_stack.redo()
    assert errors == [], errors[0] if errors else ""


def test_undo_in_the_middle_of_a_tool(bp, errors):
    bp.add_note({"type": "text", "text": "UNDO ME", "x": 30.0, "y": 24.0},
                None)                              # a step to undo
    bp.set_tool("dim_smart")
    _click(bp, _scene_point(bp, "F", 0, 0))
    _click(bp, _scene_point(bp, "F", 80, 0))     # the preview is out
    bp.undo_stack.undo()                          # the sheet is rebuilt
    assert bp.tool.preview is None                # and the tool starts over
    count = len(bp.scene.notes())
    _click(bp, _scene_point(bp, "F", 40, -30))    # off the views: nothing
    assert len(bp.scene.notes()) == count
    for where, u, v in PLANS["dim_smart"]:
        _click(bp, _scene_point(bp, where, u, v))
    assert len(bp.scene.notes()) == count + 1
    assert all(n.scene() is bp.scene for n in bp.scene.notes())
    assert errors == [], errors[0] if errors else ""


def test_every_action_on_the_bars_and_menus(bp, errors, monkeypatch,
                                            tmp_path):
    from PyQt5.QtWidgets import QFileDialog, QMessageBox
    from khervecad import blueprint_export
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(tmp_path / "out"), ""))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(blueprint_export, "print_sheet",
                        lambda *a, **k: True)
    actions = []
    for menu_action in bp.menuBar().actions():
        menu = menu_action.menu()
        for act in menu.actions():
            actions += act.menu().actions() if act.menu() else [act]
    for act in actions:
        if act.isSeparator() or act.text() == "&Close":
            continue
        act.trigger()
        bp.set_tool("select")
    for index in range(bp.sheet_combo.count()):
        bp.sheet_combo.setCurrentIndex(index)
        bp._sheet_chosen(index)
    for index in range(bp.scale_combo.count()):
        bp.scale_combo.setCurrentIndex(index)
        bp._scale_chosen(index)
    bp.hidden_act.trigger()
    bp.sheet.zoom(60.0)
    bp.sheet.grab()                              # paint at full zoom
    assert errors == [], errors[0] if errors else ""


def test_clicking_a_label_selects_it_and_delete_removes_it(bp, errors):
    """The click area used to be the outline of the text box only: a
    click on a dimension's number or a note's words hit nothing."""
    front = bp.scene.projected("Front")
    dim = bp.add_note({"type": "dim", "kind": "horizontal", "a": [0, 0],
                       "b": [80, 0], "offset": 25.0}, front)
    note = bp.add_note({"type": "leader", "tip": [80.0, 5.0],
                        "at": [15.0, -12.0], "text": "BREAK EDGES"}, front)
    for item in (dim, note):
        label = next(p for p in item.prims if p[0] == "text")
        centre = item.mapToScene(bi.placed_text(label).boundingRect()
                                 .center())
        bp.scene.clearSelection()
        _click(bp, centre)
        assert bp.scene.selectedItems() == [item], item.TITLE
        _key(bp, Qt.Key_Delete)
        assert item not in bp.scene.notes()
    assert errors == [], errors[0] if errors else ""


# ── nothing lost ─────────────────────────────────────────────────────

def test_everything_on_the_sheet_survives_save_and_open(bp, errors,
                                                        tmp_path):
    for key, plan in PLANS.items():
        bp.set_tool(key)
        for where, u, v in plan:
            _click(bp, _scene_point(bp, where, u, v))
    bp.set_tool("select")
    bp.add_section("y")
    bp.add_shaded()
    bp.add_bom()
    bp.set_field(bp.scene.title, "company", "Kherve Labs")
    bp.style_combo.setCurrentIndex(bp.style_combo.findData("blueprint"))
    bp._style_chosen(0)
    text = next(n for n in bp.scene.notes() if n.KIND == "text")
    was = text.pos()
    start = _grab_point(text)
    _drag(bp, start, QPointF(start.x() + 12, start.y() + 7))   # moved
    assert text.pos() != was
    state = bp.scene.state()
    assert _saved(bp) == state                   # every change committed
    kinds = {n["type"] for n in state["notes"]}
    assert kinds >= {"dim", "leader", "balloon", "datum", "fcf", "finish",
                     "centre_mark", "centre_line", "text", "sketch", "bom"}
    path = tmp_path / "part.kcad"
    document.save_kcad(bp.model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    assert other.drawing == state
    # and a sheet rebuilt from the file writes the same state back
    scene = blueprint.BlueprintScene()
    scene.geometry = bp.scene.geometry
    scene.load_state(other.drawing)
    assert scene.state() == state
    assert errors == [], errors[0] if errors else ""


def test_closing_the_window_keeps_an_unfinished_edit(bp, errors):
    note = bp.add_note({"type": "text", "text": "OLD", "x": 40, "y": 40},
                       None)
    note.setSelected(True)
    editor = next(bp.panel.form.itemAt(r, QFormLayout.FieldRole).widget()
                  for r in range(bp.panel.form.rowCount())
                  if isinstance(bp.panel.form.itemAt(
                      r, QFormLayout.FieldRole).widget(), QPlainTextEdit))
    editor.setPlainText("NEW")                   # typed, not yet applied
    bp.close()
    texts = [n.get("text") for n in _saved(bp)["notes"]
             if n["type"] == "text"]
    assert "NEW" in texts
    assert bp.main._dirty
    assert errors == [], errors[0] if errors else ""

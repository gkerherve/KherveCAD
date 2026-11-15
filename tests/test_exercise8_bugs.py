"""Bugs found while filming Exercise 8 (clevis), 2026-11-15 — each one
driven with real mouse events.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAbstractButton

from khervecad import analysis, choice_preview, mesh, sketch_mode
from test_lever_by_mouse import (_button_for, _extruded_boss, _wait,  # noqa
                                 win)
from test_clevis_by_mouse import (_circle, _click_areas, _frame,  # noqa
                                  _sketch_of, _tab, _window_ok, _ids)


@pytest.fixture(autouse=True)
def _plane_rows():
    """The tests' default hides the Origin / plane rows; these use them."""
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", True)
    yield


def _new_object(win):
    nb = next(b for b in win.findChildren(QAbstractButton)
              if b.isVisible() and b.text().strip() == "New Object")
    QTest.mouseClick(nb, Qt.LeftButton)
    QTest.qWait(150)


def _row_sketch(win, row):
    """Sketch tab, a Front / Top / Right Plane tree row selected, Sketch."""
    _tab(win, "Sketch")
    tree = win.builder.active_tree()
    item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                if tree.topLevelItem(i).text(0) == row)
    QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier,
                     tree.visualItemRect(item).center())
    QTest.qWait(80)
    QTest.mouseClick(_button_for(win, sketch_mode.create_action(win)),
                     Qt.LeftButton)
    assert _wait(lambda: sketch_mode.sketching(win))
    QTest.qWait(500)


def _top_of(win, node):
    while node.parent is not None and node.parent is not win.model.root:
        node = node.parent
    return node


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))


# ------------------------------------------------ 2. Front Plane row in Main
def test_front_plane_row_in_main_makes_a_part_that_extrudes(win):
    """A sketch from the Front Plane row with no Object open left a
    "Front sketch" rotate at the Main level: Extruded Boss then found
    no regions. It becomes a part like a Top-plane sketch does."""
    before = _ids(win)
    _row_sketch(win, "Front Plane")
    _frame(win, -45, -8, 90, 100)
    _circle(win, (0, 40), 24)
    _circle(win, (0, 40), 11)
    sk = _sketch_of(win, before)
    assert sk.type == "rotate"
    assert _top_of(win, sk).type == "component", \
        "the sketch stayed loose at the Main level"
    assert win.builder.isolated_component() is not None
    _extruded_boss(win)
    sketches, items = choice_preview.region_items(win)
    assert items, "Extruded Boss finds no regions"
    _click_areas(win, sk, [(18, 40)])
    _window_ok(win, direction="symmetric", distance=40)
    v = _volume(win)
    assert v["size"][1] == pytest.approx(40, abs=0.1)
    assert v["volume"] > 0

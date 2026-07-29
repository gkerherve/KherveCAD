"""The Main tab is an assembly of single-row parts: geometry added or
imported there arrives wrapped in an Object, edited in the Object tab.

Run with: python -m pytest tests/  (offscreen Qt).

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

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


def test_primitive_in_main_becomes_an_object(window):
    """Insert a cube while Main is current: it lands as one visible
    Object row and the Object tab opens on it for editing."""
    window._add_primitive("cube")
    comps = window.model.components()
    assert len(comps) == 1 and comps[0].visible
    assert comps[0].children[0].type == "cube"
    assert window.builder.isolated_component() is comps[0]


def test_primitive_in_object_tab_stays_inside_it(window):
    comp = window.model.new_component("Part", visible=False)
    window.builder.open_component(comp)
    window._add_primitive("sphere")
    assert comp.children and comp.children[0].type == "sphere"
    assert window.model.components() == [comp]     # no extra Object


def test_drawn_shape_in_main_becomes_an_object(window):
    """A shape drawn in the Main 2D view wraps into a new Object and
    editing continues in the Object tab."""
    node = window.model.add_node("rect", dict(x=0, y=0, width=10,
                                              height=5))
    window.scene.node_created.emit(node)
    comps = window.model.components()
    assert len(comps) == 1
    assert node.parent is comps[0]
    assert window.builder.isolated_component() is comps[0]


def test_drawn_shape_in_object_tab_is_untouched(window):
    comp = window.model.new_component("Part", visible=False)
    window.builder.open_component(comp)
    node = window.model.add_node("circle", dict(radius=4), parent=comp)
    window.scene.node_created.emit(node)
    assert node.parent is comp
    assert window.model.components() == [comp]


def test_library_insert_is_one_part(window, app):
    """A part inserted from the library shows as a single Object row."""
    from khervecad.library import PartLibraryDialog
    dlg = PartLibraryDialog(window.model, window)
    dlg._insert()
    assert dlg.inserted is not None
    assert dlg.inserted.type == "component"
    assert dlg.inserted.parent is window.model.root
    assert dlg.inserted.visible


def test_scad_import_lands_as_one_part(window, tmp_path):
    p = tmp_path / "plate.scad"
    p.write_text("cube([10, 10, 5]);\ncylinder(h=8, r=3);\n",
                 encoding="utf-8")
    window.open_any(str(p))
    comps = window.model.components()
    assert len(comps) == 1
    assert comps[0].name == "plate"
    types = {n.type for n in comps[0].walk()}
    assert {"cube", "cylinder"} <= types

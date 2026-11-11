"""Properties ▸ For construction on every sketch shape, as SolidWorks'
Line / Circle properties (2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.model import DocumentModel
from khervecad.properties import PropertiesPanel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("kind", ["line", "circle", "rect", "polygon"])
def test_the_tick_makes_it_construction_and_back(app, kind):
    model = DocumentModel()
    node = model.add_node(kind, {})
    panel = PropertiesPanel(model)
    panel.set_node(node)
    box = panel._construction
    assert box is not None and not box.isChecked()
    box.setChecked(True)
    assert node.params.get("modifier") == "%"
    assert "%" in model.to_scad()
    box.setChecked(False)
    assert "modifier" not in node.params
    model.set_modifier(node, "%")           # switched elsewhere: it follows
    assert box.isChecked()


def test_solids_have_no_tick(app):
    model = DocumentModel()
    panel = PropertiesPanel(model)
    panel.set_node(model.add_node("cube", {}))
    assert panel._construction is None

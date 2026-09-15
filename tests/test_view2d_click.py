"""Clicking a part in the 2D view must not free the item Qt is still
delivering the press to (it segfaulted on a House Builder floor).

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
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad.model import CadNode, DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_clicking_a_part_that_rebuilds_the_scene_survives(app):
    from khervecad.view2d import SketchScene, SketchView
    model = DocumentModel()
    model.root.add(CadNode("cube", "Box", dict(width=20.0, depth=20.0,
                                               height=20.0, center=True)))
    scene = SketchScene(model)
    scene.rebuild()
    seen = []

    def selected(nodes):
        # what MainWindow._sync_highlight does: rebuild, freeing every item
        seen.append([n.name for n in nodes])
        scene.set_highlight(nodes)

    scene.selection_changed.connect(selected)
    view = SketchView(scene)
    view.resize(300, 300)
    view.show()
    QApplication.processEvents()
    view.centerOn(0, 0)
    QApplication.processEvents()
    at = view.mapFromScene(QPointF(3.0, 3.0))
    assert scene._part_items, "the cube should show as a part"
    try:
        QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, at)
        QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier, at)
        assert seen == []            # reported after the press, not inside
        QApplication.processEvents()
        assert seen and seen[0] == ["Box"]
    finally:
        view.close()

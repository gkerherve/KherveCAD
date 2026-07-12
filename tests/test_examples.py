"""Every Examples-menu entry must build a clean, valid document.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import examples, mesh, model
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_every_example_builds_and_validates(app):
    for label, category, build in examples.EXAMPLES:
        root = build()
        assert root.type == "root", label
        errors = model.validate(root)
        assert errors == {}, f"{label}: {list(errors.values())}"


def test_projects_cover_chapters_two_to_ten(app):
    labels = [lbl for lbl, cat, _b in examples.EXAMPLES
              if cat == "Projects"]
    assert len(labels) == 9                       # chapters 2..10
    for chapter in range(2, 11):
        assert any(lbl.startswith(f"Ch.{chapter} ") for lbl in labels)


def test_solid_projects_preview_in_the_builtin_mesh(app):
    """The projects that are meant to be solid produce triangles in the
    built-in tessellator (not only under the OpenSCAD engine)."""
    m = DocumentModel()
    for label, category, build in examples.EXAMPLES:
        if category != "Projects":
            continue
        m.root = build()
        tris = mesh.tessellate(m.root, fn=m.effective_fn())
        assert tris, f"{label} previewed empty"

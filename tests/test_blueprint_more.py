"""Revision table, ordinate dimensions, baseline / chain runs.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import blueprint, blueprint_more as bm, scadparse
from khervecad import blueprint_items as bi


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_helpers():
    assert bm.next_rev([]) == "A"
    assert bm.next_rev([["A"], ["B"]]) == "C"
    assert bm.next_rev([["3"]]) == "4"
    dims = bm.baseline([0, 0], [[80, 0], [10, 0]])
    assert [d["b"][0] for d in dims] == [10, 80]
    assert dims[1]["offset"] > dims[0]["offset"]
    chain = bm.chain([[30, 0], [0, 0], [80, 0]])
    assert [(d["a"][0], d["b"][0]) for d in chain] == [(0, 30), (30, 80)]
    assert "ordinate" in bi.NOTE_CLASSES and "revisions" in bi.NOTE_CLASSES


@pytest.fixture
def bp(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad("cube([80, 50, 10]);")
    win.model.root = root
    win.model.structure_changed.emit()
    board = blueprint.open_blueprint(win)
    yield board
    board.close()
    win._dirty = False
    win.close()


def test_revision_and_ordinate_on_a_sheet(bp):
    assert bp.add_revision("First issue", "GK") == "A"
    assert bp.add_revision("Hole moved") == "B"
    table = next(n for n in bp.scene.notes()
                 if isinstance(n, bm.RevisionItem))
    assert [r[0] for r in table.data["rows"]] == ["A", "B"]
    assert bp.scene.fields["revision"] == "B"
    front = bp.scene.projected("Front")
    item = bp.scene.add_note({"type": "ordinate", "axis": "horizontal",
                              "origin": [0, 0],
                              "points": [[20, 0], [80, 0]]}, front)
    assert item.values() == [20, 80]
    assert any(p[0] == "text" and p[3] == "80" for p in item.prims) or \
        any(p[0] == "text" and p[3].startswith("80") for p in item.prims)
    st = bp.scene.state()
    kinds = {n["type"] for n in st["notes"]}
    assert {"revisions", "ordinate"} <= kinds
    # the MCP side, on the same window (a second Blueprint window in
    # one test module crashed Qt offscreen)
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(bp.main)
    out = ex.execute("blueprint", dict(action="revision", text="Issued"))
    assert out.get("revision") == "C", out
    out = ex.execute("blueprint", dict(action="baseline", view="Front",
                                       points=[[0, 0], [40, 0], [80, 0]]))
    assert out.get("added") == 2, out

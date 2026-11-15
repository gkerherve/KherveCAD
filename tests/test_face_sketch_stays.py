"""A face sketch stays put when a fillet wraps the part (Exercise 49,
2026-11-15): wrapping the bracket in Fillet2 made the upright's back-face
sketch "follow" a round boss's facet whose normal was almost the face's,
and slid it 54 mm along the plate — the fillet then found none of its
edges.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _holes(win):
    return [float(n.params["x"]) for n in win.model.root.walk()
            if n.type == "circle"
            and abs(float(n.params.get("radius", 0)) - 22.225) < 1e-3]


def test_the_exercise_49_bracket_keeps_its_upright_under_fillets(app):
    import os
    path = os.path.join(os.path.dirname(__file__), "data",
                        "exercise49_bracket.kcad")
    from khervecad import toolbar_style
    win = MainWindow()
    win.resize(1500, 950)
    toolbar_style.apply(win, "SolidWorks", remember=False)
    win.show()
    try:
        ex = McpToolExecutor(win)
        ex.execute("open_document", dict(path=path))
        QApplication.processEvents()
        assert _holes(win) == [156.0, 156.0]
        top = [n for n in win.model.root.children if n.visible
               and n.type not in ("assign", "variables")][0]
        edges = ex.execute("list_edges", dict(node_id=top.id))["edges"]
        # Fillet2: every edge where the upright, ribs and ring meet the
        # plate's top
        pick = [e["index"] for e in edges if not e["convex"]
                and abs(e["centre"][2] - 19) < 0.5 and e["length"] > 3]
        out = ex.execute("fillet_edges", dict(node_id=top.id, radius=3,
                                              chains=pick))
        QApplication.processEvents()
        assert _holes(win) == pytest.approx([156.0, 156.0], abs=1e-6)
        from khervecad import fillet
        node = [n for n in win.model.root.walk() if n.type == "fillet"][0]
        from khervecad import anchors
        missing = fillet.baked(node, anchors.doc_env(win.model))["missing"]
        # only tessellation chords inside the ring may go missing; every
        # real junction (upright, gussets, rib) is found
        for m in missing:
            mid = [(m[i] + m[i + 3]) / 2 for i in range(3)]
            assert mid[0] ** 2 + mid[1] ** 2 < 40 ** 2, (m, out)
    finally:
        toolbar_style.apply(win, "KherveCAD", remember=False)
        win._dirty = False
        win.close()


def test_a_round_boss_on_the_face_does_not_drag_the_sketch(app):
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        ex.execute("apply_code", {"code": "translate([-220, -100, 0]) "
                                  "cube([200, 39, 19]); // Plate\n"})
        QApplication.processEvents()
        # the plate's back face (y = -61), a round boss standing out of it
        s = ex.execute("reference_geometry", dict(
            action="sketch", origin=[0, -61, 0], normal=[0, 1, 0]))
        sid = s["sketch_id"]
        c = ex.execute("add_node", dict(type="circle", parent_id=sid,
                       params=dict(x=120, y=9.5, radius=8)))["created"]
        r = ex.execute("sketch_feature", dict(node_id=sid, depth=30))
        assert "error" not in r, r
        QApplication.processEvents()
        top = [n for n in win.model.root.children if n.visible
               and n.type not in ("assign", "variables")]
        part = win.model.wrap_nodes(top, "union")
        QApplication.processEvents()
        out = ex.execute("fillet_edges", dict(node_id=part.id, radius=1,
                                              chains=[0]))
        QApplication.processEvents()
        assert "error" not in out, (out.get("error"), [n for n in win.model.root.walk() if n.type == "fillet"][0].params.get("edges"))
        circle = win.model.find(c)
        assert float(circle.params["x"]) == pytest.approx(120, abs=1e-6)
    finally:
        win._dirty = False
        win.close()

"""SolidWorks' Offset Entities (2026-11-14, Exercise 7: the bent wall is a
line, an R18 arc and a line, offset 12 with both ends capped).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

Q = math.tan(math.radians(22.5))          # a quarter arc's bulge


def _model():
    from khervecad.model import DocumentModel
    m = DocumentModel()
    g = m.add_node("union", {}, name="Sketch")
    return m, g


def _wall(m, g):
    """Up 28,18 -> 28,53, R18 over to 46,71, across to 91,71."""
    a = m.add_node("line", dict(x1=28, y1=18, x2=28, y2=53, width=0.2),
                   parent=g)
    b = m.add_node("line", dict(x1=28, y1=53, x2=46, y2=71, bulge=-Q,
                                width=0.2), parent=g)
    c = m.add_node("line", dict(x1=46, y1=71, x2=91, y2=71, width=0.2),
                   parent=g)
    return [a, b, c]


def test_a_line_arc_line_chain_offsets_and_caps():
    from khervecad import sketch_offset as so
    m, g = _model()
    chain = _wall(m, g)
    new = so.offset(m, chain, 12, side=1, cap=True)
    lines = [n for n in new if n.type == "line"]
    assert len(lines) == 5                          # 3 copies + 2 caps
    pts = {(round(n.params["x1"], 3), round(n.params["y1"], 3),
            round(n.params["x2"], 3), round(n.params["y2"], 3))
           for n in lines}
    # the copy runs 12 outside: up x = 16, over R30, across y = 83
    assert (16.0, 18.0, 16.0, 53.0) in pts
    assert (46.0, 83.0, 91.0, 83.0) in pts
    arc = next(n for n in lines if n.params.get("bulge"))
    from khervecad import sketch_arc
    cx, cy, r, _a, _s = sketch_arc.geometry(
        *(arc.params[k] for k in ("x1", "y1", "x2", "y2", "bulge")))
    assert (cx, cy, r) == pytest.approx((46, 53, 30))
    # the caps close both ends
    assert (28.0, 18.0, 16.0, 18.0) in pts
    assert (91.0, 71.0, 91.0, 83.0) in pts


def test_the_chain_is_found_in_any_order_and_direction():
    from khervecad import sketch_offset as so
    m, g = _model()
    a, b, c = _wall(m, g)
    c.params.update(x1=91, y1=71, x2=46, y2=71)      # drawn backwards
    new = so.offset(m, [a, c, b], 12, side=1, cap=False)
    assert len(new) == 3
    ys = sorted(round(n.params["y1"], 3) for n in new
                if not n.params.get("bulge") and
                abs(n.params["y1"] - n.params["y2"]) < 1e-9)
    assert ys == [83.0]


def test_a_square_corner_is_joined():
    from khervecad import sketch_offset as so
    m, g = _model()
    a = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0, width=0.2),
                   parent=g)
    b = m.add_node("line", dict(x1=10, y1=0, x2=10, y2=10, width=0.2),
                   parent=g)
    new = so.offset(m, [a, b], 2, side=1, cap=False)
    ends = sorted((round(n.params["x2"], 3), round(n.params["y2"], 3))
                  for n in new)
    assert (8.0, 2.0) in ends                        # met at the corner


def test_the_mcp_action(qtbot=None):
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    sk = w.model.add_node("union", {}, name="Sketch")
    chain = _wall(w.model, sk)
    out = McpToolExecutor(w).execute("sketch_modify", {
        "action": "offset", "node_ids": [n.id for n in chain],
        "size": 12, "reverse": False, "cap": True})
    assert "error" not in out, out
    assert len(out["node_ids"]) == 5
    w._dirty = False
    w.close()


def test_the_button_offsets_the_selection():
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad import sketch_modify
    w = MainWindow()
    w.show()
    sk = w.model.add_node("union", {}, name="Sketch")
    chain = _wall(w.model, sk)
    w.model.structure_changed.emit()
    QApplication.processEvents()
    w.builder.active_tree().select_nodes(chain)
    act = next(a for a in sketch_modify.panel_actions(w)
               if a.data() == "sk_offset")
    act.trigger()
    panel = w._offset_panel
    assert panel is not None
    panel.fields["distance"].setValue(12)
    panel.fields["cap"].setChecked(True)
    panel.ok.click()
    lines = [n for n in sk.children if n.type == "line"]
    assert len(lines) == 3 + 5
    w._dirty = False
    w.close()


def test_mcp_sketch_fillet_of_two_lines_is_a_real_arc():
    """As the window's Sketch Fillet: a bulged line (an arc) tangent to
    both, not a band polygon — so it can be offset and dimensioned."""
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    ex = McpToolExecutor(w)
    sk = w.model.add_node("union", {}, name="Sketch")
    a = w.model.add_node("line", dict(x1=28, y1=18, x2=28, y2=71,
                                      width=0.2), parent=sk)
    b = w.model.add_node("line", dict(x1=28, y1=71, x2=91, y2=71,
                                      width=0.2), parent=sk)
    out = ex.execute("sketch_modify", {"action": "fillet",
                                       "node_ids": [a.id, b.id], "size": 18})
    assert "error" not in out, out
    assert not any(n.type == "polygon" for n in sk.children)
    arc = next(n for n in sk.children if n.params.get("bulge"))
    from khervecad import sketch_arc
    cx, cy, r, _a, _s = sketch_arc.geometry(
        *(arc.params[k] for k in ("x1", "y1", "x2", "y2", "bulge")))
    assert (cx, cy, r) == pytest.approx((46, 53, 18), abs=1e-3)
    w._dirty = False
    w.close()


def test_arcs_of_one_circle_share_their_points():
    """Exercise 50: the cut's Converted R100 starts at x = 20 while the
    plate's R100 starts at the peak; split evenly each, their chords
    crossed and the cut left slivers standing along the arc. Arcs of
    one circle now put their points on the same angles."""
    import math
    from khervecad import sketch_arc
    c, r = (78.0, 124.8), 100.0

    def at(deg):
        a = math.radians(deg)
        return c[0] + r * math.cos(a), c[1] + r * math.sin(a)
    whole = sketch_arc.points(*at(250), *at(293),
                              sketch_arc.bulge_for_sweep(43))
    part = sketch_arc.points(*at(258.3), *at(293),
                             sketch_arc.bulge_for_sweep(34.7))
    keys = {(round(x, 6), round(y, 6)) for x, y in whole}
    inner = part[1:-1]
    assert len(inner) >= 3
    assert all((round(x, 6), round(y, 6)) in keys for x, y in inner)

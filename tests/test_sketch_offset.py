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


# ---- Offset Entities of the PART's edges (2026-11-14, Exercise 54: the
#   lead screw bracket's wall is the base's inside edges — a line, the R45
#   fillet and a line — clicked with Select chain and offset 19)

_L_BASE = """
linear_extrude(25) polygon([[-100, -106.5], [100, -106.5], [100, 106.5],
    [62, 106.5], [62, -4.5], [-100, -4.5]]); // Base
"""


def _filleted_base(w):
    """The video's way: the L extruded, then Fillet R45 on its inside
    upright edge."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(w)
    assert "error" not in ex.execute("apply_code", {"code": _L_BASE})
    part = next(c for c in w.model.root.children
                if c.visible and c.type not in ("assign", "variables"))
    edges = ex.execute("list_edges", {"node_id": part.id})["edges"]
    inner = [e["index"] for e in edges if not e["convex"]
             and abs(e["centre"][0] - 62) < 0.5
             and abs(e["centre"][1] + 4.5) < 0.5]
    out = ex.execute("fillet_edges", {"node_id": part.id, "chains": inner,
                                      "radius": 45})
    assert "error" not in out, out
    return next(c for c in w.model.root.children
                if c.visible and c.type not in ("assign", "variables"))


def _l_outline():
    """The base's top face: the L with the R45 fillet in its corner."""
    pts = [(-100, -106.5), (100, -106.5), (100, 106.5), (62, 106.5),
           (62, 40.5)]
    for i in range(1, 24):                  # R45 about (17, 40.5)
        a = math.radians(0 - 90 * i / 24)
        pts.append((17 + 45 * math.cos(a), 40.5 + 45 * math.sin(a)))
    pts += [(17, -4.5), (-100, -4.5)]
    return list(zip(pts, pts[1:] + pts[:1]))


def test_a_model_edge_chain_runs_through_tangent_edges_only():
    from khervecad import sketch_offset as so
    order = so.edge_chain(_l_outline(), (-50, -4.5), 1.0)
    assert order is not None and len(order) == 3     # line, arc, line
    ends = {(round(s[0], 2), round(s[1], 2)) for s in order} | \
        {(round(s[2], 2), round(s[3], 2)) for s in order}
    assert (-100, -4.5) in ends and (62, 106.5) in ends
    one = so.edge_chain(_l_outline(), (-50, -4.5), 1.0, chain=False)
    assert len(one) == 1


def test_a_model_edge_chain_offsets_into_the_part():
    from khervecad import sketch_offset as so
    m, g = _model()
    order = so.edge_chain(_l_outline(), (-50, -4.5), 1.0)
    new = so.offset_order(m, order, 19, parent=g)
    _check_wall(new)


def _check_wall(new):
    from khervecad import sketch_arc
    lines = [n.params for n in new if not n.params.get("bulge")]
    arcs = [n.params for n in new if n.params.get("bulge")]
    assert len(lines) == 2 and len(arcs) == 1, [n.params for n in new]
    ys = [p for p in lines if abs(p["y1"] - p["y2"]) < 1e-6]
    xs = [p for p in lines if abs(p["x1"] - p["x2"]) < 1e-6]
    assert ys and ys[0]["y1"] == pytest.approx(-23.5, abs=0.05)
    assert xs and xs[0]["x1"] == pytest.approx(81, abs=0.05)
    cx, cy, r, _a, _s = sketch_arc.geometry(
        *(arcs[0][k] for k in ("x1", "y1", "x2", "y2", "bulge")))
    assert (cx, cy, r) == pytest.approx((17, 40.5, 64), abs=0.3)


def test_the_mcp_offsets_part_edges_by_a_point():
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    ex = McpToolExecutor(w)
    _filleted_base(w)
    sk = ex.execute("reference_geometry", {
        "action": "sketch", "origin": [0, 0, 25], "normal": [0, 0, 1]})
    out = ex.execute("sketch_modify", {
        "action": "offset", "node_id": sk["sketch_id"],
        "point": [-50, -4.5], "size": 19})
    assert "error" not in out, out
    g = next(n for n in w.model.root.walk() if n.id == sk["sketch_id"])
    _check_wall([n for n in g.children if n.id in out["node_ids"]])
    w._dirty = False
    w.close()


def test_the_button_offsets_a_part_edge_clicked_in_3d(monkeypatch):
    """By mouse, as the video: open a sketch on the top face, press
    Offset Entities, click the base's inside edge in the 3D view (Select
    chain takes the fillet and the far line too), Distance 19, OK."""
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    from khervecad import cut_feature, sketch_modify
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    try:
        part = _filleted_base(w)
        QApplication.processEvents()
        cut_feature.start(w, "extruded_boss")
        w.view3d._pick_cb(dict(kind="face", pos=(0, -50, 25),
                               dir=(0, 0, 1)), part)
        QApplication.processEvents()
        w.view3d.resize(800, 600)
        w.view3d.fit()
        sk = w._sketch3d_tool
        g = sk.holder or sk.group
        before = list(g.children)
        act = next(a for a in sketch_modify.panel_actions(w)
                   if a.data() == "sk_offset")
        act.trigger()
        QApplication.processEvents()
        panel = w._offset_panel
        assert panel is not None
        panel.fields["distance"].setValue(19)
        v = w.view3d
        s = v._project(*v._camera(), (-50, -4.5, 25))
        QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier,
                         QPoint(int(round(s[0])), int(round(s[1]))))
        QApplication.processEvents()
        panel.ok.click()
        QApplication.processEvents()
        new = [n for n in g.children if n not in before
               and n.type == "line"]
        _check_wall(new)
    finally:
        w._dirty = False
        w.close()


def test_the_button_offsets_a_line_arc_line_with_square_corners():
    """Exercise 59's wall: a line, a quarter arc R90 and a line meeting at
    right angles (not tangent), offset 15 outward. SolidWorks trims the
    arc copy and the line copies to where they cross; the copies were left
    apart so the wall's outline stayed open."""
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    from khervecad import sketch_modify, sketch_arc
    w = MainWindow()
    w.show()
    sk = w.model.add_node("union", {}, name="Sketch")
    a = w.model.add_node("line", dict(x1=100, y1=63.5, x2=20, y2=63.5,
                                      width=0.2), parent=sk)
    b = w.model.add_node("line", dict(x1=20, y1=63.5, x2=-70, y2=-26.5,
                                      bulge=-Q, width=0.2), parent=sk)
    c = w.model.add_node("line", dict(x1=-70, y1=-26.5, x2=-70, y2=-106.5,
                                      width=0.2), parent=sk)
    w.model.structure_changed.emit()
    QApplication.processEvents()
    w.builder.active_tree().select_nodes([a, b, c])
    act = next(x for x in sketch_modify.panel_actions(w)
               if x.data() == "sk_offset")
    act.trigger()
    panel = w._offset_panel
    panel.fields["distance"].setValue(15)
    panel.ok.click()
    new = [n for n in sk.children if n.type == "line"][3:]
    assert len(new) == 3
    p = [n.params for n in new]
    for u, v in zip(p, p[1:]):
        assert (u["x2"], u["y2"]) == pytest.approx((v["x1"], v["y1"]),
                                                   abs=1e-6)
    top = math.sqrt(105 ** 2 - 15 ** 2) - 70
    assert (p[0]["x1"], p[0]["y1"]) == pytest.approx((100, 48.5))
    assert (p[0]["x2"], p[0]["y2"]) == pytest.approx((top, 48.5), abs=1e-4)
    arc = next(n for n in new if n.params.get("bulge"))
    cx, cy, r, _a, _s = sketch_arc.geometry(
        *(arc.params[k] for k in ("x1", "y1", "x2", "y2", "bulge")))
    assert (cx, cy, r) == pytest.approx((-70, 63.5, 105), abs=1e-4)
    assert (p[2]["x1"], p[2]["x2"]) == pytest.approx((-55, -55))
    w._dirty = False
    w.close()


def test_the_copies_of_a_faceted_chain_meet():
    """A part's fillet comes off its facets a hair off tangent (the arc
    ended at y = 40.243 where the line's copy began at 40.14): the copies
    must still join end to end, or the wall's band is open and the
    extrude takes the whole face."""
    from khervecad import sketch_offset as so
    m, g = _model()
    order = [[62.0, 106.5, 62.0, 40.243, 0.0],
             [62.0, 40.243, 17.257, -4.5, -0.4111212927],
             [17.257, -4.5, -100.0, -4.5, 0.0]]
    new = so.offset_order(m, order, 19, parent=g)
    p = [n.params for n in new]
    for a, b in zip(p, p[1:]):
        assert (a["x2"], a["y2"]) == pytest.approx((b["x1"], b["y1"]),
                                                   abs=1e-6)

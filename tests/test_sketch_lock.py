"""What a sketch is locked to and what is still free (2026-11-10, the
user: a boss grew both ways when its length changed — "I do not know
what it is locked to ... why is he using this centre").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_constraints as sc, sketch_lock
from khervecad.model import DocumentModel

from test_stacked_features import app, win, _base, _rect_feature  # noqa


def _boss_on_an_edge():
    """The user's boss: a rectangle whose bottom side rides on the
    part's edge y = 0, sized 30 x 12 — and nothing holding it sideways."""
    m = DocumentModel()
    g = m.add_node("union", {}, name="Sketch")
    r = m.add_node("rect", dict(x=20, y=0, width=30, height=12), parent=g)
    for v in ("v0", "v1"):
        sc.add(m, g, "on_edge", ["0." + v], edge=[0, 0, 100, 0])
    sc.add(m, g, "length", ["0.e0"], 30.0)
    sc.add(m, g, "length", ["0.e1"], 12.0)
    return m, g, r


def test_it_says_the_sketch_can_still_slide_along_the_edge():
    m, g, r = _boss_on_an_edge()
    info = sketch_lock.describe(m, g)
    assert info["dof"] == 1 and not info["defined"]
    assert info["ties"] == ["2 points on the part's edge"]
    assert len(info["free"]) == 1 and "slide left / right" in info["free"][0]
    assert sketch_lock.marker(info) == "(-) "
    assert "Under defined" in sketch_lock.text(info)


def test_a_dimension_to_the_parts_corner_locks_it():
    m, g, r = _boss_on_an_edge()
    ref = m.add_node("circle", dict(x=0, y=0, radius=0.25), parent=g,
                     name="Reference point")
    m.set_modifier(ref, "%")
    ref.params["ref_world"] = [[0, 0, 0]]
    sc.add(m, g, "fix", ["1.c"])
    sc.add(m, g, "distance", ["1.c", "0.v0"], 20.0)
    info = sketch_lock.describe(m, g)
    assert info["defined"] and sketch_lock.marker(info) == ""
    assert "dimensioned or related to a point of the part" in info["ties"]
    # ... and now a longer boss grows from the locked end only
    sc.set_value(m, g, 2, 40.0)
    assert (r.params["x"], r.params["width"]) == pytest.approx((20.0, 40.0),
                                                               abs=1e-4)


def test_a_free_size_is_named():
    m = DocumentModel()
    g = m.add_node("union", {}, name="Sketch")
    m.add_node("rect", dict(x=0, y=0, width=30, height=12), parent=g)
    sc.add(m, g, "fix", ["0.v0"])
    info = sketch_lock.describe(m, g)
    assert info["dof"] == 2 and info["ties"] == ["1 point fixed in place"]
    assert any("Rectangle" in f and "can still change" in f
               for f in info["free"])


def test_history_marks_an_under_defined_sketch(win):
    part = _base(win)
    boss = _rect_feature(win, part, (10, 5, 20), (-20, -10), (20, 10),
                         height=5.0)
    QApplication.processEvents()
    hb = win.builder.history_btn
    if not hb.isChecked():
        hb.click()
    QApplication.processEvents()
    tree = win.builder.active_tree()

    def rows(item=None, out=None):
        out = [] if out is None else out
        n = tree.topLevelItemCount() if item is None else item.childCount()
        for i in range(n):
            it = tree.topLevelItem(i) if item is None else item.child(i)
            out.append(it)
            rows(it, out)
        return out
    sketch = [it for it in rows() if "Sketch" in it.text(0)]
    assert sketch and sketch[-1].text(0).startswith("(-) ")
    assert "Under defined" in sketch[-1].toolTip(0)
    # the feature's Properties say it too
    tree.select_nodes([boss])
    QApplication.processEvents()
    from PyQt5.QtWidgets import QLabel
    labels = [w.text() for w in win.findChildren(QLabel)]
    assert any("Under defined" in t or "No relations" in t for t in labels)
    hb.click()


def test_an_assistant_reads_what_holds_a_sketch(win):
    from khervecad.mcp_tools import McpToolExecutor
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    m.add_node("rect", dict(x=20, y=0, width=30, height=12), parent=g)
    for v in ("v0", "v1"):
        sc.add(m, g, "on_edge", ["0." + v], edge=[0, 0, 100, 0])
    got = McpToolExecutor(win).execute("sketch_constraint",
                                       dict(action="list", node_id=g.id))
    assert got["held_by"] == ["2 points on the part's edge"]
    assert any("slide left / right" in f for f in got["free_to"])

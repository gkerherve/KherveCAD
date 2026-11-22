"""Exercise 010's outline: a Tangent Arc leaving a line's end, and a
3-Point Arc starting on a line's end, must be made and JOINED to that line."""
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from test_clevis_by_mouse import _frame, _ids, _sketch, _snap
from test_lever_by_mouse import win  # noqa
from test_open_arcs_by_mouse import _clicks, _lines_of


def _chain(win):
    # as the film does: no Escape between the line chain and the arc tool
    _clicks(win, "line", (0, 0), (20, 0), (20, 40))


def _joined(win, a, b):
    """Is there a coincident constraint tying a node's end to b's end?"""
    sk = a.parent
    cons = sk.params.get("constraints", []) if sk is not None else []
    kids = [n for n in sk.children]
    ia, ib = kids.index(a), kids.index(b)
    for c in cons:
        if c["kind"] == "coincident":
            idx = {int(r.split(".")[0]) for r in c["refs"]}
            if {ia, ib} <= idx:
                return True
    return False


def _setup(win):
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, -40, 100, 100)
    _chain(win)
    return before


def test_tangent_arc_from_a_line_end_is_made_and_joined(win):
    before = _setup(win)
    _clicks(win, "arc_tangent", (20, 40), (0, 60))
    ls = _lines_of(win, before)
    assert len(ls) == 3, "no tangent arc was made"
    assert (ls[2].params["x1"], ls[2].params["y1"]) == pytest.approx((20, 40))
    assert _joined(win, ls[1], ls[2])


def test_three_point_arc_on_a_line_end_is_joined_to_it(win):
    before = _setup(win)
    _clicks(win, "arc_3pt", (20, 40), (0, 60), (14, 54))
    ls = _lines_of(win, before)
    assert len(ls) == 3
    assert _joined(win, ls[1], ls[2])


def _inch_setup(win):
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    win.model.set_unit("in")
    _snap(win)
    _frame(win, -1.2, -0.3, 4.4, 4.2)
    _clicks(win, "line", (0, 0), (1.4, 0), (1.4, 2.0))
    return before


def test_tangent_arc_in_inches(win):
    before = _inch_setup(win)
    _clicks(win, "arc_tangent", (1.4, 2.0), (0, 3.4))
    ls = _lines_of(win, before)
    assert len(ls) == 3, "no tangent arc at inch scale"
    assert _joined(win, ls[1], ls[2])


def test_three_point_arc_in_inches_is_joined(win):
    before = _inch_setup(win)
    _clicks(win, "arc_3pt", (1.4, 2.0), (0, 3.4), (0.99, 2.99))
    ls = _lines_of(win, before)
    assert len(ls) == 3
    assert _joined(win, ls[1], ls[2])



def test_a_line_from_the_origin_stays_on_it_after_a_dimension(win):
    from khervecad import sketch_constraints as sc
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, -40, 100, 100)
    _clicks(win, "line", (0, 0), (20, 0), (20, 40))
    ls = _lines_of(win, before)
    sk = ls[0].parent
    sc.add(win.model, sk, "length", ["0.l"], value=30)
    assert (ls[0].params["x1"], ls[0].params["y1"]) == pytest.approx((0, 0))

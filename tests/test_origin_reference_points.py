"""Two Smart Dimensions from the origin made two "Reference point" copies
of it in the sketch (Exercise 010); one is enough."""
from test_clevis_by_mouse import _circle, _frame, _ids, _sketch, _sketch_of, _snap
from test_lever_by_mouse import win  # noqa
from test_smart_dimension_by_mouse import _dimension


def test_the_origin_is_copied_once_for_several_dimensions(win):
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -60, -20, 120, 120)
    _circle(win, (0, 30), 10)
    _circle(win, (0, 70), 10)
    sk = _sketch_of(win, before)
    _dimension(win, (0, 0), (0, 30), value=25)
    _dimension(win, (0, 0), (0, 70), value=75)
    refs = [c for c in sk.children if c.name == "Reference point"]
    assert len(refs) == 1, len(refs)

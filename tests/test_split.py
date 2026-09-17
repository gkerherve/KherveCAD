"""Split for printing (split.py, split_ui.py, MCP split_part)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, split
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad


def _vase(model):
    comp = model.new_component("Vase")
    model.add_node("cylinder", dict(
        x=0.0, y=0.0, z=0.0, height=120.0, radius_bottom=30.0,
        radius_top=20.0, segments=48, center=False), parent=comp)
    return comp


def test_split_makes_two_halves_a_pin_and_hides_the_original():
    model = DocumentModel()
    vase = _vase(model)
    first, second, pin, points = split.split_part(model, vase, "z", 40.0,
                                                  dowels=2)
    assert not vase.visible
    assert (first.name, second.name) == ("Vase (part 1)", "Vase (part 2)")
    assert second.params["z"] == 10.0                    # the gap
    assert len(points) == 2 and pin is not None
    assert validate(model.root) == {}
    holes = [n for n in first.walk() if n.type == "translate"
             and n.name.startswith("Dowel hole")]
    assert len(holes) == 2
    code = model.to_scad()
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code


def test_dowels_stay_inside_the_section_and_apart():
    loops = [[(0, 0), (40, 0), (40, 10), (0, 10)]]
    points = split.dowel_points(loops, 3, 3.0)
    assert points
    for u, v in points:
        assert 3 <= u <= 37 and 3 <= v <= 7
    if len(points) > 1:
        assert math.dist(points[0], points[1]) >= 6


def test_a_plane_outside_the_part_is_refused():
    model = DocumentModel()
    vase = _vase(model)
    with pytest.raises(ValueError):
        split.split_part(model, vase, "z", 500.0)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_and_mcp(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    from khervecad.split_ui import SplitDialog
    win = MainWindow()
    try:
        vase = _vase(win.model)
        dialog = SplitDialog(win, vase)
        assert dialog.position.value() == pytest.approx(60)
        dialog.dowels.setValue(1)
        dialog._split()
        names = {n.name for n in win.model.root.children}
        assert {"Vase (part 1)", "Vase (part 2)"} <= names
        other = _vase(win.model)
        result = McpToolExecutor(win).execute(
            "split_part", {"node_id": other.id, "axis": "x", "dowels": 0})
        assert "error" not in result and result["pin"] is None
    finally:
        win._dirty = False
        win.close()

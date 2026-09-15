"""Exploded views: the geometry (explode.py), the 3D view, PNG export,
the Printables stills and the MCP switch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import explode
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _two_parts(model):
    a = model.new_component("Base")
    model.add_node("cube", dict(width=20.0, depth=20.0, height=10.0),
                   parent=a)
    b = model.new_component("Lid")
    model.add_node("cube", dict(x=30.0, width=20.0, depth=20.0,
                                height=10.0), parent=b)
    colour = model.add_node("color", dict(color="#d0302a", alpha=1.0))
    ball = model.new_component("Ball")
    model.remove_node(ball)
    colour.add(ball)
    model.add_node("sphere", dict(radius=5.0, z=30.0), parent=ball)
    return a, b, colour


def _xs(items):
    return [v[0] for tri, _c in items for v in tri]


def test_offsets_push_each_part_away_from_the_centre():
    boxes = [([0, 0, 0], [10, 10, 10]), ([30, 0, 0], [40, 10, 10])]
    moves = explode.offsets(boxes, 1.0, "Radial")
    assert moves[0][0] == pytest.approx(-15) and moves[1][0] == pytest.approx(15)
    assert explode.offsets(boxes, 2.0, "Y") == [[0, 0, 0], [0, 0, 0]]
    stacked = [([0, 0, 0], [10, 10, 10]), ([0, 0, 20], [10, 10, 30])]
    assert explode.offsets(stacked, 1.0, "Z")[1] == pytest.approx([0, 0, 10])


def test_exploded_mesh_spreads_parts_and_keeps_colours(app):
    m = DocumentModel()
    _two_parts(m)
    from khervecad import mesh
    together = mesh.tessellate_colored(m.root)
    apart = explode.exploded_colored(m.root, amount=1.0)
    assert len(apart) == len(together)
    assert max(_xs(apart)) - min(_xs(apart)) > \
        max(_xs(together)) - min(_xs(together)) + 10
    assert sorted({c for _t, c in apart if c}) == \
        sorted({c for _t, c in together if c})      # the red ball stays red
    assert explode.part_count(m.root) == 3          # nested Object counted


def test_one_part_does_not_move(app):
    m = DocumentModel()
    a = m.new_component("Alone")
    m.add_node("cube", parent=a)
    from khervecad import mesh
    assert explode.exploded_colored(m.root, amount=3.0) == \
        mesh.tessellate_colored(m.root)


def _hinge_like(model, beside=True):
    """One Group holding two Objects — what a library insert or Make
    Object gives — and, optionally, a loose part beside it."""
    group = model.add_node("union", dict())
    group.name = "Hinge"
    a = model.new_component("Leaf A")
    model.remove_node(a)
    group.add(a)
    model.add_node("cube", dict(width=20.0, depth=20.0, height=4.0), parent=a)
    b = model.new_component("Leaf B")
    model.remove_node(b)
    group.add(b)
    model.add_node("cube", dict(y=25.0, width=20.0, depth=20.0, height=4.0),
                   parent=b)
    c = None
    if beside:
        c = model.new_component("Beside")
        model.add_node("cube", dict(x=80.0, width=10.0, depth=10.0,
                                    height=10.0), parent=c)
    return group, a, b, c


def _ys(items):
    return [v[1] for tri, _c in items for v in tri]


def test_a_lone_group_is_looked_into(app):
    """A document holding one Group of parts used to count as one part,
    and the exploded view silently did nothing."""
    m = DocumentModel()
    group, _a, _b, _c = _hinge_like(m, beside=False)
    plan = explode.plan(m.root, amount=1.0)
    assert plan.group is m.root and plan.path[-1] == group.id
    assert [p.name for p, _move in plan.pieces] == ["Leaf A", "Leaf B"]
    assert "the 2 parts of Hinge" == plan.note
    from khervecad import mesh
    together = mesh.tessellate_colored(m.root)
    assert max(_ys(plan.items)) - min(_ys(plan.items)) > \
        max(_ys(together)) - min(_ys(together)) + 10
    assert explode.part_count(m.root) == 2


def test_selecting_a_part_takes_its_assembly_apart_and_nothing_else(app):
    m = DocumentModel()
    group, a, _b, c = _hinge_like(m)
    plan = explode.plan(m.root, amount=1.0, selected=[a])
    assert plan.group is group
    moves = {p.name: move for p, move in plan.pieces}
    assert moves["Leaf A"][1] < 0 < moves["Leaf B"][1]
    # the part beside the hinge stays exactly where it is
    from khervecad import mesh
    beside = sorted(t for t, _c in mesh.tessellate_colored(c))
    assert sorted(t for t, _col in plan.items
                  if min(v[0] for v in t) >= 80.0 - 1e-9) == beside


def test_a_boolean_is_one_part(app):
    """Pulling a bore out of its plate would show nothing true."""
    m = DocumentModel()
    part = m.new_component("Plate")
    cut = m.add_node("difference", dict(), parent=part)
    m.add_node("cube", dict(width=20.0, depth=20.0, height=4.0), parent=cut)
    bore = m.add_node("cylinder", dict(x=10.0, y=10.0, z=-1.0, height=6.0,
                                       radius_bottom=3.0, radius_top=3.0),
                      parent=cut)
    plan = explode.plan(m.root, amount=2.0, selected=[bore])
    from khervecad import mesh
    assert plan.group is None and plan.pieces == []
    assert plan.items == mesh.tessellate_colored(m.root)
    assert plan.note.startswith("Nothing to pull apart")


def _window(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    _two_parts(w.model)
    w._refresh_preview()
    return w


def test_window_explodes_the_selected_part_s_assembly(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    _group, a, _b, _c = _hinge_like(w.model)
    w.model.structure_changed.emit()
    w._refresh_preview()
    w.builder.tree.select_nodes([a])
    app.processEvents()
    tint = lambda: (min(v[1] for t in w.view3d.highlight_mesh for v in t),
                    max(v[1] for t in w.view3d.highlight_mesh for v in t))
    assert tint() == pytest.approx((0.0, 20.0))
    w.set_explode(True, amount=1.0, mode="Radial")
    assert "the 2 parts of Hinge" in w.statusBar().currentMessage()
    assert w.explode_state()["parts"] == ["Leaf A", "Leaf B"]
    # Leaf A moved 12.5 mm towards -y, and its tint went with it
    assert tint() == pytest.approx((-12.5, 7.5))
    # a picture shows the whole assembly, whatever is selected
    with explode.showing(w):
        assert w._explode_plan.group is w.model.root
        assert len(w._explode_plan.pieces) == 2          # Hinge, Beside
    w.set_explode(False)
    assert tint() == pytest.approx((0.0, 20.0))


def test_window_says_when_nothing_can_come_apart(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    part = w.model.new_component("Alone")
    w.model.add_node("cube", parent=part)
    w._refresh_preview()
    w.set_explode(True)
    assert "Nothing to pull apart" in w.statusBar().currentMessage()
    assert "nothing to pull apart" in w.view3d.source
    w.set_explode(False)


def test_view_menu_explodes_the_3d_view(app):
    w = _window(app)
    width = lambda: max(v[0] for t in w.view3d.mesh for v in t) - \
        min(v[0] for t in w.view3d.mesh for v in t)
    before = width()
    w.set_explode(True, amount=1.0, mode="Radial")
    assert w._explode_act.isChecked()
    assert width() > before + 10
    assert "exploded" in w.view3d.source
    w.set_explode(False)
    assert width() == pytest.approx(before)
    assert w.model.root.children                  # nothing was edited


def test_png_export_can_explode(app, tmp_path):
    from khervecad import pngexport
    w = _window(app)
    out = pngexport.export_request(w.view3d, tmp_path / "apart.png",
                                   view="Isometric", width=320, height=240,
                                   exploded=True, window=w)
    assert out["exploded"] and (tmp_path / "apart.png").exists()
    assert not w.explode_state()["on"]            # put back afterwards


def test_printables_adds_exploded_stills_for_an_assembly(app, tmp_path):
    from khervecad import printables
    w = _window(app)
    bundle = printables.build_bundle(
        w, tmp_path, title="Box set", formats=("kcad",),
        views=("Isometric",), image_size=(320, 240))
    names = [os.path.basename(p) for p in bundle["images"]]
    assert any("exploded" in n for n in names), names
    single = DocumentModel()
    w.model.root.children[:] = []
    lone = w.model.new_component("Lone")
    w.model.add_node("cube", parent=lone)
    w._refresh_preview()
    bundle = printables.build_bundle(
        w, tmp_path / "one", title="Lone", formats=("kcad",),
        views=("Isometric",), image_size=(320, 240))
    assert not any("exploded" in os.path.basename(p)
                   for p in bundle["images"])
    del single


def test_mcp_set_render_options_explodes(app):
    from khervecad.mcp_tools import McpToolExecutor
    w = _window(app)
    tools = McpToolExecutor(w)
    out = tools.execute("set_render_options", {"explode": 1.5,
                                               "explode_mode": "X"})
    state = out.get("exploded") or w.explode_state()
    assert state["on"] and state["amount"] == 1.5 and state["mode"] == "X"
    tools.execute("set_render_options", {"explode": 0})
    assert not w.explode_state()["on"]

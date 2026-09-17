"""Motion stays fast: a variable that drives movement must RE-PLACE
parts, never rebuild them, and nothing invisible may be recomputed on
the way. Each test here pins one of the things that made a moving
model crawl.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import anchors, library_motion as lm, library_solar as ls, mesh
from khervecad.model import CadNode, DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _var(doc, suffix):
    return next(n for n in doc.global_assigns()
                if n.params["variable"].endswith(suffix))


def _object(doc, name):
    return next(c for c in doc.all_components() if c.name == name)


# ------------------------------------------------- what a part depends on

def test_a_variable_named_like_a_parameter_is_not_a_dependency(app):
    """An Object's cache key may only depend on the variables its
    EXPRESSIONS read. It used to be matched against the whole key —
    parameter names and node types included — so a circle's `angle=`
    made the part depend on a variable called `angle`, and every moon
    of an orrery re-tessellated on every tick."""
    doc = DocumentModel()
    part = CadNode("component", "Dial", dict(x=0.0, y=0.0, z=0.0, rx=0.0,
                                             ry=0.0, rz=0.0, color="",
                                             alpha=1.0))
    part.add(CadNode("circle", "Face", dict(x=0.0, y=0.0, radius=10.0,
                                            angle=360.0, start_angle=0.0,
                                            segments=32)))
    doc.root.add(part)
    before = mesh._component_key(part, {"angle": 0.0, "radius": 4.0})
    after = mesh._component_key(part, {"angle": 90.0, "radius": 4.0})
    assert before == after
    # but a part that really reads it does depend on it
    part.children[0].params["radius"] = "angle"
    reading = mesh._component_key(part, {"angle": 0.0})
    assert reading != mesh._component_key(part, {"angle": 90.0})


def test_a_slider_rebuilds_only_what_it_moves(app):
    """A tick of an orrery re-places every body but rebuilds none: the
    globes' meshes come back from the cache."""
    doc = DocumentModel()
    ls.insert_system("solar_system", doc)
    fn = doc.effective_fn()
    mesh.tessellate_colored(doc.root, env=anchors.doc_env(doc), fn=fn)
    globes = [c for c in doc.all_components() if c.name.endswith("globe")]
    assert len(globes) > 20
    _var(doc, "_days").params["value"] = 40.0
    mesh.CACHE_STATS["hits"] = mesh.CACHE_STATS["misses"] = 0
    mesh.tessellate_colored(doc.root, env=anchors.doc_env(doc), fn=fn)
    # every globe (the geometry) is a hit; the bodies that carry them
    # move, so those are the misses
    assert mesh.CACHE_STATS["hits"] >= len(globes)


def test_a_mechanism_moves_without_rebuilding_its_gears(app):
    doc = DocumentModel()
    comps = lm.insert("motion_gear_pair", doc)
    fn = doc.effective_fn()
    env = anchors.doc_env(doc)
    before = {c.name: mesh.tessellate(c, env=env, fn=fn) for c in comps}
    _var(doc, "_angle").params["value"] = 37.0
    env = anchors.doc_env(doc)
    after = {c.name: mesh.tessellate(c, env=env, fn=fn) for c in comps}
    assert before["Drive gear"] != after["Drive gear"]        # it turned
    assert len(before["Drive gear"]) == len(after["Drive gear"])
    assert before["Motor"] == after["Motor"]                  # it did not


# ------------------------------------------------------ transform chains

def test_a_chain_of_transforms_is_one_pass(app):
    """translate · rotate · scale over a part is ONE matrix. Applied
    one link at a time it walked the whole mesh per link, which on an
    assembly is the whole model several times over per frame."""
    cube = CadNode("cube", "Body", dict(x=0.0, y=0.0, z=0.0, width=10.0,
                                        depth=4.0, height=2.0,
                                        center=True))
    plain = mesh.tessellate(cube, env={}, fn=16)
    chain = CadNode("translate", "Move", dict(x=10.0, y=2.0, z=-3.0))
    turn = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z=35.0))
    grow = CadNode("scale", "Size", dict(x=2.0, y=1.0, z=0.5))
    chain.add(turn)
    turn.add(grow)
    grow.add(cube)
    calls = []
    original = mesh._transform_colored

    def spy(matrix, marked):
        calls.append(matrix)
        return original(matrix, marked)
    mesh._transform_colored = spy
    try:
        got = mesh.tessellate(chain, env={}, fn=16)
    finally:
        mesh._transform_colored = original
    assert len(calls) == 1, "the chain should collapse to one matrix"
    want = mesh.transform_mesh(
        mesh.mat_mul(mesh.mat_mul(mesh.mat_translate(10.0, 2.0, -3.0),
                                  mesh.mat_rotate(0.0, 0.0, 35.0)),
                     mesh.mat_scale(2.0, 1.0, 0.5)), plain)
    assert len(got) == len(want)
    for a, b in zip(got, want):
        for p, q in zip(a, b):
            assert all(abs(u - v) < 1e-9 for u, v in zip(p, q))


def test_a_hidden_link_in_a_chain_still_hides_its_part(app):
    chain = CadNode("translate", "Move", dict(x=5.0, y=0.0, z=0.0))
    inner = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z=90.0))
    inner.visible = False
    inner.add(CadNode("cube", "Body", dict(x=0.0, y=0.0, z=0.0, width=4.0,
                                           depth=4.0, height=4.0,
                                           center=True)))
    chain.add(inner)
    assert mesh.tessellate(chain, env={}, fn=16) == []


# ----------------------------------------------- nothing invisible rebuilt

def test_the_code_tab_waits_until_it_is_looked_at(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    builder = win.builder
    builder.setCurrentIndex(0)                       # Main
    lm.insert("motion_gear_pair", win.model)
    win.model.structure_changed.emit()
    stale = builder.code.toPlainText()
    angle = _var(win.model, "_angle")
    angle.params["value"] = 42.0
    win.model.node_changed.emit(angle)
    assert builder._code_dirty
    assert builder.code.toPlainText() == stale       # not regenerated
    builder.setCurrentIndex(builder.indexOf(builder._code_page))
    assert not builder._code_dirty
    assert "42" in builder.code.toPlainText()
    # left open on purpose: closing a dirty window asks to discard, and
    # that dialog has nobody to answer it here


def test_a_customizer_row_follows_a_value_without_being_rebuilt(app):
    from khervecad.customizer_panel import CustomizerPanel
    doc = DocumentModel()
    lm.insert("motion_gear_pair", doc)
    panel = CustomizerPanel(doc)
    angle = _var(doc, "_angle")
    row = panel._rows[angle.id]
    angle.params["value"] = 45.0
    doc.node_changed.emit(angle)
    assert panel._rows[angle.id] is row, "the control was recreated"
    assert row[1].text() == "45"                     # the value shown
    assert row[2].value() == 9                       # 45 / step 5
    # a control that changes shape is still rebuilt
    angle.params["options"] = "0:1:90"
    doc.node_changed.emit(angle)
    assert panel._rows[angle.id] is not row


def test_the_exact_paint_order_waits_for_the_model_to_settle(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.hardware = False                            # the painter's path
    tris = [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
            ((0.0, 0.0, 5.0), (10.0, 0.0, 5.0), (0.0, 10.0, 5.0))]
    view.set_mesh(tris, "preview")
    assert view._bsp_timer.isActive(), "a build started under the drag"
    assert view._bsp is None
    view.wait_for_bsp()                              # a still model needs it
    assert not view._bsp_timer.isActive()
    assert view._bsp is not None

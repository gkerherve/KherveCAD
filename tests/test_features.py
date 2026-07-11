"""Tests for expressions, control flow, rounding ops and partial
circles.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import expr
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


# --------------------------------------------------------- expressions

def test_expr_arithmetic():
    assert expr.evaluate("2 + 3 * 4") == 14
    assert expr.evaluate("2 ^ 3") == 8            # OpenSCAD power
    assert expr.evaluate("i * 10 + 2", {"i": 3}) == 32


def test_expr_trig_in_degrees():
    assert expr.evaluate("sin(30)") == pytest.approx(0.5)
    assert expr.evaluate("cos(60)") == pytest.approx(0.5)
    assert expr.evaluate("atan2(1, 1)") == pytest.approx(45.0)


def test_expr_conditions():
    assert expr.evaluate("x < 100", {"x": 50}) is True
    assert expr.evaluate("x < 100 and x > 10", {"x": 5}) is False


def test_expr_rejects_python():
    with pytest.raises(expr.ExprError):
        expr.evaluate("__import__('os')")
    with pytest.raises(expr.ExprError):
        expr.evaluate("open('/etc/passwd')")


def test_expr_resolve_fallback():
    assert expr.resolve("nope + 1", None, 7.0) == 7.0
    assert expr.resolve(3.5) == 3.5


# ----------------------------------------------------- expression params

def test_expression_param_emitted_raw(model):
    model.add_node("circle", dict(x="i * 10", y=0.0, radius=5.0))
    assert "translate([i * 10, 0])" in model.root.to_scad()


# ------------------------------------------------------ partial circles

def test_quarter_circle_is_polygon_fan(model):
    model.add_node("circle", dict(radius=10.0, angle=90.0, segments=8))
    code = model.root.to_scad()
    assert "polygon(points=[[0, 0]," in code
    assert "[10, 0]" in code                      # arc start
    assert "[0, 10]" in code.replace("[0.0", "[0")  # arc end at 90 deg


def test_semi_circle_arc_ends(model):
    node = model.add_node("circle", dict(radius=10.0, angle=180.0,
                                         segments=16))
    pts = node.arc_points()
    assert pts[0] == (pytest.approx(10.0), pytest.approx(0.0))
    assert pts[-1][0] == pytest.approx(-10.0)
    assert pts[-1][1] == pytest.approx(0.0, abs=1e-9)


def test_full_circle_still_circle(model):
    model.add_node("circle", dict(radius=10.0, angle=360.0))
    assert "circle(r=10" in model.root.to_scad()


# ---------------------------------------------------------- rounding ops

def test_offset_codegen(model):
    c = model.add_node("circle")
    off = model.wrap_nodes([c], "offset")
    off.params["radius"] = 3.0
    assert "offset(r=3)" in model.root.to_scad()
    off.params["chamfer"] = True
    assert "offset(delta=3, chamfer=true)" in model.root.to_scad()


def test_round_edges_builds_minkowski_with_sphere(model):
    cube = model.add_node("cube")
    wrapper = model.round_edges([cube], radius=2.0)
    assert wrapper.type == "minkowski"
    code = model.root.to_scad()
    assert code.startswith("minkowski() {")
    assert "sphere(r=2" in code
    assert "cube(" in code


def test_hull_codegen(model):
    a = model.add_node("circle")
    b = model.add_node("rect")
    model.wrap_nodes([a, b], "hull")
    assert model.root.to_scad().startswith("hull() {")


# ---------------------------------------------------------- control flow

def test_for_loop_codegen(model):
    loop = model.add_node("for_loop", dict(variable="a", start=0.0,
                                           end=270.0, step=90.0))
    model.add_node("cube", parent=loop)
    code = model.root.to_scad()
    assert code.startswith("for (a = [0 : 90 : 270]) {")


def test_for_loop_value_list(model):
    loop = model.add_node("for_loop", dict(values="3, 7, 12"))
    model.add_node("sphere", parent=loop)
    assert "for (i = [3, 7, 12])" in model.root.to_scad()
    assert loop.loop_values() == [3, 7, 12]


def test_while_loop_unrolls_to_valid_for(model):
    loop = model.add_node("while_loop", dict(
        variable="x", start=1.0, condition="x < 20", update="x * 2"))
    model.add_node("sphere", dict(radius="x"), parent=loop)
    assert loop.loop_values() == [1, 2, 4, 8, 16]
    code = model.root.to_scad()
    assert "for (x = [1, 2, 4, 8, 16])" in code
    assert "sphere(r=x" in code


def test_while_loop_never_infinite(model):
    loop = model.add_node("while_loop", dict(
        variable="x", start=0.0, condition="true", update="x"))
    assert len(loop.loop_values()) == 1000


def test_if_else_codegen(model):
    cond = model.add_node("if_else", dict(condition="size > 10"))
    # add_node auto-creates the Else union
    else_branch = cond.children[0]
    assert else_branch.name == "Else"
    model.add_node("cube", parent=cond)
    model.add_node("sphere", parent=else_branch)
    code = model.root.to_scad()
    assert code.startswith("if (size > 10) {")
    assert "} else {" in code
    assert code.index("cube") < code.index("} else")
    assert code.index("sphere") > code.index("} else")


def test_if_without_else_children(model):
    cond = model.add_node("if_else", dict(condition="true"))
    model.add_node("cube", parent=cond)
    assert "else" not in model.root.to_scad().replace("Else", "")


def test_assign_codegen(model):
    model.add_node("assign", dict(variable="bore", value="38.1"))
    model.add_node("circle", dict(radius="bore / 2"))
    code = model.root.to_scad()
    assert "bore = 38.1;" in code
    assert "circle(r=bore / 2" in code


def test_wrap_in_if_else_puts_nodes_in_then(model):
    cube = model.add_node("cube")
    cond = model.wrap_nodes([cube], "if_else")
    code = model.root.to_scad()
    assert "cube(" in code.split("else")[0]


# ------------------------------------------------------------ STL import

def test_stl_import_codegen(model):
    model.add_node("stl_import", dict(path="parts/rotor.stl", x=5.0))
    code = model.root.to_scad()
    assert 'import("parts/rotor.stl", convexity=10)' in code
    assert "translate([5, 0, 0])" in code


# -------------------------------------------------------------- roundtrip

def test_common_fn_overrides_round_objects(model):
    import re
    from khervecad import mesh
    model.global_fn_on = False                    # start from per-object
    model.add_node("cylinder", dict(radius_bottom=5.0, radius_top=5.0,
                                    height=10.0, segments=96))
    model.add_node("sphere", dict(radius=4.0, segments=48))
    # a linear_extrude whose "segments" means slices, not $fn
    ext = model.add_node("linear_extrude", dict(height=3.0, segments=7))
    model.add_node("circle", dict(radius=2.0), parent=ext)

    fns = lambda code: sorted(set(int(x)
                                  for x in re.findall(r"\$fn=(\d+)", code)))
    own = fns(model.to_scad())
    assert len(own) > 1 and 96 in own and 48 in own   # each keeps its own

    model.set_global_fn(True, 16)
    assert model.effective_fn() == 16
    assert fns(model.to_scad()) == [16]             # all forced to 16
    assert "slices=7" in model.to_scad()            # slices untouched
    # tessellation honours it too (coarser mesh => fewer triangles)
    coarse = len(mesh.tessellate(model.root, fn=16))
    fine = len(mesh.tessellate(model.root, fn=None))
    assert coarse < fine

    model.set_global_fn(False)
    assert fns(model.to_scad()) == own              # own values restored


def test_common_fn_roundtrips_kcad(model, tmp_path):
    from khervecad import document
    model.add_node("cylinder", dict(segments=96))
    model.set_global_fn(True, 24)
    path = tmp_path / "fn.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    assert other.global_fn_on is True
    assert other.global_fn == 24
    assert other.to_scad() == model.to_scad()


def test_new_nodes_roundtrip_kcad(model, tmp_path):
    from khervecad import document
    loop = model.add_node("for_loop", dict(variable="a", start=0.0,
                                           end=270.0, step=90.0))
    rot = model.add_node("rotate", dict(z="a"), parent=loop)
    model.add_node("circle", dict(radius=5.0, angle=90.0), parent=rot)
    model.add_node("assign", dict(variable="k", value="2"))
    path = tmp_path / "loops.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    assert other.to_scad() == model.to_scad()


def test_group_variables_transparent_and_scoped(model):
    import re
    from khervecad import mesh
    model.add_node("assign", dict(variable="w", value="100"))
    model.add_node("assign", dict(variable="h", value="w/2"))
    model.add_node("cube", dict(width="w", depth="w", height="h"))
    model.group_variables()

    # one "Variables" container holding the two assigns, ahead of geometry
    assert [c.type for c in model.root.children] == ["variables", "cube"]
    grp = model.root.children[0]
    assert [c.params["variable"] for c in grp.children] == ["w", "h"]

    # the group is transparent in the code (no wrapper, still top-level)
    code = model.to_scad()
    assert "variables" not in code
    assert re.search(r"^w = 100;$", code, re.M)
    # scope is preserved: the cube resolves h = w/2 = 50
    zmax = max(v[2] for t in mesh.tessellate(model.root) for v in t)
    assert zmax == 50.0
    from khervecad.model import validate
    assert validate(model.root) == {}


def test_group_variables_idempotent_and_needs_two(model):
    model.add_node("assign", dict(variable="a", value="1"))
    model.add_node("cube")
    model.group_variables()                    # only one var -> no group
    assert [c.type for c in model.root.children] == ["assign", "cube"]

    model.add_node("assign", dict(variable="b", value="2"),
                   parent=model.root)
    model.root.children.insert(1, model.root.children.pop())  # a,b,cube
    model.group_variables()
    assert model.root.children[0].type == "variables"
    n = sum(1 for c in model.root.children if c.type == "variables")
    model.group_variables()                    # idempotent
    assert sum(1 for c in model.root.children
               if c.type == "variables") == n


def test_import_scad_groups_variables(model, tmp_path):
    from khervecad import scadparse
    path = tmp_path / "vars.scad"
    path.write_text("w = 10;\nd = 20;\ncube([w, d, 5]);\n")
    scadparse.import_scad(model, str(path))
    assert model.root.children[0].type == "variables"
    assert [c.params["variable"]
            for c in model.root.children[0].children] == ["w", "d"]


def test_group_carries_transform_and_colour(model):
    from khervecad import mesh
    grp = model.add_node("union")
    model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
                   parent=grp)
    group_line = lambda c: next(l.strip() for l in c.splitlines()
                                if l.strip().endswith("union() {"))
    # a plain group's own line is just union()
    assert group_line(model.to_scad()) == "union() {"

    grp.params.update(x=50.0, rz=90.0, color="#ff0000")
    code = model.to_scad()
    line = group_line(code)
    assert line == ('color("#ff0000") translate([50, 0, 0]) '
                    'rotate([0, 0, 90]) union() {')
    # geometry is actually moved/rotated in the preview mesh
    xs = [v[0] for t in mesh.tessellate(model.root) for v in t]
    assert max(xs) == 50.0 and 40.0 <= min(xs) <= 41.0


def test_group_transform_roundtrips_kcad(model, tmp_path):
    from khervecad import document
    grp = model.add_node("union")
    model.add_node("cube", parent=grp)
    grp.params.update(y=12.0, ry=30.0, color="#00ff00", alpha=0.5)
    path = tmp_path / "grp.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    reloaded = other.root.children[0]
    assert reloaded.params["y"] == 12.0
    assert reloaded.params["ry"] == 30.0
    assert reloaded.params["color"] == "#00ff00"

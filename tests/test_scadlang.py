"""OpenSCAD statements as tree nodes (scadlang.py) and the expression
evaluator's OpenSCAD semantics (expr.py): every statement imports as a
node, exports as the same code, and previews."""

import math

import pytest

from khervecad import expr, mesh, scadlang
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad


# ------------------------------------------------------------ expressions

@pytest.mark.parametrize("source, expected", [
    ("[1, 2, 3] * 2", [2, 4, 6]),
    ("[1, 2] + [3, 4]", [4, 6]),
    ("-[1, 2]", [-1, -2]),
    ("[1, 2, 3] * [1, 1, 1]", 6),
    ("[[1, 0], [0, 2]] * [3, 4]", [3, 8]),
    ("[3, 4] * [[1, 0], [0, 2]]", [3, 8]),
    ('str("a", 1.5, [1, "b"], true)', 'a1.5[1, "b"]true'),
    ('len("hello")', 5),
    ("round(2.5)", 3),
    ("round(-2.5)", -3),
    ("lookup(1.5, [[1, 10], [2, 20]])", 15),
    ("lookup(9, [[1, 10], [2, 20]])", 20),
    ("let (a = 2, b = a * 3) a + b", 8),
    ("max([3, 9, 2])", 9),
    ("(function (x, y = 2) x * y)(4)", 8),
    ('search("a", "banana", 0)', [[1, 3, 5]]),
    ("chr([72, 105])", "Hi"),
    ('ord("A")', 65),
    ("cross([1, 0, 0], [0, 1, 0])", [0, 0, 1]),
    ('"a:b?c!"', "a:b?c!"),
    ("-5 % 3", -2),
    ("[for (i = [0 : 3]) let (s = i * i) s]", [0, 1, 4, 9]),
    ("is_num(3) && !is_string(3)", True),
    ("norm([3, 4])", 5),
    ("log(2, 8)", 3),
    ('echo("hi") 3', 3),
    ("$fn", 0),
])
def test_openscad_expression_semantics(source, expected):
    value = expr.evaluate(source)
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert value == pytest.approx(expected)
    else:
        assert value == expected


def test_special_variables_and_closures_read_the_scope():
    assert expr.evaluate("$fn", {"$fn": 30}) == 30
    f = expr.evaluate("function (x) x + k", {"k": 10})
    assert expr.evaluate("f(5)", {"f": f}) == 15
    assert expr.evaluate("x > 1 ? let (y = x * 2) y : 0", {"x": 3}) == 6


def test_division_by_zero_is_infinite_not_a_crash():
    assert math.isinf(expr.evaluate("1 / 0"))
    assert expr.resolve("[1, 2] / 0", None, 7.0) == 7.0


def test_failed_assert_in_an_expression_raises():
    assert expr.evaluate('assert(x > 0, "bad") x', {"x": 2}) == 2
    with pytest.raises(expr.ExprError):
        expr.evaluate('assert(x > 0, "bad") x', {"x": -2})


def test_rands_are_stable_between_redraws():
    assert expr.evaluate("rands(0, 1, 3)") == expr.evaluate("rands(0, 1, 3)")
    assert len(expr.evaluate("rands(0, 1, 3, 42)")) == 3


# ------------------------------------------------------------- statements

PROGRAM = '''\
w = 10;
resize([40, 0, 0], auto = [false, true, true]) cube([w, 5, 2]);
multmatrix([[1, 0, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) sphere(3);
render(convexity = 4) cylinder(h = 5, r = 2);
intersection_for (i = [0 : 60 : 120]) rotate([0, 0, i]) cube([20, 4, 4], center = true);
let (r = w / 2, h = r * 3) { translate([0, 0, h]) sphere(r); }
echo("w = ", w, big = w > 5);
assert(w > 5, str("w too small: ", w));
linear_extrude(3) resize([30, 10]) circle(5);
'''


def _types(root):
    return [n.type for n in root.walk()]


def test_statements_import_as_nodes():
    root, warnings = parse_scad(PROGRAM)
    assert not warnings
    types = _types(root)
    for t in ("resize", "multmatrix", "render", "intersection_for", "let",
              "echo", "assert"):
        assert t in types
    let = next(n for n in root.walk() if n.type == "let")
    assert let.params["bindings"] == "r = w / 2, h = r * 3"
    echo = next(n for n in root.walk() if n.type == "echo")
    assert echo.params["args"] == '"w = ", w, big = w > 5'


def test_statements_round_trip_losslessly():
    root, _ = parse_scad(PROGRAM)
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code


def test_statements_validate_and_preview():
    root, _ = parse_scad(PROGRAM)
    assert validate(root) == {}
    assert mesh.tessellate(root)


def test_failing_assert_turns_the_node_red_with_its_message():
    root, _ = parse_scad('w = 2; assert(w > 5, str("w too small: ", w));')
    errors = validate(root)
    node = next(n for n in root.walk() if n.type == "assert")
    assert errors[node.id] == "assertion failed: w too small: 2"


def test_let_bindings_reach_the_children_in_validation():
    model = DocumentModel()
    let = model.add_node("let", dict(bindings="r = 4, h = r * 2"))
    model.add_node("cylinder", dict(x=0.0, y=0.0, z=0.0, height="h",
                                    radius_bottom="r", radius_top="r",
                                    segments=16, center=False), parent=let)
    assert validate(model.root) == {}
    zs = [v[2] for tri in mesh.tessellate(model.root) for v in tri]
    assert max(zs) == pytest.approx(8)


def test_resize_scales_to_the_absolute_size():
    root, _ = parse_scad("resize([40, 0, 0], auto = true) cube([10, 5, 2]);")
    pts = [v for tri in mesh.tessellate(root) for v in tri]
    size = [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)]
    assert size == pytest.approx([40, 20, 8])


def test_multmatrix_moves_and_shears():
    root, _ = parse_scad(
        "multmatrix([[1, 1, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0]]) "
        "cube([1, 1, 1]);")
    node = next(n for n in root.walk() if n.type == "multmatrix")
    assert node.params["matrix"][3] == [0.0, 0.0, 0.0, 1.0]
    xs = [v[0] for tri in mesh.tessellate(root) for v in tri]
    assert (min(xs), max(xs)) == pytest.approx((5, 7))


def test_2d_resize_inside_an_extrude():
    root, _ = parse_scad("linear_extrude(3) resize([30, 10]) circle(5);")
    pts = [v for tri in mesh.tessellate(root) for v in tri]
    assert max(p[0] for p in pts) - min(p[0] for p in pts) == \
        pytest.approx(30, rel=0.02)


def test_echo_text_formats_like_openscad():
    root, _ = parse_scad('w = 10; echo("a, b = ", w, big = w > 5);')
    node = next(n for n in root.walk() if n.type == "echo")
    assert scadlang.echo_text(node, {"w": 10}) == \
        'ECHO: "a, b = ", 10, big = true'


def test_singular_matrix_is_an_error():
    root, _ = parse_scad(
        "multmatrix([[0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]) cube(1);")
    assert any("det 0" in m for m in validate(root).values())


# ------------------------------------------------- text, polygon, $fa/$fs

@pytest.fixture
def qapp():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _extent(root, axis):
    pts = [v for tri in mesh.tessellate(root) for v in tri]
    return min(p[axis] for p in pts), max(p[axis] for p in pts)


def test_text_options_round_trip(qapp):
    source = ('linear_extrude(2) text("Hi", size = 10, font = '
              '"Liberation Sans:style=Bold", halign = "center", '
              'valign = "center", spacing = 1.2, direction = "rtl");')
    root, warnings = parse_scad(source)
    assert not warnings
    text = next(n for n in root.walk() if n.type == "text")
    assert (text.params["halign"], text.params["valign"],
            text.params["direction"], text.params["spacing"]) == \
        ("center", "center", "rtl", 1.2)
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert 'halign="center"' in code and 'font="Liberation Sans' in code
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code


def test_text_alignment_moves_the_glyphs(qapp):
    left, _ = parse_scad('linear_extrude(1) text("Hello", size = 10);')
    centre, _ = parse_scad('linear_extrude(1) text("Hello", size = 10, '
                           'halign = "center", valign = "center");')
    lx0, lx1 = _extent(left, 0)
    cx0, cx1 = _extent(centre, 0)
    assert lx0 >= -0.5 and (cx0 + cx1) / 2 == pytest.approx(0, abs=1.0)
    cy0, cy1 = _extent(centre, 1)
    assert (cy0 + cy1) / 2 == pytest.approx(0, abs=0.1)


def test_default_text_emits_as_before():
    model = DocumentModel()
    model.add_node("text", dict(x=0.0, y=0.0, text="A", size=5.0))
    assert 'text("A", size=5);' in model.to_scad()


def test_polygon_paths_make_holes():
    root, warnings = parse_scad(
        "linear_extrude(2) polygon(points = [[0, 0], [30, 0], [30, 30], "
        "[0, 30], [10, 10], [20, 10], [20, 20], [10, 20]], "
        "paths = [[0, 1, 2, 3], [4, 5, 6, 7]]);")
    assert not warnings
    poly = next(n for n in root.walk() if n.type == "polygon")
    assert poly.params["paths"] == [[0, 1, 2, 3], [4, 5, 6, 7]]
    from khervecad import analysis
    assert analysis.mass_properties(mesh.tessellate(root))["volume"] == \
        pytest.approx(1600)
    model = DocumentModel()
    model.root = root
    assert "paths=[[0, 1, 2, 3], [4, 5, 6, 7]]" in model.to_scad()


def test_fa_fs_choose_the_segments_like_openscad():
    root, _ = parse_scad("$fa = 6; $fs = 0.5; circle(r = 10); "
                         "sphere(1, $fs = 2); cylinder(h = 1, r = 1, $fn = n);")
    circle, sphere, cyl = [n for n in root.walk()
                           if n.type in ("circle", "sphere", "cylinder")]
    assert circle.params["segments"] == 60          # min(360/6, 2 pi 10/.5)
    assert sphere.params["segments"] == 5           # at least five
    assert cyl.params["segments"] == "n"            # an expression stays


# ------------------------------------------------------ debug modifiers

def test_debug_modifiers_round_trip_and_preview():
    root, warnings = parse_scad(
        "#cube(5); %translate([10, 0, 0]) sphere(2);")
    assert not warnings
    cube, sphere = root.children
    assert (cube.params["modifier"], sphere.params["modifier"]) == ("#", "%")
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert "#translate([0, 0, 0]) cube(" in code
    assert "%translate([10, 0, 0]) sphere(" in code
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code
    colours = {c for _t, c in mesh.tessellate_colored(root)}
    assert colours == {mesh.MODIFIER_TINT["#"], mesh.MODIFIER_TINT["%"]}


def test_show_only_renders_that_part_where_it_sits():
    root, _ = parse_scad("cube(10); translate([20, 0, 0]) "
                         "{ !cylinder(h = 3, r = 1); sphere(9); }")
    xs = [v[0] for tri in mesh.tessellate(root) for v in tri]
    assert (min(xs), max(xs)) == pytest.approx((19, 21))


def test_a_hidden_node_keeps_star_and_set_modifier_clears():
    model = DocumentModel()
    cube = model.add_node("cube")
    model.set_modifier(cube, "%")
    assert "%translate" in model.to_scad()
    model.set_visible(cube, False)
    assert "*translate" in model.to_scad()
    model.set_visible(cube, True)
    model.set_modifier(cube, "")
    assert "modifier" not in cube.params

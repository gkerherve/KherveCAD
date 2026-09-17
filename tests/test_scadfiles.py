"""surface() height maps and import() of SVG / DXF drawings as nodes
(scadfiles.py, svgdxf.py): read, previewed, exported and re-imported."""

import xml.etree.ElementTree as ET

import pytest

from khervecad import mesh, scadfiles, svgdxf
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm"
     viewBox="0 0 200 100">
  <g transform="translate(10, 0)">
    <rect x="0" y="0" width="100" height="40" rx="5"/>
    <circle cx="150" cy="50" r="20"/>
    <path d="M 10 60 h 40 v 30 h -40 z M 20 70 l 10 0 l 0 10 l -10 0 Z"/>
  </g>
  <g id="hidden" style="display:none"><rect width="10" height="10"/></g>
</svg>"""

DXF = "\n".join([
    "0", "SECTION", "2", "ENTITIES",
    # a 10 mm square drawn as four loose LINEs
    "0", "LINE", "8", "0", "10", "0", "20", "0", "11", "10", "21", "0",
    "0", "LINE", "8", "0", "10", "10", "20", "0", "11", "10", "21", "10",
    "0", "LINE", "8", "0", "10", "10", "20", "10", "11", "0", "21", "10",
    "0", "LINE", "8", "0", "10", "0", "20", "10", "11", "0", "21", "0",
    "0", "CIRCLE", "8", "holes", "10", "5", "20", "5", "40", "2",
    # a circle of diameter 10 as a closed polyline of two bulges
    "0", "LWPOLYLINE", "8", "0", "90", "2", "70", "1",
    "10", "20", "20", "0", "42", "1", "10", "30", "20", "0", "42", "1",
    "0", "ENDSEC", "0", "EOF", ""])


def _box(outline):
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    return min(xs), max(xs), min(ys), max(ys)


def test_svg_units_viewbox_transform_and_flip():
    outs = svgdxf.svg_outlines_from_root(ET.fromstring(SVG), segments=32)
    assert len(outs) == 4                          # the hidden rect is not
    rect = outs[0]
    # 200 user units over 100 mm: the 100-wide rect is 50 mm, moved 5 mm;
    # y flipped so the top of the page is y = 50
    assert _box(rect) == pytest.approx((5, 55, 30, 50))
    assert abs(mesh.polygon_area(outs[1])) == pytest.approx(
        3.14159 * 100, rel=0.02)


def test_svg_arcs_and_curves_flatten():
    loops = svgdxf.parse_path("M0 0 A 10 10 0 0 1 20 0 Q 25 -5 30 0 "
                              "C 35 5 40 -5 45 0 z", segments=32)
    assert len(loops) == 1 and len(loops[0]) > 20
    xs = [p[0] for p in loops[0]]
    assert max(xs) == pytest.approx(45)


def test_dxf_lines_chain_and_bulges_make_circles():
    outs = svgdxf.dxf_outlines_from_text(DXF, 32)
    areas = sorted(round(abs(mesh.polygon_area(o)), 0) for o in outs)
    assert areas == [12, 78, 100]
    assert len(svgdxf.dxf_outlines_from_text(DXF, 32, layer="holes")) == 1


@pytest.fixture
def drawing(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_text(SVG)
    return str(path)


def test_import_svg_is_a_2d_node_that_extrudes(drawing):
    root, warnings = parse_scad(
        f'linear_extrude(4) translate([2, 3]) import("{drawing}", '
        f'center = true);')
    assert not warnings
    node = next(n for n in root.walk() if n.type == "import_2d")
    assert (node.params["x"], node.params["y"]) == (2.0, 3.0)
    assert node.params["center"] is True
    assert validate(root) == {}
    tris = mesh.tessellate(root)
    zs = {round(v[2], 6) for tri in tris for v in tri}
    assert zs == {0.0, 4.0}
    xs = [v[0] for tri in tris for v in tri]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(2, abs=0.01)


def test_import_2d_round_trips(drawing):
    root, _ = parse_scad(f'linear_extrude(2) import(file = "{drawing}", '
                         f'layer = "top", dpi = 96);')
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert 'import(file = "' in code and 'layer = "top"' in code
    again = DocumentModel()
    again.root = parse_scad(code)[0]
    assert again.to_scad() == code


def test_a_hole_in_the_drawing_stays_open(drawing):
    root, _ = parse_scad(f'linear_extrude(1) import("{drawing}");')
    tris = mesh.tessellate(root)
    # the square with a square hole: no top face covers the hole's centre
    probe = (5 + 12.5, 50 - 37.5)                # hole centre in mm
    top = [t for t in tris if all(abs(v[2] - 1) < 1e-9 for v in t)]
    from khervecad.mesh import _inside
    assert not any(_inside(probe, [(v[0], v[1]) for v in t]) for t in top)


def test_surface_from_a_dat_matrix(tmp_path):
    dat = tmp_path / "hills.dat"
    dat.write_text("# heights\n1 2 3\n4 5 6\n")
    root, warnings = parse_scad(f'surface(file = "{dat}", center = true);')
    assert not warnings
    node = root.children[0]
    assert node.type == "surface" and node.params["center"] is True
    assert validate(root) == {}
    tris = mesh.tessellate(root)
    zs = [v[2] for tri in tris for v in tri]
    assert (min(zs), max(zs)) == (0.0, 6.0)      # base one below the lowest
    xs = [v[0] for tri in tris for v in tri]
    assert (min(xs), max(xs)) == (-1.0, 1.0)
    from khervecad import analysis
    props = analysis.mass_properties(tris)
    assert props["volume"] > 0                    # closed and outward


def test_surface_from_a_picture_is_luminance(tmp_path, app=None):
    from PyQt5.QtGui import QColor, QImage
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    image = QImage(3, 2, QImage.Format_RGB888)
    image.fill(QColor("black"))
    image.setPixelColor(0, 0, QColor("white"))       # top-left
    path = str(tmp_path / "map.png")
    image.save(path)
    grid = scadfiles.read_heights(path)
    assert grid[1][0] == pytest.approx(100)          # top row is +y
    assert grid[0][0] == pytest.approx(0)
    assert scadfiles.read_heights(path, invert=True)[1][0] == \
        pytest.approx(0)


def test_surface_round_trips_and_missing_file_is_red(tmp_path):
    root, _ = parse_scad('surface("nowhere.dat", invert = true);')
    model = DocumentModel()
    model.root = root
    code = model.to_scad()
    assert 'surface(file = "nowhere.dat", invert = true);' in code
    assert "file not found" in validate(root)[root.children[0].id]


def test_amf_mesh_parses_with_units(tmp_path):
    from khervecad.engine import MESH_EXTS, parse_mesh
    amf = tmp_path / "tri.amf"
    amf.write_text('''<?xml version="1.0"?><amf unit="inch"><object id="0">
      <mesh><vertices>
        <vertex><coordinates><x>0</x><y>0</y><z>0</z></coordinates></vertex>
        <vertex><coordinates><x>1</x><y>0</y><z>0</z></coordinates></vertex>
        <vertex><coordinates><x>0</x><y>1</y><z>0</z></coordinates></vertex>
      </vertices><volume><triangle><v1>0</v1><v2>1</v2><v3>2</v3></triangle>
      </volume></mesh></object></amf>''')
    assert ".amf" in MESH_EXTS
    tris = parse_mesh(str(amf))
    assert tris == [((0, 0, 0), (25.4, 0, 0), (0, 25.4, 0))]


def test_a_csg_file_imports_through_the_scad_parser():
    csg = """group() {
        multmatrix([[1, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) {
            cube(size = [2, 2, 2], center = false);
        }
    }"""
    root, warnings = parse_scad(csg)
    assert not warnings
    assert [n.type for n in root.walk()][1:] == ["union", "multmatrix", "cube"]
    xs = [v[0] for tri in mesh.tessellate(root) for v in tri]
    assert (min(xs), max(xs)) == (10, 12)

"""The Blueprint window: the drawing helpers it stands on, the automatic
sheet, alignment, the tools, undo, persistence in the .kcad and every
export.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from khervecad import blueprint, blueprint_export, document, drawing, mesh
from khervecad import blueprint_items as bi
from khervecad.model import CadNode

#: a plate with an upright wall, a Ø18 boss and three Ø6 pins
PART = """
cube([80, 50, 10]);
translate([0, 0, 10]) cube([10, 50, 40]);
translate([45, 25, 10]) cylinder(h=20, r=9, $fn=48);
translate([20, 12, 10]) cylinder(h=6, r=3, $fn=32);
translate([70, 12, 10]) cylinder(h=6, r=3, $fn=32);
translate([70, 38, 10]) cylinder(h=6, r=3, $fn=32);
"""


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad import scadparse
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1000, 700)
    win._confirm_discard = lambda: True
    root, _warnings = scadparse.parse_scad(PART)
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    yield win
    bp = getattr(win, "_blueprint", None)
    if bp is not None:
        bp.close()
    win._dirty = False
    win.close()


@pytest.fixture
def bp(window):
    win = blueprint.open_blueprint(window)
    win.sheet.resetTransform()
    win.sheet.scale(4.0, 4.0)                  # 9 px snap = 2.25 mm
    return win


def _dims(bp):
    return {(n.view.data.get("name"), n.label()) for n in bp.scene.notes()
            if n.KIND == "dim"}


def _at(view, u, v):
    """Sheet point of model (u, v) in *view*."""
    return view.mapToScene(QPointF(*view.to_local((u, v))))


# ── the geometry underneath ─────────────────────────────────────────

def test_round_edges_are_found_and_polygons_are_not(app):
    def on_rim(deg):
        a = math.radians(deg)
        return math.cos(a) * 9 + 45, math.sin(a) * 9 + 25
    ring = [(on_rim(i * 7.5), on_rim((i + 1) * 7.5)) for i in range(48)]
    (circle,) = drawing.find_circles(ring)
    assert circle["closed"]
    assert circle["r"] == pytest.approx(9.0, abs=0.05)
    assert circle["centre"][0] == pytest.approx(45.0, abs=0.05)
    hexagon = [((math.cos(math.radians(a)) * 5, math.sin(math.radians(a))
                 * 5), (math.cos(math.radians(a + 60)) * 5,
                        math.sin(math.radians(a + 60)) * 5))
               for a in range(0, 360, 60)]
    assert drawing.find_circles(hexagon) == []        # a nut, not a hole


def test_collinear_chords_merge_into_one_line(app):
    run = [((i, 0.0), (i + 1.0, 0.0)) for i in range(10)]
    assert drawing.merge_collinear(run) == [((0.0, 0.0), (10.0, 0.0))]


def test_clipping_and_hatching(app):
    (seg,) = drawing.clip_to_circle([((-10.0, 0.0), (10.0, 0.0))], (0, 0), 4)
    assert seg == ((-4.0, 0.0), (4.0, 0.0))
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole = [(3, 3), (7, 3), (7, 7), (3, 7)]
    for a, b in drawing.hatch_segments([square, hole], 1.0):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        assert not (3.05 < mx < 6.95 and 3.05 < my < 6.95)


def test_title_block_cells_fit_the_block(app):
    cells = drawing.title_block_cells({"title": "Bracket"}, "1:2", "A3")
    for cell in cells:
        x, y, w, h = cell["rect"]
        assert x + w <= drawing.TITLE_W + 1e-6
        assert y + h <= drawing.TITLE_H + 1e-6
    assert {c["key"] for c in cells} >= {"title", "material", "mass",
                                         "scale", "projection", "number"}


def test_a_cylinders_sides_are_not_hidden_behind_itself(app):
    """The depth grid's cell beside a curved silhouette lands on a facet
    seen edge-on, a tolerance in front of the edge: the sides of every
    cylinder used to be drawn dashed."""
    for segments in (48, 45):
        tris = mesh.tessellate(CadNode("cylinder", "c", dict(
            height=20, radius_bottom=9, radius_top=9, segments=segments)))
        for view in ("Front", "Right", "Left", "Back"):
            assert drawing.view_lines(tris, view)["hidden"] == [], \
                (segments, view)
    # at 45 segments the isometric silhouette sits past a grazing quad:
    # one side of a boss on a plate used to vanish from the drawing
    root = CadNode("root")
    root.add(CadNode("cube", "plate", dict(width=80, depth=50, height=10)))
    root.add(CadNode("cylinder", "boss", dict(
        x=45, y=25, z=10, height=20, radius_bottom=9, radius_top=9,
        segments=45)))
    tris = mesh.tessellate(root)
    lines = drawing.view_lines(tris, "Isometric")
    tall = [s for s in lines["visible"] if abs(s[0][0] - s[1][0]) < 1e-6
            and abs(s[0][1] - s[1][1]) > 5.0]
    # the plate's three vertical corners and the boss's two sides
    assert len(tall) >= 5
    assert not [s for s in lines["hidden"] if abs(s[0][0] - s[1][0])
                < 1e-6 and abs(s[0][1] - s[1][1]) > 5.0 and
                s[0][1] > 0]


# ── the sheet it makes by itself ─────────────────────────────────────

def test_first_open_lays_out_dimensions_and_fills_the_title(bp):
    scene = bp.scene
    names = {v.data.get("name") for v in scene.views.values()}
    assert names == {"Front", "Top", "Right", "Isometric"}
    front, top, right = (scene.projected(n) for n in ("Front", "Top",
                                                      "Right"))
    assert top.pos().x() == pytest.approx(front.pos().x())
    assert top.pos().y() < front.pos().y()                  # above it
    assert right.pos().y() == pytest.approx(front.pos().y())
    assert scene.scale in drawing.SCALES
    dims = _dims(bp)
    assert ("Front", "80") in dims and ("Front", "50") in dims
    assert ("Top", "Ø18") in dims and ("Top", "3× Ø6") in dims
    marks = [n for n in scene.notes() if n.KIND == "centre_mark"]
    assert len(marks) == 4
    shown = scene.display_fields()
    assert shown["material"] == "PLA" and shown["mass"].endswith(" g")
    assert bp.model.drawing and bp.model.drawing["views"]   # saved


def test_hole_labels_land_off_the_part(bp):
    top = bp.scene.projected("Top")
    outline = top.mapRectToScene(top.content_rect())
    for note in bp.scene.notes():
        if note.KIND == "dim" and note.data["kind"] == "diameter":
            label = note.prims[-1]
            at = note.mapToScene(QPointF(*label[2]))
            assert not outline.contains(at), note.label()


def test_top_stays_aligned_and_front_carries_the_others(bp):
    scene = bp.scene
    front, top, right = (scene.projected(n) for n in ("Front", "Top",
                                                      "Right"))
    top.setPos(top.pos() + QPointF(30.0, -5.0))
    assert top.pos().x() == pytest.approx(front.pos().x())
    before_top_y = top.pos().y()
    front.setPos(front.pos() + QPointF(12.0, 7.0))
    assert top.pos().x() == pytest.approx(front.pos().x())
    assert top.pos().y() == pytest.approx(before_top_y + 7.0)
    assert right.pos().y() == pytest.approx(front.pos().y())


def test_a_dimension_measures_the_model_not_the_paper(bp):
    scene = bp.scene
    front = scene.projected("Front")
    item = scene.add_note({"type": "dim", "kind": "aligned",
                           "a": [0.0, 0.0], "b": [80.0, 50.0]}, front)
    assert item.label() == bi.fmt(math.hypot(80, 50))
    scene.set_scale(0.5)
    assert item.label() == bi.fmt(math.hypot(80, 50))
    assert drawing.scale_label(scene.scale) == "1:2"
    assert scene.title.data["scale_label"] == "1:2"


# ── the tools ────────────────────────────────────────────────────────

def test_smart_dimension_between_two_corners(bp):
    front = bp.scene.projected("Front")
    before = len(bp.scene.notes())
    bp.set_tool("dim_smart")
    bp.tool.press(_at(front, 0.0, 0.0))
    bp.tool.press(_at(front, 80.0, 0.0))
    below = _at(front, 40.0, -30.0)
    bp.tool.move(below)
    bp.tool.press(below)
    added = bp.scene.notes()[before:]
    assert [(n.data["kind"], n.label()) for n in added] == [
        ("horizontal", "80")]


def test_smart_dimension_on_a_rim_is_a_diameter(bp):
    top = bp.scene.projected("Top")
    before = len(bp.scene.notes())
    bp.set_tool("dim_smart")
    bp.tool.press(_at(top, 45.0, 34.0))                # on the Ø18 rim
    bp.tool.press(_at(top, 70.0, 60.0))
    (note,) = bp.scene.notes()[before:]
    assert note.label() == "Ø18"


def test_angle_between_two_edges(bp):
    iso = bp.scene.projected("Front")
    bp.set_tool("dim_angle")
    bp.tool.press(_at(iso, 40.0, 0.0))                 # bottom edge
    bp.tool.press(_at(iso, 0.0, 30.0))                 # left edge
    bp.tool.press(_at(iso, 15.0, 15.0))
    note = bp.scene.notes()[-1]
    assert note.data["kind"] == "angle" and note.label() == "90°"


def test_notes_and_symbols(bp, monkeypatch):
    monkeypatch.setattr(bp, "ask_text", lambda *a, **k: "BREAK EDGES")
    monkeypatch.setattr(bp, "ask_choice", lambda *a, **k: "Ra 1.6")
    monkeypatch.setattr(bp, "ask_fcf", lambda: {
        "symbol": "flatness", "tolerance": "0.05", "datums": "A"})
    front = bp.scene.projected("Front")
    for key in ("leader", "balloon", "datum", "fcf"):
        bp.set_tool(key)
        bp.tool.press(_at(front, 80.0, 5.0))
        bp.tool.press(_at(front, 95.0, 20.0))
    bp.set_tool("finish")
    bp.tool.press(_at(front, 40.0, 10.0))
    kinds = [n.KIND for n in bp.scene.notes()[-5:]]
    assert kinds == ["leader", "balloon", "datum", "fcf", "finish"]
    leader, balloon, datum, fcf, finish = bp.scene.notes()[-5:]
    assert leader.data["text"] == "BREAK EDGES"
    assert balloon.data["number"] == "1" and datum.data["letter"] == "A"
    assert fcf.data["symbol"] == "flatness" and finish.data["ra"] == "Ra 1.6"
    for note in (leader, balloon, datum, fcf, finish):
        assert note.prims, note.KIND


def test_undo_and_redo(bp, monkeypatch):
    monkeypatch.setattr(bp, "ask_text", lambda *a, **k: "HELLO")
    count = len(bp.scene.notes())
    bp.set_tool("text")
    bp.tool.press(QPointF(40.0, 40.0))
    assert len(bp.scene.notes()) == count + 1
    bp.undo_stack.undo()
    assert len(bp.scene.notes()) == count
    assert len(bp.model.drawing["notes"]) == count      # saved too
    bp.undo_stack.redo()
    assert [n.data.get("text") for n in bp.scene.notes()][-1] == "HELLO"


def test_deleting_a_view_takes_its_dimensions(bp):
    top = bp.scene.projected("Top")
    top.setSelected(True)
    bp.delete_selected()
    assert bp.scene.projected("Top") is None
    assert all(n.view is not top for n in bp.scene.notes())


def test_sections_details_pictures_and_the_parts_list(bp):
    section = bp.add_section("y")
    assert section.outlines and section.label_text() == "SECTION A-A"
    assert any(isinstance(m, bi.CuttingLineItem) for m in bp.scene.derived)
    front = bp.scene.projected("Front")
    detail = bp.add_detail(front, (45.0, 20.0), 12.0)
    assert detail.scale_ == pytest.approx(bp.scene.scale * 2.0)
    assert detail.label_text() == "DETAIL B"
    for a, b in detail.lines["visible"]:
        for u, v in (a, b):
            assert math.hypot(u - 45.0, v - 20.0) <= 12.0 + 1e-6
    shaded = bp.add_shaded()
    assert shaded.image is not None
    bp.add_bom()
    (bom,) = [n for n in bp.scene.notes() if n.KIND == "bom"]
    assert bom.data["rows"][0][2] == "1"


def test_the_material_sets_the_mass(bp):
    title = bp.scene.title
    pla = bp.scene.display_fields()["mass"]
    bp.set_field(title, "material", "Aluminium")
    alu = bp.scene.display_fields()["mass"]
    assert float(alu.split()[0]) == pytest.approx(
        float(pla.split()[0]) * 2.70 / 1.24, rel=0.01)
    bp.set_field(title, "mass", "250 g")                  # typed wins
    assert bp.scene.title.data["fields"]["mass"] == "250 g"


# ── saved with the document ──────────────────────────────────────────

def test_the_sheet_round_trips_through_the_kcad(bp, tmp_path):
    front = bp.scene.projected("Front")
    bp.add_note({"type": "dim", "kind": "horizontal", "a": [10.0, 0.0],
                 "b": [45.0, 0.0], "offset": 20.0}, front)
    path = tmp_path / "part.kcad"
    document.save_kcad(bp.model, str(path))
    from khervecad.model import DocumentModel
    other = DocumentModel()
    document.load_kcad(other, str(path))
    assert other.drawing == bp.model.drawing
    scene = blueprint.BlueprintScene()
    scene.geometry = bp.scene.geometry
    scene.load_state(other.drawing)
    assert sorted(n.label() for n in scene.notes() if n.KIND == "dim") == \
        sorted(n.label() for n in bp.scene.notes() if n.KIND == "dim")


def test_opening_another_document_shows_its_sheet(bp, window):
    window.model.clear()
    assert window.model.drawing is None or not window.model.drawing.get(
        "notes")


# ── output ───────────────────────────────────────────────────────────

def test_every_format_is_written(bp, tmp_path):
    for ext in ("pdf", "svg", "png", "dxf"):
        path = tmp_path / f"part.{ext}"
        blueprint_export.export(bp.scene, str(path))
        assert path.stat().st_size > 1000, ext
    dxf = (tmp_path / "part.dxf").read_text()
    for token in ("TABLES", "HIDDEN", "CENTER", "VISIBLE", "%%c18",
                  "SOLID", "CIRCLE"):
        assert token in dxf, token
    assert dxf.rstrip().endswith("EOF")
    image = QImage(str(tmp_path / "part.png"))
    assert image.width() == int(bp.scene.W * 8)
    with pytest.raises(ValueError):
        blueprint_export.export(bp.scene, str(tmp_path / "part.txt"))


def test_blueprint_blue(bp):
    bp.style_combo.setCurrentIndex(bp.style_combo.findData("blueprint"))
    bp._style_chosen(0)
    image = blueprint_export.to_image(bp.scene, 2.0)
    corner = image.pixelColor(30, 30)
    assert corner.blue() > corner.red() + 60
    assert bp.model.drawing["style"] == "blueprint"


def test_the_export_leaves_no_selection_or_marker(bp, tmp_path):
    front = bp.scene.projected("Front")
    front.setSelected(True)
    bp.scene.marker.show_at(QPointF(10, 10), "end")
    with bp.scene.exporting():
        assert not front.isSelected()
        assert not bp.scene.marker.isVisible()
    assert front.isSelected() and bp.scene.marker.isVisible()


def test_mcp_exports_the_users_sheet(bp, window, tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    front = bp.scene.projected("Front")
    bp.add_note({"type": "leader", "tip": [80.0, 5.0], "at": [10, -10],
                 "text": "DEBURR ALL EDGES"}, front)
    ex = McpToolExecutor(window)
    out = ex.execute("export_drawing", {"path": str(tmp_path / "s.dxf")})
    assert out.get("blueprint") is True, out
    assert "DEBURR ALL EDGES" in (tmp_path / "s.dxf").read_text()
    fresh = ex.execute("export_drawing", {"path": str(tmp_path / "f.dxf"),
                                          "blueprint": False})
    assert "blueprint" not in fresh and fresh["views"]


# ── in the main window ───────────────────────────────────────────────

def test_the_file_menu_and_toolbar_open_it(window):
    file_menu = next(a.menu() for a in window.menuBar().actions()
                     if a.text() == "&File")
    action = next(a for a in file_menu.actions() if "Blueprint" in a.text())
    assert action.shortcut().toString() == "Ctrl+Shift+D"
    tool = next(a for a in window._options_bar.actions()
                if a.text() == "Blueprint")
    assert tool.toolTip().startswith("<table")
    action.trigger()
    assert window._blueprint.isVisible()

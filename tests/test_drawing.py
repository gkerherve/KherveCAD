"""2D drawings: projection, hidden lines, layout, the writers, the
dialog's layout helper and the MCP tool.

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
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import drawing, drawing_export, mesh
from khervecad.model import CadNode


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _cube(w=20.0, d=30.0, h=10.0):
    return mesh.tessellate(CadNode("cube", "c", dict(width=w, depth=d,
                                                     height=h)))


def _length(seg):
    (a, b) = seg
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def test_front_view_of_a_box_is_its_outline(app):
    lines = drawing.view_lines(_cube(), "Front")
    assert lines["bounds"] == (0.0, 0.0, 20.0, 10.0)      # X by Z
    # four visible edges of 20 or 10 mm, and nothing hidden; the back
    # face's edges coincide with the front's, so they are seen too
    assert lines["hidden"] == []
    lengths = sorted(round(_length(s), 3) for s in lines["visible"])
    assert set(lengths) <= {10.0, 20.0}
    assert len(lengths) >= 4


def test_a_hole_shows_as_hidden_lines_in_the_side_view(app):
    # a block with a box tunnel through it along X: from the front the
    # tunnel's edges are behind the front face -> hidden (dashed)
    root = CadNode("root")
    diff = CadNode("difference", "d")
    diff.add(CadNode("cube", "a", dict(width=40, depth=40, height=40)))
    diff.add(CadNode("cube", "b", dict(x=-1, y=15, z=15, width=42,
                                       depth=10, height=10)))
    root.add(diff)
    # the fallback tessellator keeps only the first operand, so build
    # the tunnel as real geometry instead: two slabs and two walls
    tris = []
    for kw in (dict(width=40, depth=40, height=15),
               dict(z=25, width=40, depth=40, height=15),
               dict(y=0, z=15, width=40, depth=15, height=10),
               dict(y=25, z=15, width=40, depth=15, height=10)):
        tris += mesh.tessellate(CadNode("cube", "p", kw))
    # from the front the tunnel's walls end on the front face, whose own
    # edges are visible at the same place: nothing dashed
    lines = drawing.view_lines(tris, "Front")
    assert lines["hidden"] == []
    top = drawing.view_lines(tris, "Top")
    # from above the tunnel is covered by the top slab: its two walls
    # show as dashed lines at y = 15 and y = 25
    ys = sorted({round(s[0][1], 3) for s in top["hidden"]
                 if abs(s[0][1] - s[1][1]) < 1e-6})
    assert ys == [15.0, 25.0]
    assert drawing.view_lines(tris, "Top", hidden_lines=False)["hidden"] \
        == []


def test_layout_places_third_angle_views_and_picks_a_scale(app):
    lay = drawing.layout(_cube(200, 100, 50), sheet="A4", title="Block")
    names = [v["name"] for v in lay["views"]]
    assert names == ["Front", "Top", "Right", "Isometric"]
    by = {v["name"]: v for v in lay["views"]}
    assert by["Top"]["x"] == pytest.approx(by["Front"]["x"])   # aligned
    assert by["Top"]["y"] > by["Front"]["y"]                    # above
    assert by["Right"]["y"] == pytest.approx(by["Front"]["y"])
    assert by["Right"]["x"] > by["Front"]["x"]
    assert lay["scale"] in drawing.SCALES and lay["scale"] <= 1.0
    assert lay["scale_label"].startswith("1:")
    # every placed view lies inside the sheet's frame
    for v in lay["views"]:
        b = v["lines"]["bounds"]
        assert v["x"] >= lay["margin"]
        assert v["x"] + (b[2] - b[0]) * lay["scale"] <= lay["width"]
        assert v["y"] + (b[3] - b[1]) * lay["scale"] <= lay["height"]
    dims = by["Front"]["dims"]
    assert [d["text"] for d in dims] == ["200", "50"]


def test_section_view_is_hatched_material(app):
    lay = drawing.layout(_cube(), section_axis="y", views=("Front",))
    sec = next(v for v in lay["views"] if v.get("section"))
    assert sec["name"] == "Section Y"
    assert sec["section"]["area"] == pytest.approx(200.0)      # 20 x 10


def test_every_writer_writes_a_file(app, tmp_path):
    lay = drawing.layout(_cube(), section_axis="z", title="Cube")
    for ext in ("pdf", "svg", "png", "dxf"):
        path = tmp_path / f"cube.{ext}"
        drawing_export.export(lay, str(path))
        assert path.stat().st_size > 200, ext
    dxf = (tmp_path / "cube.dxf").read_text()
    assert "VISIBLE" in dxf and "SECTION" in dxf and "Cube" in dxf
    assert dxf.rstrip().endswith("EOF")
    with pytest.raises(ValueError):
        drawing_export.export(lay, str(tmp_path / "cube.txt"))


def test_dialog_helper_and_mcp_tool(app, tmp_path):
    from khervecad import drawing_dialog
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        win._confirm_discard = lambda: True
        win.model.add_node("cube", dict(width=30, depth=20, height=10))
        lay = drawing_dialog.make_layout(win, views=("Front", "Top"))
        assert [v["name"] for v in lay["views"]] == ["Front", "Top"]
        ex = McpToolExecutor(win)
        out = ex.execute("export_drawing",
                         {"path": str(tmp_path / "d.dxf"),
                          "section": "y", "views": ["Front"]})
        assert out.get("exported", "").endswith("d.dxf"), out
        assert out["views"] == ["Front", "Section Y"]
        bad = ex.execute("export_drawing", {"path": str(tmp_path / "d.stl")})
        assert "error" in bad
    finally:
        win._dirty = False
        win.close()

"""Paint from photo: the PNG reader, the projection, the node, its
codegen and round trip, and the picture path saved relative.

Run with: python -m pytest tests/  (offscreen Qt).

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

from khervecad import document, mesh, paint, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def halves(app, tmp_path):
    """A 40x20 PNG: left half red, right half blue, a green top-left
    pixel to pin the orientation."""
    from PyQt5.QtGui import QColor, QImage
    image = QImage(40, 20, QImage.Format_RGB888)
    for y in range(20):
        for x in range(40):
            image.setPixelColor(x, y, QColor("#ff0000" if x < 20
                                             else "#0000ff"))
    image.setPixelColor(0, 0, QColor("#00ff00"))
    path = tmp_path / "halves.png"
    image.save(str(path))
    return str(path)


def test_the_png_reader_reads_rgb_rgba_grey_and_palette(app, tmp_path):
    from PyQt5.QtGui import QColor, QImage
    for fmt in (QImage.Format_RGB888, QImage.Format_ARGB32,
                QImage.Format_Grayscale8, QImage.Format_Indexed8):
        image = QImage(8, 4, QImage.Format_ARGB32)
        image.fill(QColor("#336699"))
        image.setPixelColor(7, 3, QColor("#ffffff"))
        image = image.convertToFormat(fmt)
        path = tmp_path / f"f{int(fmt)}.png"
        assert image.save(str(path))
        picture = paint.read_png(path)
        assert (picture.width, picture.height) == (8, 4)
        top_left = picture.rows[0][0]
        if fmt == QImage.Format_Grayscale8:
            assert top_left[0] == top_left[1] == top_left[2]
        else:
            assert top_left == (0x33, 0x66, 0x99)
        assert picture.rows[3][7] == (255, 255, 255)
    with pytest.raises(ValueError):
        paint.read_png(Path(__file__))


def test_sampling_is_t_up_and_the_loader_caches(halves):
    picture = paint.load(halves)
    assert picture is not None and picture.aspect == pytest.approx(0.5)
    assert picture.at(0.25, 0.5) == "#ff0000"
    assert picture.at(0.75, 0.5) == "#0000ff"
    assert picture.at(0.01, 0.99) == "#00ff00"        # top-left, t up
    assert picture.at(1.2, 0.5) == "" and picture.at(0.5, -0.1) == ""
    assert paint.load(halves) is picture
    assert paint.load(halves + ".missing") is None


def test_paint_colours_faces_by_their_projection(halves):
    from khervecad.model import CadNode
    root = CadNode("root", "root")
    root.add(CadNode("cube", "c", dict(x=-20.0, y=-5.0, z=0.0, width=40.0,
                                       depth=10.0, height=20.0)))
    items = [(t, ("#aaaaaa", 0.5, "Matte"), False)
             for t in mesh.tessellate(root)]
    picture = paint.load(halves)
    out = paint.paint(items, picture, "Front (XZ)", -20.0, 0.0, 40.0)
    for tri, colour, _sel in out:
        cx = sum(v[0] for v in tri) / 3
        expect = "#ff0000" if cx < 0 else "#0000ff"
        assert colour == (expect, 0.5, "Matte")       # alpha, material kept
    # a picture covering only the right half leaves the rest alone
    part = paint.paint(items, picture, "Front (XZ)", 0.0, 0.0, 20.0)
    kept = [c for t, c, _s in part if sum(v[0] for v in t) / 3 < 0]
    assert kept and all(c == ("#aaaaaa", 0.5, "Matte") for c in kept)
    # no picture, no colour of its own: the photo's colour with alpha 1
    plain = paint.paint([(t, None, False) for t in mesh.tessellate(root)],
                        picture, "Front (XZ)", -20.0, 0.0, 40.0)
    assert plain[0][1][1] == 1.0
    assert paint.paint(items, None, "Front (XZ)", 0, 0, 40) is items


def test_the_paint_node_previews_bakes_and_round_trips(app, halves, tmp_path):
    doc = DocumentModel()
    cube = doc.add_node("cube", dict(x=-20.0, y=-5.0, width=40.0,
                                     depth=10.0, height=20.0))
    node = doc.wrap_nodes([cube], "paint")
    node.params.update(image=halves, plane="Front (XZ)", x=-20.0, y=0.0,
                       width=40.0)
    assert node.id not in validate(doc.root)
    colours = {c[0] for _t, c in mesh.tessellate_colored(doc.root) if c}
    assert colours == {"#ff0000", "#0000ff"}
    code = doc.to_scad()
    assert 'kcad_paint(image = "' in code and 'plane = "Front (XZ)"' in code
    assert "module kcad_paint(" in code
    path = tmp_path / "paint.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    back = next(n for n in other.root.walk() if n.type == "paint")
    assert back.params["image"] == halves and back.params["width"] == 40
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["image"] = ""
    assert "choose" in validate(doc.root)[node.id]
    node.params["image"] = str(tmp_path / "gone.png")
    assert "not found" in validate(doc.root)[node.id]


def test_the_picture_path_saves_relative_and_resolves(app, halves, tmp_path):
    doc = DocumentModel()
    cube = doc.add_node("cube")
    node = doc.wrap_nodes([cube], "paint")
    node.params["image"] = halves
    kcad = tmp_path / "model.kcad"
    document.save_kcad(doc, str(kcad))
    assert '"image": "halves.png"' in kcad.read_text()
    loaded = DocumentModel()
    document.load_kcad(loaded, str(kcad))
    back = next(n for n in loaded.root.walk() if n.type == "paint")
    assert back.params["image"] == halves


def test_paint_is_a_character_tool_with_a_tip(app):
    from khervecad import toolbars, tooltips
    assert "paint" in dict(toolbars.OPERATION_GROUPS)["character"]
    assert "Paint" in tooltips.TIPS["paint"][0]

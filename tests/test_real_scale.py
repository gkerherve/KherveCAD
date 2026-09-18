"""The scale bar measures the real thing: a document is 1 : N of what it
models (a 60 mm Earth is 1 : 212 600 000), the bar then reads
kilometres of planet and writes the ratio under itself, a true-size map
reads metres and kilometres instead of 200000 mm, and the scale rides
in the file and the undo history like the unit does.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, library, scalebar, units
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("value,unit,want", [
    (250, "mm", "250 mm"), (200_000, "mm", "200 m"),
    (5e9, "mm", "5000 km"), (5e10, "mm", "50 000 km"),
    (0.5, "um", "0.5 µm"), (20, "nm", "20 nm"), (500, "cm", "5 m"),
    (0.5, "m", "0.5 m"), (12, "in", "12 in")])
def test_the_bar_says_lengths_in_a_unit_that_reads(value, unit, want):
    assert scalebar.label(value, unit).replace(" ", " ") == want


def test_ratios_read_and_write_like_a_map():
    assert units.ratio_text(212_604_567).replace(" ", " ") == \
        "1 : 212 600 000"
    assert units.ratio_text(1.0) == "1 : 1"
    assert units.ratio_text(0.04) == "25 : 1"
    assert units.parse_ratio("1 : 2.5e8") == 2.5e8
    assert units.parse_ratio("1:250 000 000") == 2.5e8
    assert units.parse_ratio("25:1") == 0.04
    assert units.parse_ratio("212600000") == 212_600_000
    for bad in ("", "abc", "0:1", "1:-5"):
        with pytest.raises(ValueError):
            units.parse_ratio(bad)


def test_a_scale_model_bar_measures_the_real_thing():
    # 60 mm across on screen at 5 px/mm: a 5000 km bar, ~118 px
    n = 2 * 6378.137e6 / 60.0
    length, px = scalebar.real_length(5.0, n)
    assert length == 5e9 and 60 <= px <= 170
    assert scalebar.label(length, "mm") == "5000 km"
    # life size: the model's own length, as before
    assert scalebar.real_length(5.0) == (20.0, 100.0)


def test_a_planet_sets_the_scale_of_an_empty_document(app):
    doc = DocumentModel()
    note = library.prepare_document(doc, "body_earth", {"d": 60.0})
    assert doc.real_scale == pytest.approx(212_604_567, rel=1e-4)
    assert "212" in note
    # a document with something in it keeps its scale
    doc.root.add(library.build_part("body_earth", {"d": 60.0}))
    before = doc.real_scale
    note = library.prepare_document(doc, "body_moon", {"d": 30.0})
    assert doc.real_scale == before
    assert "stays" in note and "Moon" in note
    # a house document is never relabelled by a planet
    other = DocumentModel()
    other.add_node("cube")
    library.prepare_document(other, "body_mars", {"d": 60.0})
    assert other.real_scale == 1.0


def test_the_scale_saves_undoes_and_resets(app, tmp_path):
    doc = DocumentModel()
    doc.set_real_scale("1 : 250000000")
    assert doc.real_scale == 2.5e8
    path = tmp_path / "planet.kcad"
    document.save_kcad(doc, str(path))
    back = DocumentModel()
    document.load_kcad(back, str(path))
    assert back.real_scale == 2.5e8
    # an older file (no key) opens at life size
    legacy = DocumentModel()
    legacy.set_real_scale(7.0)
    import json
    data = json.loads(path.read_text())
    data.pop("real_scale")
    path.write_text(json.dumps(data))
    document.load_kcad(legacy, str(path))
    assert legacy.real_scale == 1.0
    # undo brings the previous scale back
    doc2 = DocumentModel()
    doc2._capture()
    doc2.set_real_scale(1000.0)
    doc2._capture()
    doc2.undo_stack.undo()
    assert doc2.real_scale == 1.0
    doc2.set_real_scale(500.0)
    doc2.clear()
    assert doc2.real_scale == 1.0


def test_mcp_sets_and_reports_the_scale(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()                      # never closed (asks to discard)
    ex = McpToolExecutor(win)
    result = ex.execute("set_render_options", {"real_scale": 212600000})
    assert result["real_scale"] == 212600000
    assert win.view3d.real_scale == 212600000
    info = ex.execute("get_document_info", {})
    assert info["scale"].replace(" ", " ") == "1 : 212 600 000"
    bad = ex.execute("set_render_options", {"real_scale": -3})
    assert "error" in bad

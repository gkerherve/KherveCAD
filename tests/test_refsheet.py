"""The blueprint cutter: trims each view to its drawing, mirrors on
request and places it at true size.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad.tools import refsheet


@pytest.fixture
def sheet(tmp_path):
    """A white sheet with a 'side view' (a 200×80 px black body plus a
    red nose on its left) and a 'front view' (a 90×80 px block)."""
    from PyQt5.QtCore import QRect
    from PyQt5.QtGui import QColor, QImage, QPainter
    refsheet._app()
    img = QImage(400, 200, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.fillRect(QRect(40, 60, 200, 80), QColor("black"))
    p.fillRect(QRect(40, 90, 10, 10), QColor("red"))        # the nose
    p.fillRect(QRect(290, 60, 90, 80), QColor("black"))
    p.end()
    path = tmp_path / "car.png"
    img.save(str(path))
    return path


def test_a_loose_box_is_trimmed_to_the_drawing(sheet):
    from PyQt5.QtGui import QImage
    img = QImage(str(sheet)).convertToFormat(QImage.Format_RGB32)
    assert refsheet.trim(img, (10, 20, 270, 180)) == (40, 60, 240, 140)


def test_views_are_saved_mirrored_and_placed_at_true_size(sheet):
    report = refsheet.cut(sheet, [("side", (10, 20, 270, 180), True),
                                  ("front", (275, 20, 395, 180), False)],
                          dict(length=4000.0, width=1800.0, height=1600.0))
    side, front = report
    assert side["pixels"] == [200, 80]
    args = side["set_reference_image"]
    assert args["plane"] == "Front" and args["width"] == 4000.0
    assert args["x"] == -2000.0 and args["y"] == 0.0
    assert side["implied_height"] == 1600.0 and "+0.0 %" in side["check"]
    assert front["set_reference_image"]["plane"] == "Side"
    assert front["set_reference_image"]["width"] == 1800.0
    # mirrored: the red nose moved from the left edge to the right one
    from PyQt5.QtGui import QImage
    view = QImage(side["path"])
    right = view.pixelColor(view.width() - 3, 35)
    left = view.pixelColor(2, 35)
    assert right.red() > 200 and right.green() < 60
    assert left.red() < 60


def test_a_top_view_is_centred_on_the_origin():
    out = refsheet.placement("top", 400, 180,
                             dict(length=4000.0, width=1800.0))
    assert out["plane"] == "Top" and out["y"] == -900.0


def test_bad_input_is_explained():
    with pytest.raises(ValueError, match="unknown view"):
        refsheet.parse_view("roof=1,2,3,4")
    with pytest.raises(ValueError, match="needs --width"):
        refsheet.placement("front", 100, 80, dict(length=4000.0))


def test_the_command_line_prints_a_json_report(sheet, capsys):
    assert refsheet.main([str(sheet), "--view", "front=275,20,395,180",
                          "--width", "1800", "--height", "1600"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report[0]["view"] == "front"
    assert Path(report[0]["path"]).name == "car-front.png"

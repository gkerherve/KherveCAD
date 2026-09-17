"""OpenSCAD Customizer annotations (customizer.py): read into variable
nodes, written back, and turned into working controls in the Variables
sheet."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QLineEdit,
                             QSlider)

from khervecad import customizer, mesh
from khervecad.model import DocumentModel
from khervecad.scadparse import parse_scad

PROGRAM = '''/* [Size] */
// Box width in mm
width = 40;  // [10:5:200]
lid = "snap";  // [snap, screw, none]
wall = 2;  // [1.2:Thin, 2:Normal, 3:Strong]
label = "Box";  // 12
flag = true;
/* [Hidden] */
$fn = 64;
translate([0, 0, 0]) cube([width, width, wall], center=false);
'''


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _model(source=PROGRAM):
    model = DocumentModel()
    model.root = parse_scad(source)[0]
    model.group_variables()
    return model


def _assign(model, name):
    return next(n for n in model.root.walk()
                if n.type == "assign" and n.params["variable"] == name)


def test_annotations_become_params():
    model = _model()
    width = _assign(model, "width")
    assert width.params["options"] == "10:5:200"
    assert width.params["description"] == "Box width in mm"
    assert width.params["group"] == "Size"
    assert _assign(model, "label").params["options"] == "12"
    assert _assign(model, "$fn").params["group"] == "Hidden"
    assert "options" not in _assign(model, "flag").params


def test_program_round_trips_exactly():
    model = _model()
    code = model.to_scad()
    assert code.split("\n", 4)[-1].startswith(PROGRAM)
    assert _model(code).to_scad() == code


def test_geometry_follows_the_variables():
    model = _model()
    cube = next(n for n in model.root.walk() if n.type == "cube")
    assert cube.params["width"] == "width"


def test_widgets():
    model = _model()
    assert customizer.widget(_assign(model, "width")) == \
        {"kind": "slider", "min": 10, "max": 200, "step": 5}
    lid = customizer.widget(_assign(model, "lid"))
    assert lid["kind"] == "dropdown" and lid["items"][1] == ('"screw"',
                                                              "screw")
    assert customizer.widget(_assign(model, "wall"))["items"][0] == \
        ("1.2", "Thin")
    assert customizer.widget(_assign(model, "label")) == \
        {"kind": "text", "max": 12}
    assert customizer.widget(_assign(model, "flag")) == {"kind": "checkbox"}
    assert customizer.hidden(_assign(model, "$fn"))


def test_variables_sheet_controls_drive_the_model(app):
    from khervecad.treepanel import VariablesSheet
    model = _model()
    sheet = VariablesSheet(model)
    rows = {n.params["variable"]: i for i, n in enumerate(sheet._rows)}
    slider = sheet.table.cellWidget(rows["width"], 2)
    assert isinstance(slider, QSlider)
    assert slider.value() == 6                      # (40 - 10) / 5
    slider.setValue(18)                             # 100 mm
    assert _assign(model, "width").params["value"] == 100.0
    assert sheet.table.item(rows["width"], 1).text() == "100.0"
    xs = [v[0] for tri in mesh.tessellate(model.root) for v in tri]
    assert max(xs) == pytest.approx(100)

    combo = sheet.table.cellWidget(rows["lid"], 2)
    assert isinstance(combo, QComboBox) and combo.currentText() == "snap"
    combo.setCurrentIndex(2)
    assert _assign(model, "lid").params["value"] == '"none"'

    wall = sheet.table.cellWidget(rows["wall"], 2)
    assert wall.currentText() == "Normal"

    check = sheet.table.cellWidget(rows["flag"], 2)
    assert isinstance(check, QCheckBox) and check.isChecked()
    check.setChecked(False)
    assert _assign(model, "flag").params["value"] == "false"

    text = sheet.table.cellWidget(rows["label"], 2)
    assert isinstance(text, QLineEdit) and text.maxLength() == 12
    assert sheet.table.cellWidget(rows["$fn"], 2) is None   # Hidden
    assert "lid = \"none\";  // [snap, screw, none]" in model.to_scad()

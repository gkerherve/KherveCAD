"""View ▸ Customizer (customizer_panel.py): the document's annotated
variables as grouped controls that move the model while dragged."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

import pytest
from PyQt5.QtWidgets import QApplication, QGroupBox, QSlider

from khervecad import mesh
from khervecad.scadparse import parse_scad

PROGRAM = '''/* [Motion] */
// Motor shaft angle
angle = 0;  // [0:10:360]
/* [Size] */
// Arm length
arm = 20;  // [10:5:60]
rotate([0, 0, angle]) cube([arm, 2, 2]);
'''


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _window():
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.model.root = parse_scad(PROGRAM)[0]
    win.model.group_variables()
    win.model.structure_changed.emit()
    return win


def test_panel_opens_with_grouped_sliders_that_move_the_model(app):
    win = _window()
    try:
        panel = win._customizer
        assert not win._customizer_dock.isHidden()
        titles = [b.title() for b in panel.body.findChildren(QGroupBox)]
        assert titles == ["Motion", "Size"]
        rows = {n.params["variable"]: control
                for n, _v, control in panel._rows.values()}
        assert isinstance(rows["arm"], QSlider)
        rows["arm"].setValue(rows["arm"].maximum())            # 60 mm
        xs = [v[0] for t in mesh.tessellate(win.model.root) for v in t]
        assert max(xs) == pytest.approx(60)
        rows["angle"].setValue(9)                              # 90 degrees
        ys = [v[1] for t in mesh.tessellate(win.model.root) for v in t]
        assert max(ys) == pytest.approx(60)
        assert "angle = 90;" in win.model.to_scad()
    finally:
        win._dirty = False
        win.close()


def test_play_sweeps_the_slider_back_and_forth(app):
    win = _window()
    try:
        panel = win._customizer
        node, _v, slider = next(r for r in panel._rows.values()
                                if r[0].params["variable"] == "angle")
        slider.play_button.setChecked(True)
        for _ in range(slider.maximum() + 3):
            panel._tick()
        assert slider.value() == slider.maximum() - 3           # bounced
        slider.play_button.setChecked(False)
        assert not panel._timer.isActive()
    finally:
        win._dirty = False
        win.close()


def test_a_moving_variable_leaves_other_parts_cached():
    from khervecad.model import DocumentModel
    root, _ = parse_scad("angle = 0; size = 5;\n"
                         "module Arm() { rotate([0, 0, angle]) cube(size); }\n"
                         "module Base() { cube(size); }\nArm();\nBase();")
    model = DocumentModel()
    model.root = root
    base = next(n for n in root.walk() if n.name == "Base")
    arm = next(n for n in root.walk() if n.name == "Arm")
    env = {"angle": 0, "size": 5}
    k_base, k_arm = mesh.exact_key(base, env), mesh.exact_key(arm, env)
    env["angle"] = 30
    assert mesh.exact_key(base, env) == k_base
    assert mesh.exact_key(arm, env) != k_arm

"""The rest of Tools ▸ Options (2026-11-13, the user: everything
SolidWorks, Fusion and Blender have): each option is checked to DO
something, not only to be saved."""

import os

import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtWidgets import QApplication

from khervecad import options_dialog, options_more, units
from khervecad.mainwindow import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _defaults():
    """Every option back to its default after each test (a 90° field
    of view left behind broke the 3D view's own tests)."""
    from PyQt5.QtCore import QSettings
    yield
    s = QSettings("Kherve", "KherveCAD")
    for key in options_more.PREFS:
        s.remove("options/" + key)
    units.DUAL = False


@pytest.fixture
def win(app):
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    QApplication.processEvents()
    yield w
    w._dirty = False
    w.close()
    units.DUAL = False


def _wheel(view, up=True, pos=None):
    pos = pos or QPoint(view.width() // 2, view.height() // 2)
    ev = QWheelEvent(QPointF(pos), QPointF(view.mapToGlobal(pos)),
                     QPoint(0, 0), QPoint(0, 120 if up else -120),
                     Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    view.wheelEvent(ev)


def test_every_page_opens_and_applies(win):
    d = options_dialog.OptionsDialog(win)
    for name in ("Mouse", "Colors", "Keyboard", "Backup", "Import Export",
                 "Template", "Drafting Standard"):
        assert name in d.PAGES
    assert len(d._keys) > 100            # every menu command rebindable
    d.apply()
    d.reject()


def test_reverse_zoom(win):
    v = win.view3d
    d0 = v.distance
    _wheel(v, up=True)
    assert v.distance < d0
    options_more.put("reverse_zoom", True)
    d1 = v.distance
    _wheel(v, up=True)
    assert v.distance > d1


def test_zoom_toward_the_cursor_moves_the_target(win):
    v = win.view3d
    t0 = list(v.target)
    _wheel(v, pos=QPoint(10, 10))
    assert t0 != list(v.target)
    options_more.put("zoom_to_cursor", False)
    t1 = list(v.target)
    _wheel(v, pos=QPoint(10, 10))
    assert t1 == list(v.target)


def test_mouse_schemes():
    options_more.put("mouse_scheme", "SolidWorks")
    assert options_more.mode_for(Qt.MiddleButton, Qt.NoModifier) == "orbit"
    assert options_more.mode_for(Qt.MiddleButton,
                                 Qt.ControlModifier) == "pan"
    options_more.put("mouse_scheme", "Fusion")
    assert options_more.mode_for(Qt.MiddleButton, Qt.NoModifier) == "pan"
    assert options_more.mode_for(Qt.MiddleButton,
                                 Qt.ShiftModifier) == "orbit"


def test_field_of_view(win):
    v = win.view3d
    usual = v._focal()
    options_more.put("fov", 90)
    assert v._focal() < usual


def test_colour_scheme_and_dual_dimensions(win):
    options_more.put("scheme", "Blue selection")
    options_more.put("dual_dimensions", True)
    options_more.apply_view(win.view3d)
    assert win.view3d.HIGHLIGHT_COLOR == "#3d8bff"
    assert "[" in units.length(25.4, "mm") and "in" in units.length(
        25.4, "mm")
    options_more.put("scheme", "Classic")
    options_more.put("dual_dimensions", False)
    options_more.apply_view(win.view3d)


def test_template_for_a_new_document(win):
    options_more.put("new_unit", "in")
    win.new_document()
    assert units.coerce(win.model.unit) == "in"
    assert not win._dirty
    options_more.put("new_unit", "mm")


def test_backup_writes_and_prunes(win, tmp_path, monkeypatch):
    monkeypatch.setattr(options_more, "backup_folder", lambda: str(tmp_path))
    options_more.put("backup_copies", 2)
    win.model.root.add(__import__("khervecad.model", fromlist=["CadNode"])
                       .CadNode("cube", "Cube", {}))
    win._dirty = True
    import time
    for _ in range(3):
        assert options_more.backup_now(win)
        time.sleep(1.05)
    assert len(os.listdir(tmp_path)) == 2


def test_y_up_stl(tmp_path):
    from khervecad.engine import parse_stl, write_stl
    path = str(tmp_path / "a.stl")
    write_stl([((0, 0, 0), (1, 0, 0), (0, 0, 5))], path)
    options_more.y_up_stl(path)
    tri = parse_stl(path)[0]
    assert max(p[1] for p in tri) == pytest.approx(5)

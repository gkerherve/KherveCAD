"""Shell like SolidWorks: thickness + faces to remove, clicked in 3D."""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, mesh, scadparse
from khervecad.mainwindow import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    yield w
    w._dirty = False
    w.close()


def _cup(model, remove):
    root = scadparse.parse_scad(
        "linear_extrude(height=20) circle(r=30, $fn=64);")[0]
    ext = root.children[0]
    model.root.add(ext)
    sh = model.wrap_nodes([ext], "shell")
    model.set_param(sh, "remove", remove)
    return sh


def test_a_removed_face_opens_the_shell(window):
    _cup(window.model, [[0, 0, 20, 0, 0, 1]])
    vol = analysis.mass_properties(mesh.tessellate(window.model.root))["volume"]
    cup = math.pi * 900 * 20 - math.pi * 28 ** 2 * 18
    assert abs(vol - cup) / cup < 0.03


def test_no_face_is_a_closed_hollow(window):
    _cup(window.model, [])
    vol = analysis.mass_properties(mesh.tessellate(window.model.root))["volume"]
    closed = math.pi * 900 * 20 - math.pi * 28 ** 2 * 16
    assert abs(vol - closed) / closed < 0.03


def test_clicking_faces_in_the_window(window):
    from khervecad import shell_pick
    sh = _cup(window.model, [])
    assert shell_pick.start(window, sh)
    view = window.view3d
    world = [t for t in shell_pick.fillet_pick.meshes(window, sh)[0]
             if all(abs(v[2] - 20) < 1e-6 for v in t)]
    desc = {"kind": "face", "tris": [world[0]]}
    view._pick_cb(desc, sh)
    assert len(sh.params["remove"]) == 1
    view._pick_cb(desc, sh)                  # again: kept after all
    assert sh.params["remove"] == []
    view._pick_cb(desc, sh)
    panel = window._shell_panel
    panel.ok.click()
    assert len(sh.params["remove"]) == 1 and sh.parent is not None
    assert not panel.isVisible()            # OK closes the window


def test_the_removed_faces_round_trip_through_scad(window):
    sh = _cup(window.model, [[0, 0, 20, 0, 0, 1]])
    code = window.model.to_scad()
    back = scadparse.parse_scad(code)[0]
    found = [n for n in back.walk() if n.type == "shell"]
    assert found and [[float(v) for v in r] for r in
                      found[0].params["remove"]] == [[0, 0, 20, 0, 0, 1]]
    assert sh.params["remove"]


def test_shell_button_on_a_selected_shell_edits_it(window):
    sh = _cup(window.model, [])
    window.builder.active_tree().select_nodes([sh])
    window._apply_operation("shell")
    assert window._shell_panel is not None
    assert sh.parent is window.model.root          # not wrapped again
    assert not any(c.type == "shell" for c in sh.children)
    window._shell_panel.fields["thickness"].setValue(3.0)
    assert float(sh.params["thickness"]) == 3.0
    window._shell_panel.ok.click()

"""The Chemistry Builder window driven with real mouse clicks."""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import chem_scene as cs


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def builder(app):
    from khervecad import chem_dialog
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    panel = chem_dialog.open_builder(win)
    panel.canvas.resize(600, 500)
    yield win, panel
    panel.close()
    win.model.undo_stack.clear()
    win.model._dirty = False if hasattr(win.model, "_dirty") else None


def _click(canvas, i, mods=Qt.NoModifier):
    x, y, _z = canvas.project(canvas.scene.atoms[i][1:4])
    QTest.mouseClick(canvas, Qt.LeftButton, mods, QPoint(int(x), int(y)))


def test_clicks_measure_a_distance_and_an_angle(builder):
    _win, panel = builder
    panel.load_scene(cs.compound_scene("water"))
    canvas = panel.canvas
    panel.set_tool("measure")
    o = next(i for i, a in enumerate(canvas.scene.atoms) if a[0] == "O")
    h1, h2 = [i for i, a in enumerate(canvas.scene.atoms) if a[0] == "H"]
    # a view where the three atoms do not hide one another
    for name in ("Front", "Top", "Side", "3D"):
        canvas.set_view(name)
        canvas.fit()
        pts = [canvas.project(canvas.scene.atoms[i][1:4]) for i in (h1, o,
                                                                    h2)]
        if min(abs(p[0] - q[0]) + abs(p[1] - q[1])
               for k, p in enumerate(pts) for q in pts[k + 1:]) > 60:
            break
    for i in (h1, o, h2):
        _click(canvas, i)
    texts = [panel.measures.item(k).text()
             for k in range(panel.measures.count())]
    assert any("Å" in t for t in texts) and any("°" in t for t in texts)
    kinds = [m[1]["kind"] for m in canvas.measures]
    assert "distance" in kinds and "angle" in kinds
    canvas.grab()                                     # paints


def test_add_delete_and_undo(builder):
    _win, panel = builder
    panel.load_scene(cs.compound_scene("CCO"))
    canvas = panel.canvas
    n = len(canvas.scene.atoms)
    panel.element.setCurrentText("Cl")
    panel.set_tool("add")
    _click(canvas, 0)
    assert len(canvas.scene.atoms) == n + 1
    assert canvas.scene.atoms[-1][0] == "Cl"
    panel.set_tool("delete")
    _click(canvas, n)
    assert len(canvas.scene.atoms) == n
    panel.undo()
    assert len(canvas.scene.atoms) == n + 1
    panel.undo()
    assert len(canvas.scene.atoms) == n


def test_surface_dope_adsorbate_and_build(builder):
    win, panel = builder
    panel.source.setCurrentIndex(2)                    # Surface
    panel.s_crystal.setCurrentIndex(panel.s_crystal.findData("rutile"))
    panel.miller.setText("110")
    for s in panel.s_rep:
        s.setValue(2)
    panel.layers.setValue(2)
    panel.complete.setChecked(True)
    panel.load_from_form()
    scene = panel.canvas.scene
    assert scene.kind == "surface" and "whole polyhedra" in scene.name
    panel.dope_rule.setText("Ti:Zr:0.5")
    panel._dope()
    assert scene.composition().get("Zr")
    panel.ads_text.setText("CO")
    panel._add_adsorbate()
    assert panel.groups.count() == 1
    panel.gh.setValue(3.0)
    assert ad_height(panel) == pytest.approx(3.0)
    out = panel.build_into_document()
    assert out and out["objects"] and win.model.unit == "nm"
    rows = dict(cs.properties(panel.canvas.scene))
    assert "Doping" in rows and rows["Space group"]


def ad_height(panel):
    from khervecad import chem_adsorb as ad
    return ad.pose(panel.canvas.scene, 0)["height"]


def test_reaction_film_plays_and_builds(builder):
    win, panel = builder
    panel.load_reaction("H2 + O2 -> H2O")
    first = [a[1:] for a in panel.canvas.scene.atoms]
    panel.scrub.setValue(200)
    last = [a[1:] for a in panel.canvas.scene.atoms]
    assert first != last and "separate" in panel.film_label.text()
    out = panel.build_into_document()
    assert out["slider"] == "rx_t"


def test_export_writes_a_cif(builder, tmp_path):
    from khervecad import chem_io
    _win, panel = builder
    panel.source.setCurrentIndex(1)
    panel.crystal.setCurrentIndex(panel.crystal.findData("nacl"))
    panel.load_from_form()
    out = chem_io.export(panel.canvas.scene, str(tmp_path / "x.cif"))
    assert out["atoms"] == len(panel.canvas.scene.atoms)


def test_the_chemistry_mcp_tool(builder, tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    win, panel = builder
    ex = McpToolExecutor(win)
    out = ex.execute("chemistry", {"action": "load", "source": "surface",
                                   "crystal": "cu", "miller": "111",
                                   "repeat": [3, 3], "layers": 2})
    assert out["kind"] == "surface" and panel.canvas.scene.kind == "surface"
    m = ex.execute("chemistry", {"action": "measure", "atoms": [0, 1]})
    assert m["kind"] == "distance" and m["unit"] == "Å"
    a = ex.execute("chemistry", {"action": "adsorb", "compound": "CO",
                                 "mode": "upright", "height": 1.9})
    assert a["height"] == pytest.approx(1.9) and a["adsorbates"]
    d = ex.execute("chemistry", {"action": "dope", "rule": "Cu:Ni:0.5"})
    assert d["substituted"]
    e = ex.execute("chemistry", {"action": "export",
                                 "path": str(tmp_path / "s.xyz")})
    assert e["format"] == "xyz"
    b = ex.execute("chemistry", {"action": "build"})
    assert b["objects"]
    bad = ex.execute("chemistry", {"action": "fly"})
    assert "action is one of" in str(bad.get("error", bad))

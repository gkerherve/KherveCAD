"""Fitting a face to photographs: the least-squares core, the human
node's face sliders and warp, and the face_landmarks / fit_face tools.

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

from khervecad import document, facefit, human, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


# ── the solver ─────────────────────────────────────────────────────

def test_least_squares_recovers_weights_inside_the_box():
    # residual(w) = J w + r with the true answer w* = (0.5, -0.3)
    jac = [[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]]
    true = [0.5, -0.3]
    r = [-(row[0] * true[0] + row[1] * true[1]) for row in jac]
    w = facefit.least_squares(jac, r, lam=1e-6)
    assert w == pytest.approx(true, abs=1e-4)
    # an answer past the box is pinned at its edge, the rest re-solved
    r2 = [-(row[0] * 3.0 + row[1] * 0.2) for row in jac]
    w2 = facefit.least_squares(jac, r2, lam=1e-6)
    assert w2[0] == pytest.approx(1.0)
    assert -1.0 <= w2[1] <= 1.0
    assert facefit.least_squares([], [], 0.1) == []


def test_fit_uses_one_difference_per_slider_and_drops_the_tiny():
    calls = []

    def project(weights):
        calls.append(dict(weights))
        a, b = weights.get("a", 0.0), weights.get("b", 0.0)
        return [a - 0.4, 2 * b + 0.6, 0.0]
    weights, before, after = facefit.fit(project, ["a", "b"], lam=1e-6)
    assert weights["a"] == pytest.approx(0.4, abs=1e-3)
    assert weights["b"] == pytest.approx(-0.3, abs=1e-3)
    assert after < 0.01 < before
    assert calls[0] == {} and calls[1] == {"a": 1.0} and calls[2] == {"b": 1.0}
    rows = facefit.residual_warp([((0, 0, 0), (0.1, 0, 0)),
                                  ((1, 2, 3), (0, 2.0, 0))])
    assert rows == [[1, 2, 3, 0, 2.0, 0]]


# ── the human node's face ──────────────────────────────────────────

def test_face_sliders_pair_the_target_files_and_move_the_face():
    table = human.sliders()
    assert table["nose-scale-horiz"] == [("nose-scale-horiz-decr",
                                          "nose-scale-horiz-incr")]
    assert len(table["eye-scale"]) == 2 and table["head-oval"] == [(None, "head-oval")]
    assert human.target_weights([["nose-scale-horiz", -0.5],
                                 ["head-oval", 0.7]]) == {
        "nose-scale-horiz-decr": 0.5, "head-oval": 0.7}
    base = human.landmark_points(stature=1630)
    low = human.landmark_points(stature=1630, targets=[["chin-height", -1.0]])
    assert low["chin"][2] != pytest.approx(base["chin"][2], abs=0.5)
    assert low["eye_l"] == pytest.approx(base["eye_l"], abs=0.5)
    wide = human.landmark_points(stature=1630, targets=[["mouth-scale-horiz", 1.0]])
    assert wide["mouth_l"][0] > base["mouth_l"][0] + 1.0
    assert set(base) >= {"eye_l", "eye_r", "nose_tip", "chin", "mouth_l",
                         "mouth_r", "head_top", "brow_l", "jaw_r"}
    # landmarks sit where a face has them: eyes above the nose above the chin
    assert base["eye_l"][2] > base["nose_tip"][2] > base["lip_top"][2] > base["chin"][2]
    assert base["eye_l"][0] == pytest.approx(-base["eye_r"][0])


def test_the_warp_carries_a_landmark_where_asked_and_stays_smooth():
    base = human.landmark_points(stature=1630)
    tip = base["nose_tip"]
    moved = human.landmark_points(stature=1630, warp=[tip + [0, -8.0, 3.0]])
    assert moved["nose_tip"] == pytest.approx([tip[0], tip[1] - 8, tip[2] + 3], abs=0.05)
    assert moved["chin"] == pytest.approx(base["chin"], abs=0.5)      # far away: untouched
    assert moved["lip_top"] != pytest.approx(base["lip_top"], abs=0.05)  # near: follows a little
    pts = human.rbf_warp([(0, 0, 0), (100, 0, 0)], [[0, 0, 0, 1, 2, 3]], 10)
    assert pts[0] == pytest.approx((1, 2, 3)) and pts[1] == pytest.approx((100, 0, 0))
    assert human.rbf_warp([(1, 1, 1)], [], 10) == [(1, 1, 1)]


def test_the_face_params_bake_validate_and_round_trip(app, tmp_path):
    doc = DocumentModel()
    node = doc.add_node("human", dict(stature=1630.0,
                                      targets=[["nose-scale-horiz", 0.5],
                                               ["head-oval", 0.3]],
                                      warp=[[0.0, -160.0, 1490.0, 0.0, -5.0, 0.0]]))
    assert node.id not in validate(doc.root)
    code = doc.to_scad()
    assert 'targets = [["nose-scale-horiz", 0.5], ["head-oval", 0.3]]' in code
    assert "warp = [[0, -160, 1490, 0, -5, 0]]" in code
    path = tmp_path / "face.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    back = next(n for n in other.root.walk() if n.type == "human")
    assert back.params["targets"] == [["nose-scale-horiz", 0.5], ["head-oval", 0.3]]
    assert back.params["warp"] == [[0.0, -160.0, 1490.0, 0.0, -5.0, 0.0]]
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["targets"] = [["no-such-slider", 1.0]]
    assert "no slider" in validate(doc.root)[node.id]
    node.params["targets"] = []
    node.params["warp"] = [[1.0, 2.0]]
    assert "6 values" in validate(doc.root)[node.id]


# ── the tools ──────────────────────────────────────────────────────

@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def _photo(tmp_path, w=400, h=500):
    from PyQt5.QtGui import QColor, QImage
    image = QImage(w, h, QImage.Format_RGB888)
    image.fill(QColor("#cccccc"))
    path = tmp_path / "front.png"
    image.save(str(path))
    return str(path)


def test_face_landmarks_report_pixels_and_fit_face_pulls_them_there(window, tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    doc = window.model
    turn = doc.add_node("rotate", dict(z=30.0))            # a turned figure
    node = doc.add_node("human", dict(stature=1630.0), parent=turn)
    photo = _photo(tmp_path)
    # a front picture 400 mm wide placed over the head
    doc.add_reference_image(dict(path=photo, plane="Front (XZ)", x=-200.0,
                                 y=1300.0, width=400.0, height=500.0,
                                 offset=0.0, opacity=0.5, visible=True))
    lm = ex.execute("face_landmarks", {"node_id": node.id})
    assert "error" not in lm, lm
    by = {l["name"]: l for l in lm["landmarks"]}
    tip = by["nose_tip"]
    assert tip["images"][0]["px"] is not None
    # the pixel maps back to the world point on the plane
    px, py = tip["images"][0]["px"], tip["images"][0]["py"]
    assert -200 + px / 400 * 400 == pytest.approx(tip["world"][0], abs=0.2)
    assert 1300 + (1 - py / 500) * 500 == pytest.approx(tip["world"][2], abs=0.2)
    assert "nose-scale-horiz" in lm["sliders"]
    # ask for the mouth wider and the chin lower than the model has them
    def shifted(name, dx, dz):
        m = by[name]["images"][0]
        return {"name": name, "image": 0, "px": m["px"] + dx, "py": m["py"] + dz}
    landmarks = [shifted("mouth_l", 6, 0), shifted("mouth_r", -6, 0),
                 shifted("chin", 0, 8), shifted("nose_tip", 0, 0),
                 shifted("eye_l", 0, 0), shifted("eye_r", 0, 0)]
    out = ex.execute("fit_face", {"node_id": node.id, "landmarks": landmarks})
    assert "error" not in out, out
    assert out["rms_mm"]["sliders"] < out["rms_mm"]["before"]
    assert out["rms_mm"]["warp"] < 0.3                      # the warp pins them
    assert node.params["targets"] and node.params["warp"]
    assert all(l["error_mm"] < 0.3 for l in out["landmarks"])
    # the same fit again changes nothing much: it is idempotent
    again = ex.execute("fit_face", {"node_id": node.id, "landmarks": landmarks})
    assert again["rms_mm"]["warp"] < 0.3
    assert "error" in ex.execute("fit_face", {"node_id": node.id, "landmarks": []})
    assert "error" in ex.execute("fit_face", {"node_id": node.id,
                                              "landmarks": [{"name": "nowhere", "px": 1, "py": 1}]})
    assert "error" in ex.execute("fit_face", {"node_id": node.id, "sliders": ["nope"],
                                              "landmarks": landmarks})
    mm = ex.execute("fit_face", {"node_id": turn.id, "warp": False,
                                 "landmarks": [{"name": "chin", "plane": "Front (XZ)",
                                                "u": by["chin"]["world"][0],
                                                "v": by["chin"]["world"][2] - 5}]})
    assert "error" not in mm and mm["warp_rows"] == 0

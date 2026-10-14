"""File ▸ Export Turntable Movie: frames round the model and the encode.

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
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from khervecad import movie, scadparse


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 650)
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad("cube([60, 20, 10]);")
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    yield win
    win._dirty = False
    win.close()


def test_the_loop_joins_without_repeating_a_frame():
    yaws = movie.frame_yaws(8, turns=1, start=10, clockwise=False)
    assert yaws[0] == 10 and yaws[1] == 55 and yaws[-1] == 325
    assert movie.frame_yaws(4, clockwise=True)[1] == -90


def test_requests_are_checked():
    with pytest.raises(movie.MovieError):
        movie.check("/tmp/a.avi", 8, 30, 1, 640, 480)
    with pytest.raises(movie.MovieError):
        movie.check("/tmp/a.mp4", 200, 60, 1, 640, 480)
    with pytest.raises(movie.MovieError):
        movie.check("/tmp/a.mp4", 8, 30, 0, 640, 480)


def test_frames_keep_one_distance_round_the_turn(window, tmp_path):
    """A long thin bar fits differently side-on and end-on; the movie
    must not zoom as it turns, so every frame uses the widest fit."""
    count = movie.render_frames(window.view3d, tmp_path, seconds=1, fps=6,
                                turns=1, width=96, height=64)
    assert count == 6
    files = sorted(tmp_path.glob("frame_*.png"))
    assert len(files) == 6
    images = [QImage(str(f)) for f in files]
    assert all(img.width() == 96 and img.height() == 64 for img in images)
    # the turn changes the picture
    assert images[0] != images[1]


@pytest.mark.skipif(movie.ffmpeg_exe() is None, reason="no ffmpeg")
@pytest.mark.parametrize("suffix", [".mp4", ".gif"])
def test_exports_a_movie(window, tmp_path, suffix):
    out = tmp_path / f"turn{suffix}"
    result = movie.export(window.view3d, out, seconds=0.5, fps=8,
                          width=96, height=64)
    assert out.is_file() and out.stat().st_size > 500
    assert result["frames"] == 4 and result["format"] == suffix[1:]


def test_mcp_tool_is_registered():
    from khervecad import mcp_schema, mcp_tools
    assert any(t["name"] == "export_movie" for t in mcp_schema.TOOLS)
    assert hasattr(mcp_tools.McpToolExecutor, "_t_export_movie")


def test_material_survives_a_coloured_object_call():
    """`kcad_material("Metal") color(c) Part();` imports with the
    colour AND the material on one wrapper — the Object's own colour
    used to win and the steel came back flat grey."""
    root, _w = scadparse.parse_scad(
        'module Part() { cube(10); }\n'
        'kcad_material("Metal") color("#f4f6f8") { Part(); }\n')
    stack, wrappers = [root], []
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        if n.type == "color":
            wrappers.append(n)
    assert len(wrappers) == 1
    w = wrappers[0]
    assert w.params["material"] == "Metal"
    assert w.params["color"] == "#f4f6f8"
    part = w.children[0]
    assert part.type == "component" and not part.params.get("color")


def test_light_sweep_wraps_into_the_bar_range():
    lights = movie.light_turns(4, turns=1, start=0.0)
    assert lights == [0.0, 0.5, -1.0, -0.5]


def test_light_motion_keeps_the_camera_and_moves_the_light(window,
                                                          tmp_path):
    view = window.view3d
    yaw, light = view.yaw, view.light_turn
    movie.render_frames(view, tmp_path, seconds=1, fps=4, turns=1,
                        width=96, height=64, motion="light")
    assert view.yaw == yaw and view.light_turn == light   # restored
    a, b = (QImage(str(f)) for f in sorted(tmp_path.glob("*.png"))[:2])
    assert a != b                      # the shading moved


def test_sequence_is_light_then_turn_then_light():
    yaws, lights = movie.motion_path("sequence", 12, 1, 0.0, 0.0)
    assert yaws[:4] == [0.0] * 4 and yaws[8:] == [0.0] * 4   # still
    assert lights[:4] == lights[8:] and len(set(lights[:4])) == 4
    assert lights[4:8] == [0.0] * 4 and len(set(yaws[4:8])) == 4
    assert yaws[4] == 0.0 and lights[4] == 0.0   # each act joins


def test_light_swing_length_is_chosen():
    yaws, lights = movie.motion_path("sequence", 20, 1, 0.0, 0.0,
                                     light_frames=3)
    still = [i for i, y in enumerate(yaws) if y == 0.0]
    assert lights[3:17] == [0.0] * 14          # 14-frame turn
    assert len(set(lights[:3])) == 3 and lights[:3] == lights[17:]
    assert yaws[:3] == [0.0] * 3 and len(set(yaws[3:17])) == 14
    assert still[:3] == [0, 1, 2]


def test_light_swings_must_leave_time_for_the_turn(window, tmp_path):
    with pytest.raises(movie.MovieError):
        movie.export(window.view3d, tmp_path / "a.mp4", seconds=4,
                     motion="sequence", light_seconds=2)


# ── tumble, still camera, moving parts ─────────────────────────────

def test_tumble_goes_over_the_top_while_it_turns():
    pitches = movie.tumble_pitches(8, turns=1, start=0.0)
    assert pitches[:3] == [0.0, 45.0, 90.0]
    assert pitches[4] == -180.0 and pitches[-1] == -45.0   # wrapped
    yaws, _l = movie.motion_path("tumble", 8, 1, 0.0, 0.0)
    assert len(set(yaws)) == 8                 # and it goes round


def test_still_keeps_the_camera():
    yaws, lights = movie.motion_path("still", 5, 1, 30.0, 0.2)
    assert yaws == [30.0] * 5 and lights == [0.2] * 5


def test_ping_pong_loops():
    assert movie.ping_pong(4) == [0.0, 0.5, 1.0, 0.5]
    assert movie.ping_pong(4, cycles=2) == [0.0, 1.0, 0.0, 1.0]


@pytest.fixture
def moving(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 650)
    win._confirm_discard = lambda: True
    root, _w = scadparse.parse_scad(
        "/* [Motion] */\n"
        "arm = 0;  // [0:10:90]\n"
        "cube([60, 10, 10]);\n"
        "rotate([0, -arm, 0]) translate([0, 20, 0]) cube([60, 10, 10]);\n")
    win.model.root = root
    win.model.structure_changed.emit()
    win._refresh_preview()
    yield win
    win._dirty = False
    win.close()


def _arm(win):
    return next(n for n in win.model.root.walk()
                if n.type == "assign" and n.params.get("variable") == "arm")


def test_animator_finds_the_motion_slider_and_puts_it_back(moving):
    anim = movie.Animator(moving)
    assert anim.names == ["arm"]
    anim.pose(1.0)
    assert float(_arm(moving).params["value"]) == 90.0
    anim.restore()
    assert _arm(moving).params["value"] in (0, 0.0, "0")


def test_animator_takes_a_limited_range(moving):
    anim = movie.Animator(moving, [{"variable": "arm", "from": 20,
                                    "to": 40}])
    anim.pose(0.5)
    assert float(_arm(moving).params["value"]) == 30.0
    anim.restore()
    with pytest.raises(movie.MovieError):
        movie.Animator(moving, ["nothing_here"])


def test_parts_move_while_the_camera_stays(moving, tmp_path):
    view = moving.view3d
    yaw, pitch = view.yaw, view.pitch
    before = list(view.mesh)
    QApplication.processEvents()            # settle the load's snapshot
    steps = moving.model.undo_stack.count()
    count = movie.render_frames(view, tmp_path, seconds=1, fps=4, turns=1,
                                width=96, height=64, motion="still",
                                animator=movie.Animator(moving))
    assert count == 4 and (view.yaw, view.pitch) == (yaw, pitch)
    a, c = (QImage(str(tmp_path / f"frame_{i:05d}.png")) for i in (0, 2))
    assert a != c                       # the arm swung between them
    assert list(view.mesh) == before    # and came back
    QApplication.processEvents()
    assert moving.model.undo_stack.count() == steps   # no undo steps


def test_a_document_without_sliders_says_so(window):
    with pytest.raises(movie.MovieError):
        movie.Animator(window)


def test_tumble_frames_render(window, tmp_path):
    count = movie.render_frames(window.view3d, tmp_path, seconds=1, fps=4,
                                turns=1, width=96, height=64,
                                motion="tumble", tumble_turns=1)
    assert count == 4


def test_keys_are_eased_and_held():
    keys = movie.check_keys("a", [[0.5, 10], [0, 0], [1, 0]])
    assert keys[0] == (0.0, 0.0)               # sorted
    assert movie.key_value(keys, 0.0) == 0.0
    assert movie.key_value(keys, 0.5) == 10.0
    assert movie.key_value(keys, 0.25) == 5.0  # eased midpoint
    assert movie.key_value(keys, 0.05) < 0.5   # starts gently
    with pytest.raises(movie.MovieError):
        movie.check_keys("a", [[1.5, 0]])


def test_a_keyed_slider_acts_out_its_keys(moving):
    anim = movie.Animator(moving, [{"variable": "arm",
                                    "keys": [[0, 0], [0.5, 80], [1, 0]]}])
    anim.at(0.5)
    assert float(_arm(moving).params["value"]) == 80.0
    anim.at(0.25, cycles=2)                    # half way through cycle 1
    assert float(_arm(moving).params["value"]) == 80.0
    anim.restore()
    assert _arm(moving).params["value"] in (0, 0.0, "0")

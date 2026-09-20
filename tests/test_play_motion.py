"""MCP play_motion: "make it move / rotate / show it in action" ends
with the model MOVING — the Customizer's play pressed on the motion
slider, or a still part given a spin of its own — and the Earth system's
days turn the planet in small enough steps to watch it go round.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import time

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import library, library_motion as lm, library_solar as ls
from khervecad import motion_play


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    # never closed: a dirty window asks to discard, and nobody answers
    return MainWindow()


@pytest.fixture
def ex(window):
    from khervecad.mcp_tools import McpToolExecutor
    return McpToolExecutor(window)


def _pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()


def _var(model, name):
    return next(n for n in model.global_assigns()
                if n.params["variable"] == name)


def test_the_earth_system_steps_a_hundredth_of_a_day(app):
    spec = ls.SYSTEMS["system_earth"]
    assert (spec["step"], spec["span"]) == (0.01, 55)
    # Mars' moons are quick: the automatic step rounded to 0 and the
    # slider fell back to whole days
    assert ls.SYSTEMS["system_mars"]["step"] > 0
    from khervecad.model import DocumentModel
    doc = DocumentModel()
    ls.insert_system("system_earth", doc)
    assert _var(doc, "earth_days").params["options"] == "0:0.01:55"


def test_play_motion_is_a_tool(app):
    from khervecad.mcp_bridge import _READ_ONLY_TOOLS
    from khervecad.mcp_schema import TOOLS
    tool = next(t for t in TOOLS if t["name"] == "play_motion")
    assert "rotate" in tool["description"]
    assert "play_motion" not in _READ_ONLY_TOOLS       # it moves values


def test_play_runs_the_orrery_and_stops(app, window, ex):
    ls.insert_system("system_earth", window.model)
    window.model.structure_changed.emit()
    result = ex.execute("play_motion", {})
    assert result["playing"] == "earth_days", result
    assert result["range"] == [0.0, 0.01, 55.0]
    days = _var(window.model, "earth_days")
    _pump(app, 0.5)
    assert float(days.params["value"]) > 0            # it is moving
    assert not window._customizer_dock.isHidden()     # the panel shows
    stopped = ex.execute("play_motion", {"play": False})
    assert stopped == {"playing": None, "stopped": "earth_days"}
    value = days.params["value"]
    _pump(app, 0.3)
    assert days.params["value"] == value              # and it stopped


def test_play_finds_a_mechanisms_driver_among_other_sliders(app, window,
                                                            ex):
    lm.insert("motion_gear_pair", window.model)
    window.model.structure_changed.emit()
    result = ex.execute("play_motion", {})
    assert result["playing"] == "gears_angle", result
    assert ex.execute("play_motion", {"variable": "big_teeth"})[
        "playing"] == "gears_big_teeth"


def test_spin_makes_a_still_part_turn(app, window, ex):
    node = library.build_part("body_moon", {"d": 30.0})
    window.model.root.add(node)
    part = window.model.enclose_as_part(node, "Moon")
    window.model.structure_changed.emit()
    result = ex.execute("play_motion", {"spin": part.id})
    assert result["created"] == "moon_spin", result
    assert part.params["rz"] == "moon_spin"
    spin = _var(window.model, "moon_spin")
    assert spin.params["options"] == motion_play.SPIN_OPTIONS
    assert spin.params["group"] == "Motion"
    # wait for the first tick rather than for a fixed 0.3 s: on a slow CI
    # runner the first preview refresh alone can take longer than that
    deadline = time.monotonic() + 20.0
    while float(spin.params["value"]) <= 0 and time.monotonic() < deadline:
        _pump(app, 0.05)
    assert float(spin.params["value"]) > 0
    # asking again plays the same spin, it does not stack another
    again = ex.execute("play_motion", {"spin": part.id})
    assert again["playing"] == "moon_spin" and "created" not in again
    assert [n.params["variable"] for n in window.model.global_assigns()
            ].count("moon_spin") == 1


def test_spin_adds_to_a_turned_part(app, window, ex):
    node = library.build_part("body_mars", {"d": 30.0})
    window.model.root.add(node)
    part = window.model.enclose_as_part(node, "Red planet")
    part.params["rz"] = 30.0
    window.model.structure_changed.emit()
    ex.execute("play_motion", {"spin": part.id})
    assert part.params["rz"] == "(30.0) + red_planet_spin"


def test_play_says_what_to_do_when_nothing_moves(app, window, ex):
    empty = ex.execute("play_motion", {})
    assert "error" in empty and "spin" in empty["error"]
    lm.insert("motion_crank", window.model)
    window.model.structure_changed.emit()
    missing = ex.execute("play_motion", {"variable": "warp_speed"})
    assert "crank_angle" in missing["error"]            # lists the sliders
    sphere = window.model.add_node("sphere")
    leaf = ex.execute("play_motion", {"spin": sphere.id})
    assert "Object" in leaf["error"]

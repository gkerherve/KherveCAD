"""The three-part printable butt hinges — Butt Hinge (a bolt screws in)
and Butt Hinge 2 (a pin slides in and clicks home): each shipped file is
what the builder makes, each part prints flat at its own origin, and —
rendered exactly by OpenSCAD — the parts fit: Leaf B swings through 180°
without touching Leaf A or the bolt / pin, the bolt's thread sits in
the tap's, and the pin's lugs really catch until they reach the groove.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, document, engine
from khervecad.model import DocumentModel, module_name, validate
from khervecad.tools import butt_hinge as bh

#: style -> the name of its third part
FASTENER = {"screw": "Bolt", "slide": "Pin"}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _doc(style):
    model = DocumentModel()
    model.global_fn_on = False                     # as the builder saves
    for part in bh.parts(style):
        model.root.add(part)
    return model


@pytest.fixture(scope="module", params=sorted(bh.STYLES))
def styled(app, request):
    return request.param, _doc(request.param)


def test_shipped_file_is_what_the_builder_makes(styled):
    """Change the builder, re-run it (python -m khervecad.tools.butt_hinge)
    — or this fails and the library keeps the old hinge."""
    style, doc = styled
    data = json.loads(bh.default_path(style).read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(document.node_to_dict(doc.root)))
    assert data["tree"] == fresh
    # saved with the document-wide $fn on, the socket came out round
    assert data["global_fn_on"] is False


def test_three_objects_that_validate(styled):
    style, doc = styled
    assert [c.name for c in doc.components()] == \
        ["Leaf A", "Leaf B", FASTENER[style]]
    assert validate(doc.root) == {}
    # Publish to Printables writes one STL per part
    from khervecad import printables
    assert len(printables.print_parts(doc)) == 3


def test_bolt_thread_and_tap_share_one_helix(app):
    """Same start, same twist rate, same slice spacing: the only
    difference between the two threads is the diameter."""
    doc = _doc("screw")

    def extrude(comp, name):
        return next(n for n in comp.walk()
                    if n.type == "linear_extrude" and n.name == name)
    leaf_a, _b, bolt = doc.components()
    tap, thread = extrude(leaf_a, "Tapped thread"), extrude(bolt, "Thread")
    for ext in (tap, thread):
        assert ext.params["twist"] / ext.params["height"] == \
            pytest.approx(-360.0 / bh.PITCH)
    assert tap.params["height"] / tap.params["segments"] == \
        pytest.approx(thread.params["height"] / thread.params["segments"])
    # both start at THREAD_START on the same axis once the bolt is placed
    assert bolt.params["z"] + bh.FLAT == pytest.approx(bh.KNUCKLE_R)
    assert tap.parent.parent.params["x"] == thread.parent.parent.params["x"]


def test_socket_is_hexagonal(app):
    """A key turns the bolt only if the socket keeps its six sides."""
    doc = _doc("screw")
    bolt = doc.components()[2]
    socket = next(n for n in bolt.walk()
                  if n.type == "cylinder" and n.name == "Hex socket")
    assert socket.params["segments"] == 6
    line = next(ln for ln in doc.subtree_scad(bolt).splitlines()
                if f"r1={socket.params['radius_bottom']:g}" in ln)
    assert "$fn=6," in line


def test_pin_slides_its_lugs_need_a_flex_and_sit_free_in_the_groove():
    """The numbers behind the click: the lugs pass the bore only by
    flexing, which the slit allows twice over, and sit free once home."""
    over = bh.LUG_R - bh.BORE_R
    assert 0.2 <= over <= 0.4
    assert bh.SLIT_W / 2 >= 2 * over
    assert bh.GROOVE_R - bh.LUG_R >= bh.FIT
    assert bh.GROOVE_X[0] < bh.LUG_X[0] and bh.LUG_X[3] < bh.GROOVE_X[3]
    assert bh.GROOVE_X[3] < bh.TAP_END           # inside the blind knuckle


def _openscad():
    for candidate in (shutil.which("openscad"), "/opt/homebrew/bin/openscad",
                      "/usr/local/bin/openscad",
                      "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _render(binary, code, path):
    scad, stl = path.with_suffix(".scad"), path.with_suffix(".stl")
    scad.write_text(code)
    run = subprocess.run([binary, *engine.openscad_args(binary, stl, scad)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr[-1500:]
    return engine.parse_stl(str(stl))


def test_parts_print_flat_and_fit(styled, tmp_path):
    binary = _openscad()
    if binary is None:
        pytest.skip("OpenSCAD is not installed")
    style, doc = styled
    fastener = FASTENER[style]
    world = {}
    for comp in doc.components():
        code = doc.subtree_scad(comp)
        tris = _render(binary, code, tmp_path / f"{comp.name} print")
        report = analysis.print_check(tris)
        water = next(c for c in report["checks"] if c["name"] == "Watertight")
        assert water["status"] == "pass", (comp.name, water["message"])
        assert min(v[2] for t in tris for v in t) == pytest.approx(0.0,
                                                                  abs=1e-6)
        call = f"{module_name(comp.name)}();"
        world[comp.name] = code.rsplit(call, 1)[0] + "{place}" + call + "\n"

    def placed(name, place, tag):
        return _render(binary, world[name].replace("{place}", place),
                       tmp_path / tag)
    lift = bh.KNUCKLE_R - bh.FLAT
    leaf_a = placed("Leaf A", "", "A")
    home = placed(fastener, f"translate([0, 0, {lift}]) ", "home")
    # the head seats on the end knuckle: backed off 0.05 mm it touches
    # nothing, so the bores (and thread, or lugs in their groove) clear
    backed = placed(fastener, f"translate([-0.05, 0, {lift}]) ", "back")
    assert analysis.interference([("A", leaf_a), ("fastener", backed)])[0][
        "status"] == "clear"
    if style == "slide":
        # 6 mm short of home the lugs are in the plain bore: they must
        # press on it, or the pin would never click and never hold
        short = placed(fastener, f"translate([-6, 0, {lift}]) ", "short")
        assert analysis.interference([("A", leaf_a), ("pin", short)])[0][
            "status"] == "intersect"
    r = bh.KNUCKLE_R
    for angle in (0, 90, 180):
        leaf_b = placed("Leaf B", f"translate([0, 0, {r}]) rotate([{angle}, "
                                  f"0, 0]) translate([0, 0, {-r}]) ",
                        f"B {angle}")
        for other, tris in (("Leaf A", leaf_a), (fastener, home)):
            result = analysis.interference([("B", leaf_b), (other, tris)])
            assert result[0]["status"] == "clear", (angle, other, result)

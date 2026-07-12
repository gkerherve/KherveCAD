"""Tests for the redesigned fasteners and the mechanical examples.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import examples, library, mesh
from khervecad.model import CadNode, DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _names(node):
    return {n.name for n in node.walk()}


# ------------------------------------------------------------ fasteners

def test_bolt_sizes_have_bosl2_fields():
    for size, s in library.BOLT_SIZES.items():
        for key in ("d", "pitch", "af", "head_h", "socket",
                    "socket_depth", "cap_d", "cap_h", "nut_h"):
            assert key in s, f"{size} missing {key}"


def test_hex_bolt_has_chamfered_head_and_lead_in(app):
    bolt = library.hex_bolt(dict(library.BOLT_SIZES["M6"]), 20.0)
    names = _names(bolt)
    assert "Top chamfer" in names          # the head is chamfered
    assert "Lead chamfer" in names          # the tip has a lead-in
    m = DocumentModel(); m.root.add(bolt)
    assert validate(m.root) == {}
    assert len(mesh.tessellate(m.root, fn=m.effective_fn())) > 0


def test_hex_nut_is_chamfered_both_faces(app):
    nut = library.hex_nut(dict(library.BOLT_SIZES["M8"]))
    names = _names(nut)
    assert "Top chamfer" in names
    assert "Bottom chamfer" in names
    assert "Internal thread" in names       # a real mating thread


def test_socket_screw_uses_cap_diameter(app):
    screw = library.socket_screw(dict(library.BOLT_SIZES["M6"]), 20.0)
    assert "Cap chamfer" in _names(screw)
    m = DocumentModel(); m.root.add(screw)
    assert validate(m.root) == {}


# ------------------------------------------------------------ examples

def test_many_mechanical_examples(app):
    mech = [e for e in examples.EXAMPLES if e[1] == "Mechanical"]
    assert len(mech) >= 10          # "a lot more" mechanical examples


def test_examples_use_fasteners(app):
    """Several examples should actually place library fasteners."""
    threaded = 0
    for label, cat, build in examples.EXAMPLES:
        names = _names(build())
        if any("thread" in n.lower() or "Hex bolt" in n
               or "Socket head" in n or "Hex nut" in n for n in names):
            threaded += 1
    assert threaded >= 4


def test_gear_has_teeth_loop(app):
    names = _names(examples.gear_pair())
    assert "Teeth" in names

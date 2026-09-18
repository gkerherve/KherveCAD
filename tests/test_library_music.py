"""Musical instruments: every part builds and validates in every size and
finish, and the instruments are tuned by their physics — bar lengths,
closed pipes, frets, chimes — the way the modules say they are.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import (library, library_music as M, library_music_more as MM,
                       mesh, scadparse)
from khervecad.model import CadNode, validate

MUSIC = sorted(pid for pid, s in library.PARTS.items()
               if s.get("category") == M.CATEGORY)


def _build(pid, size=None, **extra):
    spec = library.PARTS[pid]
    sizes = spec.get("sizes") or {}
    size = size or next(iter(sizes))
    dims = dict(sizes.get(size, {}), _size=size)
    dims.update(extra)
    return library.build_part(pid, dims)


def _valid(node):
    root = CadNode("root")
    root.add(node)
    return validate(root)


def _find(node, name):
    if node.name == name:
        return node
    for c in node.children:
        hit = _find(c, name)
        if hit is not None:
            return hit
    return None


def open_edges(tris):
    """Directed edges without their exact twin (no rounding): 0 for a
    closed, consistently wound surface."""
    from collections import Counter
    edges = Counter()
    for t in tris:
        for i in range(3):
            edges[(t[i], t[(i + 1) % 3])] += 1
    return sum(1 for (a, b), n in edges.items() if edges[(b, a)] != n)


def test_every_instrument_is_in_the_library():
    assert len(MUSIC) == len(M.PARTS) + len(MM.PARTS) >= 30


@pytest.mark.parametrize("pid", MUSIC)
def test_every_instrument_builds_in_every_size_and_finish(pid):
    spec = library.PARTS[pid]
    colours = spec.get("colors") or [None]
    for size in spec["sizes"]:
        for colour in {colours[0], colours[-1]}:
            extra = {"_color": colour} if colour else {}
            node = _build(pid, size, **extra)
            assert _valid(node) == {}, (pid, size, colour)
    tris = mesh.tessellate(_build(pid), fn=24)
    assert tris
    assert min(p[2] for t in tris for p in t) >= -0.5, pid   # on the floor


@pytest.mark.parametrize("pid", MUSIC)
def test_every_instrument_has_a_submenu(pid):
    label = library.PARTS[pid]["label"]
    groups = dict(M.GROUPS, **MM.GROUPS)
    assert any(label.startswith(s) for starts in groups.values()
               for s in starts), label


def test_notes_and_frequencies():
    assert M.midi("A4") == 69 and M.midi("C4") == 60
    assert M.midi("F#3") == 54 and M.midi("Bb2") == 46
    assert M.freq(69) == pytest.approx(440.0)
    assert M.freq(81) == pytest.approx(880.0)
    assert M.note_name(M.midi("C#5")) == "C#5"


def test_the_keyboard_layout_puts_accidentals_between_naturals():
    layout, naturals = M.keyboard_layout(M.midi("A0"), M.midi("C8"), 23.5)
    assert len(layout) == 88 and naturals == 52
    c4 = [x for m, x, s in layout if m == 60][0]
    cs4 = [x for m, x, s in layout if m == 61][0]
    d4 = [x for m, x, s in layout if m == 62][0]
    assert cs4 == pytest.approx((c4 + d4) / 2)


def test_bars_shorten_up_the_scale_and_follow_the_beam_law():
    lo = M.midi("A2")
    Ls = [M.bar_length(m, lo, 500.0, 0.5) for m in range(lo, lo + 25)]
    assert all(a > b for a, b in zip(Ls, Ls[1:]))
    # a plain bar: two octaves up (f x 4) is half the length
    assert Ls[24] == pytest.approx(250.0)


def test_marimba_has_a_bar_and_a_resonator_per_note():
    node = _build("music_marimba", "4.3 octaves (A2–C7)")
    notes = M.midi("C7") - M.midi("A2") + 1
    bars = _find(node, "Bars A2–C7")
    tubes = _find(node, "Resonator tubes")
    assert bars.params["values"].count("[") == notes
    assert tubes.params["values"].count("[") == notes
    # the lowest resonator is the longest: a quarter wave, capped
    first = tubes.params["values"].split("],")[0].strip("[ ").split(",")
    assert float(first[3]) == pytest.approx(
        min(M.closed_pipe(M.midi("A2"), float(first[4])), 860.0 * 0.8),
        abs=0.01)


def test_closed_pipe_is_a_quarter_wave():
    # A4 = 440 Hz: 343 m/s / 4 / 440 = 194.9 mm
    assert M.closed_pipe(69) == pytest.approx(194.886, abs=0.01)


def test_pan_pipes_are_cut_to_their_notes():
    notes = MM.pan_notes("C5", 8)
    assert [M.note_name(n) for n in notes] == [
        "C5", "D5", "E5", "F5", "G5", "A5", "B5", "C6"]
    nai = MM.pan_notes("B3", 20)
    assert M.note_name(nai[0]) == "B3" and M.note_name(nai[-1]) == "G6"
    assert all(M.is_sharp(n) is False or M.note_name(n)[0] == "F"
               for n in nai)                                  # G major
    node = _build("music_pan_pipes", "8 pipes (C5 major)")
    rows = [r.strip("[] ").split(",") for r in
            _find(node, "8 pipes C5–C6").params["values"].split("],")]
    lengths = [float(r[2]) for r in rows]
    assert lengths == sorted(lengths, reverse=True)
    # the octave pipe is about half the tonic's
    assert lengths[-1] / lengths[0] == pytest.approx(0.5, abs=0.03)


def test_frets_follow_the_twelfth_root_of_two():
    assert M.fret_position(650.0, 12) == pytest.approx(325.0)
    assert M.fret_position(650.0, 24) == pytest.approx(487.5)


@pytest.mark.parametrize("key", sorted(MM.GUITARS))
def test_every_string_spans_the_scale(key):
    cfg = MM.GUITARS[key]
    node = MM.guitar(cfg, {}, ("#000", "Plastic") if cfg["kind"] ==
                     "electric" else ("#eee", "#333"))
    strings = _find(node, "Strings")
    assert len(strings.children) == cfg["strings"]
    for s in strings.children:
        assert s.params["y1"] - s.params["y2"] == pytest.approx(
            -cfg["scale"], abs=0.01)
    # the neck joins the body at the fret the cfg says
    frets = _find(node, f"{cfg['frets']} frets")
    rows = [float(r.strip("[] ").split(",")[0])
            for r in frets.params["values"].split("],")]
    assert rows[cfg["joint"] - 1] == pytest.approx(cfg["L"], abs=0.01)


def test_the_violin_arch_is_one_closed_solid_and_the_f_holes_sit_on_it():
    node = _build("music_violin", "Violin (4/4)")
    body = _find(node, "Arched body")
    assert open_edges(mesh.tessellate(body)) == 0
    cfg = MM.BOWED["Violin (4/4)"]
    base = cfg["arch"] + cfg["rib"]
    assert MM.arch_z(0.0, cfg["L"] / 2, cfg, base) == pytest.approx(
        base + cfg["arch"])
    edge = MM.half_width(0.5, cfg["L"], cfg["lower"], cfg["waist"],
                         cfg["upper"])
    assert MM.arch_z(edge - 0.01, cfg["L"] / 2, cfg, base) == pytest.approx(
        base, abs=1.0)


def test_wind_chimes_are_tuned_by_the_inverse_square_root():
    node = _build("music_wind_chimes", "5 tubes (C pentatonic)")
    rows = [r.strip("[] ").split(",") for r in
            _find(node, "5 tubes").params["values"].split("],")]
    lengths = [float(r[3]) for r in rows]
    # C5 -> A5 is 9 semitones: L ratio 2^(-9/24)
    assert lengths[-1] / lengths[0] == pytest.approx(2 ** (-9 / 24),
                                                     abs=1e-3)


def test_an_instrument_survives_the_openscad_round_trip():
    node = _build("music_toy_xylophone")
    root = CadNode("root")
    root.add(node)
    back, _warnings = scadparse.parse_scad(root.to_scad())
    assert len(mesh.tessellate(back, fn=24)) == \
        len(mesh.tessellate(root, fn=24))

"""SolidWorks' Wrap (2026-11-14, the user): a flat sketch wrapped round
a cylinder, embossed or debossed.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

BODY = "cylinder(r = 20, h = 40, $fn = 96);"
SKETCH = "translate([-10, 15]) square([20, 10]);"


def _vol(tris):
    from khervecad import analysis
    return analysis.mass_properties(tris)["volume"]


def _tess(code):
    from khervecad import mesh, scadparse
    root = scadparse.parse_scad(code)[0]
    return root, [tuple(t[:3]) for t in mesh.tessellate(root)]


def _band(kind, depth=1.0):
    """The volume a 20 x 10 sketch adds / takes, wrapped on r = 20."""
    R = 20.0
    a = 20.0 / R
    outer, inner = (R + depth, R) if kind == "emboss" else (R, R - depth)
    return a / 2 * (outer ** 2 - inner ** 2) * 10


def test_emboss_adds_the_band_and_deboss_cuts_it():
    _r, base = _tess(BODY)
    for kind, sign in (("emboss", 1), ("deboss", -1)):
        _r, t = _tess('kcad_wrap(kind = "%s", depth = 1) { %s %s }'
                      % (kind, BODY, SKETCH))
        assert sign * (_vol(t) - _vol(base)) == pytest.approx(
            _band(kind), rel=0.04), kind


def test_the_sketch_lies_on_the_curve_where_drawn():
    """Its x is the distance round, its y the height: a 20 wide sketch
    at 15..25 up, angle 0 (+X), sits between z 15 and 25, at +X."""
    _r, t = _tess('kcad_wrap(depth = 2) { %s %s }' % (BODY, SKETCH))
    out = [p for tri in t for p in tri if math.hypot(p[0], p[1]) > 20.5]
    assert out
    assert min(p[2] for p in out) == pytest.approx(15, abs=0.05)
    assert max(p[2] for p in out) == pytest.approx(25, abs=0.05)
    assert all(p[0] > 15 for p in out)
    assert max(math.hypot(p[0], p[1]) for p in out) == pytest.approx(
        22, abs=0.05)


def test_the_start_angle_turns_it_round():
    _r, t = _tess('kcad_wrap(depth = 2, angle = 90) { %s %s }'
                  % (BODY, SKETCH))
    out = [p for tri in t for p in tri if math.hypot(p[0], p[1]) > 20.5]
    assert all(p[1] > 15 for p in out)          # now at +Y


def test_the_wrap_round_trips_and_is_closed():
    from collections import Counter
    root, t = _tess('kcad_wrap(kind = "deboss", depth = 1.5) { %s %s }'
                    % (BODY, SKETCH))
    node = next(n for n in root.walk() if n.type == "wrap")
    assert node.params["kind"] == "deboss" and node.params["depth"] == 1.5
    assert "kcad_wrap(" in root.to_scad()
    k = lambda p: tuple(round(c, 5) for c in p)          # noqa: E731
    e = Counter()
    for a, b, c in t:
        for x, y in ((a, b), (b, c), (c, a)):
            e[(k(x), k(y))] += 1
    assert all(e[(y, x)] == n for (x, y), n in e.items())


@pytest.fixture
def window():
    from PyQt5.QtWidgets import QApplication
    from khervecad.mainwindow import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    yield w
    w._dirty = False
    w.close()


def test_the_wrap_button_writes_a_text_and_the_window_changes_it(window):
    from khervecad import mesh, scadparse
    cyl = scadparse.parse_scad(BODY)[0].children[0]
    window.model.root.add(cyl)
    window.model.structure_changed.emit()
    base = _vol(mesh.tessellate(window.model.root))
    window.builder.active_tree().select_nodes([cyl])
    window._apply_operation("wrap")
    node = next(n for n in window.model.root.walk() if n.type == "wrap")
    panel = window._wrap_panel
    assert panel is not None and panel.isVisible()
    text = next(c for c in node.children if c.type == "text")
    assert text.params["text"] == "KCAD"
    panel.fields["text"].setText("HELLO")
    assert text.params["text"] == "HELLO"
    raised = _vol(mesh.tessellate(window.model.root))
    assert raised > base + 20                      # letters stand out
    panel.fields["kind"].setCurrentIndex(
        panel.fields["kind"].findData("deboss"))
    assert _vol(mesh.tessellate(window.model.root)) < base - 20
    panel.ok.click()
    assert not panel.isVisible() and node.parent is not None


def test_cancel_takes_the_wrap_away(window):
    from khervecad import scadparse
    cyl = scadparse.parse_scad(BODY)[0].children[0]
    window.model.root.add(cyl)
    window.model.structure_changed.emit()
    window.builder.active_tree().select_nodes([cyl])
    window._apply_operation("wrap")
    window._wrap_panel.cancel.click()
    assert not any(n.type in ("wrap", "text")
                   for n in window.model.root.walk())
    assert any(n.type == "cylinder" for n in window.model.root.walk())

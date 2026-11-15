"""The sheet metal Jog (2026-11-15, Exercise "Jog Feature in SolidWorks
Sheet Metal"): geometry of two opposite bends from one line, holes and
slots that follow their panel, and the ribbon's Jog button with its
ToolPanel driven by real mouse clicks (two clicks for the bend line, a
click on the side that stays fixed, the offset / angle rows, OK).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAction

from test_lever_by_mouse import win, _button_for, _move, _wait  # noqa: F401
from khervecad import sheet_body as sb, sheet_metal_ops as ops

PLATE = [[0, 0], [100, 0], [100, 45], [0, 45]]


def _params(**kw):
    p = dict(sb._DEFAULTS)
    p["outline"] = [list(q) for q in PLATE]
    p.update(kw)
    return p


def _vol(tris):
    return sum(sb._dot(a, sb._cross(b, c)) for a, b, c in tris) / 6


def _box(tris):
    return [(min(v[k] for t in tris for v in t),
             max(v[k] for t in tris for v in t)) for k in range(3)]


JOG = [30, -1, 30, 46, 20, 60, 0, 0, 3, -1, 1]       # right side fixed, up


def test_a_jog_steps_the_far_side_up_by_the_offset():
    body = sb.build(_params(jogs=[JOG]))
    assert not body.errors
    assert len(body.bends) == 2
    assert [round(b["angle"]) for b in body.bends] == [60, -60]
    box = _box(sb.folded_tris(body))
    # outer faces 20 apart (outside dimension) + the 2 mm sheet
    assert box[2][0] == pytest.approx(0, abs=1e-6)
    assert box[2][1] == pytest.approx(22, abs=1e-6)
    # the fixed side did not move, the far side went left past the plate
    assert box[0][1] == pytest.approx(100, abs=1e-6)
    far = body.extra[-1]
    zs = {round(far.frame.at(q, d)[2], 6) for q in far.poly for d in (0, 2)}
    assert zs == {20.0, 22.0}                       # parallel to the base


def test_the_blank_grows_by_the_web_and_stays_one_solid():
    from khervecad import csg
    body = sb.build(_params(jogs=[JOG]))
    pat = sb.flat_pattern(body)
    grown = pat["width"] - 100
    web = 2 * body.bends[0]["allowance"] + (
        (20 - 2 * 3.0 * (1 - math.cos(math.radians(60)))) /
        math.sin(math.radians(60)))
    assert grown == pytest.approx(web, abs=0.01)
    tris = sb.folded_tris(body)
    # the folded part's volume = the (longer) blank's
    flat = _vol(sb.flat_tris(pat, body.t))
    assert abs(_vol(tris) - flat) / flat < 0.01
    if csg.available():
        import numpy as np
        m = csg._m
        pts, faces = {}, []
        for t in tris:
            row = []
            for v in t:
                k = tuple(round(c, 5) for c in v)
                pts.setdefault(k, len(pts))
                row.append(pts[k])
            faces.append(row)
        mm = m.Manifold(m.Mesh(
            vert_properties=np.array(list(pts), dtype=np.float32),
            tri_verts=np.array(faces, dtype=np.uint32)))
        assert len(mm.decompose()) == 1


def test_dimension_position_moves_the_rise():
    heights = []
    for dim in (0, 1, 2):
        row = list(JOG)
        row[7] = dim
        box = _box(sb.folded_tris(sb.build(_params(jogs=[row]))))
        heights.append(box[2][1])
    # outside 20 -> top 22; inside offset 20 -> bottom-to-bottom 22;
    # total 20 -> top 20
    assert heights == pytest.approx([22.0, 24.0, 20.0], abs=1e-6)


def test_too_small_an_offset_is_refused():
    row = list(JOG)
    row[4] = 1.0
    body = sb.build(_params(jogs=[row]))
    assert body.errors and "too small" in body.errors[0]


def test_holes_and_slots_follow_their_panel():
    from khervecad import csg
    if not csg.available():
        pytest.skip("Manifold missing")
    holes = [[10, 10, 8], [10, 35, 8], [90, 10, 8], [90, 35, 8]]
    body = sb.build(_params(jogs=[JOG], holes=holes,
                            slots=[[50, 7.5, 50, 37.5, 6]]))
    assert not body.errors
    cuts = {id(p): len(p.cuts) for p in body.all_panels()}
    assert sorted(cuts.values()) == [0, 2, 3]       # web 0, far 2, base 3
    plain = _vol(sb.folded_tris(sb.build(_params(jogs=[JOG]))))
    cut = _vol(sb.folded_tris(body))
    area = 4 * math.pi * 16 + 6 * 30 + math.pi * 9
    assert plain - cut == pytest.approx(area * 2, rel=0.02)
    # a hole across the cut is an error, not a silent drop
    bad = sb.build(_params(jogs=[JOG], holes=[[30, 20, 8]]))
    assert bad.errors


def test_jog_round_trips_through_the_document(tmp_path):
    from khervecad import document
    from khervecad.model import DocumentModel
    model = DocumentModel()
    node = ops.insert_base(model, PLATE)
    ops.add_jog(model, node, (30, -1), (30, 46), 20, 60)
    ops.add_hole(model, node, 90, 10, 8)
    path = tmp_path / "jog.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    body = next(n for n in other.root.walk() if n.type == "sheet_body")
    assert body.params["jogs"] == [JOG]
    assert body.params["holes"] == [[90.0, 10.0, 8.0]]


# ================================================================ mouse
def _px(v3, p):
    q = v3._project(*v3._camera(), p)
    return QPoint(int(round(q[0])), int(round(q[1])))


def _click(v3, p):
    _move(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(80)


def _plate(win):
    from khervecad.model import DocumentModel  # noqa: F401
    model = win.model
    body = ops.insert_base(model, PLATE)
    ops.add_hole(model, body, 90, 10, 8)
    win.builder.active_tree().select_nodes([body])
    win.ribbon.show_tab("sheetmetal")
    QTest.qWait(60)
    return body


def _jog_button(win):
    act = next(a for a in win.findChildren(QAction)
               if a.data() == "sm_jog" and a.isEnabled())
    return act, _button_for(win, act)


def test_jog_by_mouse_two_clicks_a_side_and_the_rows(win):
    body = _plate(win)
    act, button = _jog_button(win)
    QTest.mouseClick(button, Qt.LeftButton)
    v3 = win.view3d
    assert _wait(lambda: v3._pick_cb is not None), "Jog asks for no click"
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(150)
    from khervecad import sheet_jog_ui
    tool = sheet_jog_ui._OPEN[id(win)]
    panel = tool.panel
    assert panel.isVisible() and not panel.ok.isEnabled()
    # the bend line: two clicks on the sheet, the second a little off
    # vertical (the tool makes it straight)
    _click(v3, _px(v3, (30.0, 8.0, 2.0)))
    assert _wait(lambda: v3._pick_cb is not None)
    _click(v3, _px(v3, (30.3, 38.0, 2.0)))
    assert tool.p[1] is not None, "the line needs two clicks"
    assert tool.p[0][0] == tool.p[1][0]             # straightened
    # the fixed face: a click on the big right part
    assert _wait(lambda: v3._pick_cb is not None)
    _click(v3, _px(v3, (70.0, 22.0, 2.0)))
    assert tool.side == -1
    assert panel.ok.isEnabled()
    jogs = body.params["jogs"]
    assert len(jogs) == 1
    # typed: the line at x = 30, 20 mm offset at 60 degrees
    panel.fields["x1"].setValue(30.0)
    panel.fields["x2"].setValue(30.0)
    panel.fields["offset"].setValue(20.0)
    panel.fields["angle"].setValue(60.0)
    QTest.qWait(60)
    row = body.params["jogs"][0]
    assert row[0] == row[2] == 30.0
    assert row[4:6] == [20.0, 60.0] and row[8] == 3 and row[9] == -1
    pos = panel.fields["pos"]
    assert pos.currentData() == 3
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(80)
    assert tool.closed and id(win) not in sheet_jog_ui._OPEN
    assert len(body.params["jogs"]) == 1
    d = ops.describe(win.model, body)
    assert d["bends"] == 2 and not d["errors"]
    tris = sb.folded_tris(ops.built(win.model, body))
    assert _box(tris)[2][1] == pytest.approx(22, abs=1e-6)


def test_jog_cancel_takes_it_back(win):
    body = _plate(win)
    act, button = _jog_button(win)
    QTest.mouseClick(button, Qt.LeftButton)
    v3 = win.view3d
    assert _wait(lambda: v3._pick_cb is not None)
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(150)
    from khervecad import sheet_jog_ui
    tool = sheet_jog_ui._OPEN[id(win)]
    _click(v3, _px(v3, (30.0, 8.0, 2.0)))
    assert _wait(lambda: v3._pick_cb is not None)
    _click(v3, _px(v3, (30.0, 38.0, 2.0)))
    assert _wait(lambda: v3._pick_cb is not None)
    _click(v3, _px(v3, (70.0, 22.0, 2.0)))
    assert body.params["jogs"]
    QTest.mouseClick(tool.panel.cancel, Qt.LeftButton)
    QTest.qWait(60)
    assert not body.params["jogs"]
    assert tool.closed and id(win) not in sheet_jog_ui._OPEN

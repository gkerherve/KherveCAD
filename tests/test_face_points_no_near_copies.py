"""A sketch's snap points hold no near copy of a corner (2026-11-22):
the section a hair behind the face is meshed 0.03 mm off its corners
(49.968 for 50), and such a copy won a click on the exact corner, so a
rectangle drawn to the part's corner came out 0.03 mm short.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401

CODE = ("difference() { translate([-50, 0, -12]) cube([100, 160, 24]);"
        " translate([-26, -1, -12.01]) cube([52, 170, 10]);"
        " translate([38, -1, 0]) cube([12.01, 170, 12.01]); }")


def test_no_corner_has_a_copy_a_hair_away(win):
    from khervecad import face_outline, refgeom_ui
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(80)
    group = refgeom_ui.sketch_on(win, origin=(0, 0, 0), normal=(0, -1, 0),
                                 label="Face", open_2d=False)
    from khervecad import meshedit_ui
    part = next(n for n, _t in meshedit_ui._parts(win) if n is not group)
    face_outline.show(win, group, part)
    pts = win.view2d.scene().face_outline["points"]
    near = [p for p in pts if abs(p[0] - 50) < 0.1 and abs(p[1] - 12) < 0.1]
    assert near and all(p[0] == 50.0 and p[1] == 12.0 for p in near), near


def test_a_cut_tool_is_not_part_of_the_body_a_click_can_choose(win):
    """The parts a click chooses between hold the body only: the cutter
    of a Difference (here 322 long) is not solid (2026-11-22)."""
    from khervecad import meshedit_ui
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(80)
    ys = [p[1] for _n, tris in meshedit_ui._parts(win)
          for t in tris for p in t[:3]]
    assert min(ys) > -0.5 and max(ys) < 160.5

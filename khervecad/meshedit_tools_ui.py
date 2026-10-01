"""Edit Mode's box-modelling tools on the 3D view: Inset (I), Loop Cut
(Ctrl+R), Knife (K), Bridge and Spin — meshedit_more.py's geometry
driven by an EditSession (meshedit_ui.py, past its size, keeps only the
hooks). Each lands through the session's ``_apply``, so one that would
open the solid is refused with the reason.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPen

from . import language, meshedit, meshedit_more

#: the knife's line on the view
KNIFE_PEN = QColor("#ff3030")


def _mean_edge(session):
    sel = set(session.selection)
    lengths = []
    for i in meshedit.selected_faces(session.faces, sel):
        face = session.faces[i]
        n = len(face)
        for k in range(n):
            a, b = session.points[face[k]], session.points[face[(k + 1) % n]]
            lengths.append(math.dist(a, b))
    return sum(lengths) / len(lengths) if lengths else 1.0


def inset(session, thickness=None, depth=0.0, individual=False,
          follow=True):
    """I: inset the selected faces, then scale the inner ring with the
    mouse (a click confirms) — Blender's I then drag."""
    before = ([list(p) for p in session.points],
              [list(f) for f in session.faces], set(session.selection))
    if thickness is None:
        thickness = 0.2 * _mean_edge(session)
    try:
        result = meshedit_more.inset(session.points, session.faces,
                                     session.selection, thickness, depth,
                                     individual)
    except meshedit_more.EditFailed as exc:
        session.say(language.tr("Inset: {why}").format(why=str(exc)))
        return False
    if not session._apply(result, "Inset"):
        return False
    if follow:
        session.begin("scale", before=before)
    return True


def loop_cut(session, x=None, y=None, cuts=1):
    """Ctrl+R: an edge loop through the edge under the mouse."""
    if x is None:
        pos = session._cursor()
        x, y = pos.x(), pos.y()
    hit = session.edge_at(x, y)
    if hit is None:
        session.say(language.tr("Loop cut: point at an edge of a quad "
                                "first, then press Ctrl+R."))
        return False
    a, b, _t = hit
    try:
        result = meshedit_more.loop_cut(session.points, session.faces, a, b,
                                        0.5, cuts)
    except meshedit_more.EditFailed as exc:
        session.say(language.tr("Loop cut: {why}").format(why=str(exc)))
        return False
    if session._apply(result, "Loop cut"):
        session.say(language.tr("Loop cut: the new loop is selected — G "
                                "slides it, S widens it."), 4000)
        return True
    return False


def bridge(session):
    try:
        result = meshedit_more.bridge(session.points, session.faces,
                                      session.selection)
    except meshedit_more.EditFailed as exc:
        session.say(language.tr("Bridge: {why}").format(why=str(exc)))
        return False
    return session._apply(result, "Bridge")


def spin(session, angle=90.0, steps=8, taper=1.0, radius=None):
    """Spin the selected faces about the VIEW's axis, through a pivot
    *radius* mm to the right of the selection on screen (default: the
    selection's own size) — a horn curling away from you."""
    pivot = session._pivot()
    if pivot is None:
        session.say(language.tr("Spin: select the faces to spin."))
        return False
    _project, _eye, right, _up, forward = session._camera()
    if radius is None:
        radius = max(2.0 * _mean_edge(session), 1.0)
    world_origin = [pivot[k] + right[k] * radius for k in range(3)]
    origin = session._to_local_point(world_origin)
    axis = meshedit.local_delta(session.inverse, forward)
    try:
        result = meshedit_more.spin(session.points, session.faces,
                                    session.selection, origin, axis, angle,
                                    steps, taper)
    except meshedit_more.EditFailed as exc:
        session.say(language.tr("Spin: {why}").format(why=str(exc)))
        return False
    return session._apply(result, "Spin")


# ------------------------------------------------------------- knife

def knife_start(session):
    session._knife = []
    session.say(language.tr("Knife: click where the cut starts, then "
                            "where it ends; Esc cancels."), 6000)
    session.view.update()


def knife_click(session, pos):
    """A click while the knife is armed. Returns True when handled."""
    pts = session._knife
    pts.append(QPointF(pos))
    if len(pts) < 2:
        session.view.update()
        return True
    session._knife = None
    a, b = pts
    if (a - b).manhattanLength() < 4:
        session.say(language.tr("Knife: the line is too short."))
        return True
    knife_line(session, a.x(), a.y(), b.x(), b.y())
    return True


def _ray(view, x, y):
    from .sculpt_ui import screen_ray
    return screen_ray(view, x, y)


def knife_line(session, x0, y0, x1, y1):
    """Cut the faces facing the camera that the screen line crosses."""
    view = session.view
    o0, d0 = _ray(view, x0, y0)
    o1, d1 = _ray(view, x1, y1)
    if view.projection == "Orthographic":
        along = [o1[k] - o0[k] for k in range(3)]
        n_world = meshedit._cross(along, d0)
    else:
        n_world = meshedit._cross(d0, d1)
    if math.sqrt(sum(c * c for c in n_world)) < 1e-12:
        session.say(language.tr("Knife: draw a line across the part."))
        return False
    m = session.matrix
    # a plane's normal maps by the transpose of the linear part
    n_local = [sum(m[r][c] * n_world[r] for r in range(3)) for c in range(3)]
    p_local = session._to_local_point(o0)
    proj, front, _vis = session._screen()
    lo_x, hi_x = min(x0, x1) - 2, max(x0, x1) + 2
    lo_y, hi_y = min(y0, y1) - 2, max(y0, y1) + 2
    only = []
    for i, (face, f) in enumerate(zip(session.faces, front)):
        if not f and not session.xray:
            continue
        ps = [proj[v] for v in face]
        if any(p is None for p in ps):
            continue
        xs, ys = [p[0] for p in ps], [p[1] for p in ps]
        if max(xs) >= lo_x and min(xs) <= hi_x and max(ys) >= lo_y \
                and min(ys) <= hi_y:
            only.append(i)
    try:
        result = meshedit_more.knife(session.points, session.faces,
                                     p_local, n_local, only)
    except meshedit_more.EditFailed as exc:
        session.say(language.tr("Knife: {why}").format(why=str(exc)))
        return False
    return session._apply(result, "Knife")


def paint_knife(session, painter):
    pts = getattr(session, "_knife", None)
    if not pts:
        return
    pen = QPen(KNIFE_PEN)
    pen.setWidthF(2.0)
    pen.setStyle(Qt.DashLine)
    painter.setPen(pen)
    end = session._hover if session._hover is not None else pts[-1]
    painter.drawLine(pts[0], QPointF(end))

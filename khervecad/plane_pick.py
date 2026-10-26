"""Picking a main plane in the 3D view (2026-10-26, the user: "in
SolidWorks we select the plane we want — XZ — and start sketching; here
we see the XYZ but it's not selectable").

Create Sketch with nothing selected draws SolidWorks' three planes —
Front Plane (XZ), Top Plane (XY), Right Plane (YZ) — as see-through
squares through the origin; the one under the cursor lights up and a
click sketches on it (`normal_to.turn_to`). Esc, or a click off every
plane, cancels. Drawn through the view's `overlay_painters` and
`click_hooks` / `move_hooks`, so nothing in the document changes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: SolidWorks' names, the view2d plane each opens, the two world axes
PLANES = [("Front Plane", "Front (XZ)", (0, 2)),
          ("Top Plane", "Top (XY)", (0, 1)),
          ("Right Plane", "Side (YZ)", (1, 2))]
NAMES = {plane: name for name, plane, _a in PLANES}
MIN_HALF = 25.0                         # mm: half a plane's side at least


def name_of(plane):
    """'Front Plane' for 'Front (XZ)'."""
    return NAMES.get(plane, plane)


def active(window):
    return bool(getattr(window, "_plane_pick", None))


def _half(window):
    mesh = getattr(window.view3d, "model_mesh", None) or \
        getattr(window.view3d, "mesh", None) or []
    reach = 0.0
    for tri in mesh[:20000]:
        for p in tri[:3]:
            try:
                reach = max(reach, abs(p[0]), abs(p[1]), abs(p[2]))
            except (TypeError, IndexError):
                break
    return max(MIN_HALF, reach * 0.75)


def _polygons(window, project):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QPolygonF
    h = window._plane_pick["half"]
    out = []
    for name, plane, (a, b) in PLANES:
        pts = []
        for sa, sb in ((-h, -h), (h, -h), (h, h), (-h, h)):
            v = [0.0, 0.0, 0.0]
            v[a], v[b] = sa, sb
            q = project(v)
            if q is None:
                break
            pts.append(QPointF(q[0], q[1]))
        if len(pts) == 4:
            out.append((plane, name, QPolygonF(pts)))
    return out


def _area(poly):
    s = 0.0
    for i in range(poly.size()):
        p, q = poly.at(i), poly.at((i + 1) % poly.size())
        s += p.x() * q.y() - q.x() * p.y()
    return abs(s) / 2


def hit(window, pos):
    """The plane under *pos*: of those containing it, the one seen most
    squarely (the biggest on screen)."""
    from PyQt5.QtCore import QPointF, Qt
    polys = window._plane_pick.get("polys") or []
    found = [(_area(p), plane) for plane, _n, p in polys
             if p.containsPoint(QPointF(pos), Qt.OddEvenFill)]
    return max(found)[1] if found else None


def paint(window, painter, project):
    state = getattr(window, "_plane_pick", None)
    if not state:
        return
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QFont, QPen
    from . import language
    polys = _polygons(window, project)
    state["polys"] = polys
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    font = QFont(painter.font())
    font.setBold(True)
    painter.setFont(font)
    for plane, name, poly in polys:
        hot = plane == state.get("hover")
        painter.setPen(QPen(QColor("#1565c0"), 2.5 if hot else 1.2))
        painter.setBrush(QColor(66, 133, 244, 110 if hot else 38))
        painter.drawPolygon(poly)
        corner = poly.at(3)
        painter.setPen(QColor("#0d47a1"))
        painter.drawText(corner.x() + 4, corner.y() + 14,
                         language.tr(name))
    painter.restore()


def move(window, pos):
    state = getattr(window, "_plane_pick", None)
    if not state:
        return False
    plane = hit(window, pos)
    if plane != state.get("hover"):
        state["hover"] = plane
        window.view3d.update()
    return False                         # the view still orbits


def press(window, pos):
    state = getattr(window, "_plane_pick", None)
    if not state:
        return False
    plane = hit(window, pos)
    if plane is None:
        return False                     # a drag on empty space orbits
    stop(window)
    from . import normal_to
    normal_to.turn_to(window, plane)
    return True


def start(window):
    """Show the three planes; the next click on one sketches there."""
    from . import language
    window._plane_pick = {"half": _half(window), "hover": None}
    msg = language.tr("Select a plane to sketch on: Front, Top or Right "
                      "Plane · Esc cancels")
    window.statusBar().showMessage(msg, 10000)
    flash = getattr(window.view3d, "flash", None)
    if flash is not None:
        try:
            flash(msg)
        except Exception:
            pass
    window.view3d.update()


def stop(window):
    if getattr(window, "_plane_pick", None):
        window._plane_pick = None
        window.view3d.update()

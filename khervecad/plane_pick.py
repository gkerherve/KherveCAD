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
    # big enough to read on an empty document: a share of the view
    seen = getattr(window.view3d, "distance", 0.0) * 0.22
    # past the part on every side: at 0.75 a plate's Top plane lay wholly
    # under the plate, and a click on it sketched on the plate's face
    return max(MIN_HALF, reach * 1.2, seen)


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
    """SolidWorks' look: light blue see-through squares with a thin
    edge, each name in italics along its top edge, and the lines where
    they cross dashed."""
    state = getattr(window, "_plane_pick", None)
    if not state:
        return
    import math
    from PyQt5.QtCore import QLineF, QPointF, Qt
    from PyQt5.QtGui import QColor, QFont, QPen
    from . import language
    polys = _polygons(window, project)
    state["polys"] = polys
    h = state["half"]
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    edge = QColor(70, 120, 210)
    for plane, name, poly in polys:
        hot = plane == state.get("hover")
        painter.setPen(QPen(edge, 2.2 if hot else 1.1))
        painter.setBrush(QColor(110, 160, 235, 95 if hot else 34))
        painter.drawPolygon(poly)
    # where the planes cross: the three axes, dashed
    dash = QPen(QColor(40, 40, 40), 1.0, Qt.DashLine)
    painter.setPen(dash)
    for axis in range(3):
        a, b = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
        a[axis], b[axis] = -h, h
        pa, pb = project(a), project(b)
        if pa is not None and pb is not None:
            painter.drawLine(QLineF(pa[0], pa[1], pb[0], pb[1]))
    # the names, along each plane's upper edge (corners 3 -> 2)
    font = QFont(painter.font())
    font.setItalic(True)
    font.setBold(True)
    font.setPointSizeF(max(9.0, font.pointSizeF() * 1.25))
    painter.setFont(font)
    painter.setPen(QColor(70, 120, 210))
    for plane, name, poly in polys:
        p0, p1 = poly.at(3), poly.at(2)
        if p1.x() < p0.x():                 # read left to right
            p0, p1 = poly.at(0), poly.at(1)
            if p1.x() < p0.x():
                p0, p1 = p1, p0
        ang = math.degrees(math.atan2(p1.y() - p0.y(), p1.x() - p0.x()))
        if abs(ang) > 80:                    # edge-on: nothing to read
            continue
        painter.save()
        painter.translate(QPointF(p0.x(), p0.y()))
        painter.rotate(ang)
        painter.drawText(QPointF(8, painter.fontMetrics().ascent() + 3),
                         language.tr(name))
        painter.restore()
    painter.restore()


def _all_seen(window):
    """True when every plane is seen at a slant (none edge-on)."""
    view = window.view3d
    import math
    yaw, pitch = math.radians(view.yaw), math.radians(view.pitch)
    # the view direction's components: none near zero = all three seen
    d = (abs(math.cos(pitch) * math.cos(yaw)),
         abs(math.cos(pitch) * math.sin(yaw)), abs(math.sin(pitch)))
    return min(d) > 0.25


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
    cb = state.get("on_plane")
    stop(window)
    if cb is not None:                   # a tool asked which plane
        cb(plane)
        return True
    from . import normal_to
    normal_to.turn_to(window, plane)
    return True


def start(window, on_plane=None):
    """Show the three planes; the next click on one sketches there — or,
    given *on_plane*, hands it the plane clicked instead (the Extrude
    window's Sketch plane box)."""
    from . import language
    window._plane_pick = {"half": _half(window), "hover": None,
                          "on_plane": on_plane}
    if not _all_seen(window):
        # square on to one plane the other two are edge-on: turn to the
        # isometric so all three show, as SolidWorks shows them
        try:
            from . import view_anim
            view = window.view3d
            yaw, pitch = view.VIEWS["Isometric"]
            if getattr(view, "projection", "") == "Orthographic":
                view.projection = "Perspective"
            view_anim.glide_3d(view, dict(
                yaw=yaw, pitch=pitch, target=[0.0, 0.0, 0.0],
                distance=view.distance))
        except Exception:
            pass
    msg = language.tr("Select a plane (Front, Top or Right Plane) or a "
                      "face of a part to sketch on · Esc cancels")
    window.statusBar().showMessage(msg, 10000)
    _arm(window, msg)
    window.view3d.update()


def _arm(window, msg):
    """The view's pick mode over every part: a face clicked is a face
    sketch (as Sketch on Face); a click elsewhere is tried against the
    planes — the release hook noted where it landed."""
    from . import face_sketch, language, meshedit_ui
    parts = meshedit_ui._parts(window) or []

    def picked(desc, node=None):
        state = getattr(window, "_plane_pick", None)
        if not state:
            return
        pos = state.pop("pos", None)
        if desc is not None and node is not None:
            if desc.get("kind") == "face" and not state.get("on_plane"):
                stop(window)
                face_sketch.make(window, node, desc["pos"], desc["dir"])
                return
            if pos is None or hit(window, pos) is None:
                window.statusBar().showMessage(language.tr(
                    "Click a flat FACE (not an edge), or a plane."), 5000)
                _arm(window, msg)
                return
        if pos is None:                  # Esc / Select: cancelled
            stop(window)
            return
        plane = hit(window, pos)
        if plane is None:                # empty space: keep asking
            _arm(window, msg)
            return
        cb = state.get("on_plane")
        stop(window)
        if cb is not None:
            cb(plane)
            return
        from . import normal_to
        normal_to.turn_to(window, plane)
    window.view3d.start_pick(
        picked, groups=parts, banner=msg,
        labeler=lambda desc, node: getattr(node, "name", ""))


def release(window, pos):
    """Note where a click lands (the pick callback has no position)."""
    state = getattr(window, "_plane_pick", None)
    if state:
        state["pos"] = pos
    return False


def stop(window):
    if getattr(window, "_plane_pick", None):
        window._plane_pick = None
        view = window.view3d
        if getattr(view, "_pick_cb", None) is not None:
            view.cancel_pick()
        view.update()

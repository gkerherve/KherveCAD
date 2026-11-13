# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""What the Boss / Cut choice window shows on the model while it is open
(2026-11-13, the user: "add as numbers each of the faces too ... toggles
to show or hide the faces, the sketches' regions and the planes").

- **Faces**: every flat face of the parts in view, numbered F1, F2...
  (largest first) at a point ON the face; the window can use one by its
  number, no click needed.
- **Sketch regions**: the closed areas of every sketch, numbered as
  Extruded Boss / Cut number them (`sketch_regions.start_any`).
- **Planes**: Front / Top / Right (off by default).

Painted through View3D's ``overlay_painters``; :func:`stop` takes it all
away again.
"""

from __future__ import annotations

FACE_COLOUR = (230, 120, 20)
#: faces smaller than this share of the largest are not numbered
MIN_SHARE = 0.004
MAX_FACES = 60
#: the sign of a projected, counter-clockwise (outward) triangle's area
#: on screen (y down) when it faces the eye
FACING_SIGN = -1


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _tri(t):
    """The three points of a triangle row (rows may carry flags)."""
    return t[0], t[1], t[2]


def flat_faces(parts):
    """``[{"node", "pos", "dir", "tris", "area"}]`` — the flat faces of
    *parts* [(node, world triangles)], largest first: coplanar triangles
    joined through shared corners."""
    out = []
    for node, tris in parts:
        groups = {}
        for t in tris:
            a, b, c = _tri(t)
            n = _cross(_sub(b, a), _sub(c, a))
            area2 = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
            if area2 < 1e-9:
                continue
            n = (n[0] / area2, n[1] / area2, n[2] / area2)
            d = n[0] * a[0] + n[1] * a[1] + n[2] * a[2]
            key = (round(n[0], 3), round(n[1], 3), round(n[2], 3),
                   round(d, 2))
            groups.setdefault(key, []).append(((a, b, c), area2 / 2, n))
        for items in groups.values():
            # connected pieces of one plane (two separate tops are two)
            parent = list(range(len(items)))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i
            seen = {}
            for i, (pts, _a, _n) in enumerate(items):
                for p in pts:
                    k = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
                    if k in seen:
                        parent[find(i)] = find(seen[k])
                    else:
                        seen[k] = i
            pieces = {}
            for i in range(len(items)):
                pieces.setdefault(find(i), []).append(items[i])
            for piece in pieces.values():
                area = sum(a for _p, a, _n in piece)
                cx = sum(a * (p[0][0] + p[1][0] + p[2][0]) / 3
                         for p, a, _n in piece) / area
                cy = sum(a * (p[0][1] + p[1][1] + p[2][1]) / 3
                         for p, a, _n in piece) / area
                cz = sum(a * (p[0][2] + p[1][2] + p[2][2]) / 3
                         for p, a, _n in piece) / area
                # the label ON the face: the triangle centre nearest the
                # area centre (a ring's centre is in its hole)
                centres = [((p[0][0] + p[1][0] + p[2][0]) / 3,
                            (p[0][1] + p[1][1] + p[2][1]) / 3,
                            (p[0][2] + p[1][2] + p[2][2]) / 3)
                           for p, _a, _n in piece]
                best = min(centres, key=lambda c: (c[0] - cx) ** 2 +
                           (c[1] - cy) ** 2 + (c[2] - cz) ** 2)
                out.append(dict(node=node, pos=best, dir=piece[0][2],
                                tris=[p for p, _a, _n in piece],
                                area=area))
    if not out:
        return []
    out.sort(key=lambda f: -f["area"])
    biggest = out[0]["area"]
    out = [f for f in out if f["area"] >= biggest * MIN_SHARE]
    return out[:MAX_FACES]


def face_name(face, number):
    return "Face %d (%s)" % (number, getattr(face["node"], "name", "") or
                             "part")


def start(window):
    """Work out what to show; the window's toggles then call :func:`show`."""
    from . import meshedit_ui
    state = dict(faces=[], regions=[], show_faces=True, show_regions=True,
                 show_planes=False)
    try:
        parts = meshedit_ui._parts(window)
        state["solid"] = [(id(n), [tuple(t[:3]) for t in tris])
                          for n, tris in parts]
        state["faces"] = flat_faces(parts)
    except Exception:
        state["faces"] = []
    try:
        state["regions"] = sketch_regions_shown(window)
    except Exception:
        state["regions"] = []
    window._choice_preview = state
    if not getattr(window, "_choice_preview_painter", False):
        window.view3d.overlay_painters.append(
            lambda painter, project: paint(window, painter, project))
        window._choice_preview_painter = True
    _sync_planes(window)
    window.view3d.update()
    return state


def show(window, faces=None, regions=None, planes=None):
    state = getattr(window, "_choice_preview", None)
    if state is None:
        return
    if faces is not None:
        state["show_faces"] = bool(faces)
    if regions is not None:
        state["show_regions"] = bool(regions)
    if planes is not None:
        state["show_planes"] = bool(planes)
    _sync_planes(window)
    window.view3d.update()


def _sync_planes(window):
    state = getattr(window, "_choice_preview", None)
    window._ref_force_planes = bool(state and state["show_planes"])


def stop(window):
    if getattr(window, "_choice_preview", None) is not None:
        window._choice_preview = None
        window._ref_force_planes = False
        window.view3d.update()


def sketch_regions_shown(window):
    """``[(world loops, world label point, number)]`` for every sketch's
    regions, numbered across them all (as `start_any` numbers them)."""
    from . import sketch_regions, sketch_section
    from .fillet_pick import _apply
    scope = window._render_scope()[0]
    if scope is window.model.root:
        return []                         # the assembly: a jumble
    shown, number = [], 0
    for cont in sketch_regions.all_sketches(window):
        try:
            shapes, _g = sketch_section.with_section(
                window, cont, sketch_regions.shapes_of(cont))
            face_list = sketch_regions.faces(shapes)
            mat = sketch_regions._frame(window, cont)
        except Exception:
            continue
        for cs, loops, *_m in face_list:
            number += 1
            world = [[_apply(mat, (x, y, 0.05)) for x, y in lp]
                     for lp in loops]
            at = sketch_regions.seed(cs)
            if at:
                shown.append((world, _apply(mat, (at[0], at[1], 0.05)),
                              number))
    return shown


def _hidden(window, state, i):
    """True when the part stands between face *i*'s label and the eye
    (the floor of a hole), cached per camera."""
    view = window.view3d
    try:
        eye, _r, _u, forward = view._camera()
    except Exception:
        return False
    key = (tuple(round(v, 3) for v in eye), view.projection)
    cache = state.setdefault("hidden", {})
    if cache.get("key") != key:
        cache.clear()
        cache["key"] = key
    if i in cache:
        return cache[i]
    from . import analysis
    face = state["faces"][i]
    n = face["dir"]
    p = tuple(face["pos"][k] + n[k] * 0.01 for k in range(3))
    if view.projection == "Orthographic":
        d = tuple(-forward[k] for k in range(3))
        far = float("inf")
    else:
        d = tuple(eye[k] - p[k] for k in range(3))
        far = sum(c * c for c in d) ** 0.5
        d = tuple(c / max(far, 1e-9) for c in d)
    try:
        hits = analysis.surface_hits(p, d, state.get("solid") or [],
                                     limit=1)
        hit = bool(hits) and hits[0]["distance"] < far
    except Exception:
        hit = False
    cache[i] = hit
    return hit


def paint(window, painter, project):
    state = getattr(window, "_choice_preview", None)
    if not state:
        return
    from . import region_show
    if state["show_regions"] and state["regions"]:
        saved = getattr(window, "_region_show", None)
        window._region_show = dict(regions=state["regions"], picked=set())
        try:
            region_show.paint(window, painter, project)
        finally:
            window._region_show = saved
    if not (state["show_faces"] and state["faces"]):
        return
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPainterPath, QPen
    r, g, b = FACE_COLOUR
    painter.save()
    try:
        font = QFont()
        font.setBold(True)
        font.setPointSizeF(9)
        painter.setFont(font)
        for i, face in enumerate(state["faces"]):
            # a faint outline of the face, then its number — only faces
            # turned towards the eye (a back face's number read through
            # the part)
            path = QPainterPath()
            facing = 0.0
            for t in face["tris"]:
                pts = [project(p) for p in t]
                if any(p is None for p in pts):
                    continue
                facing += (pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) \
                    - (pts[1][1] - pts[0][1]) * (pts[2][0] - pts[0][0])
                path.moveTo(QPointF(*pts[0][:2]))
                path.lineTo(QPointF(*pts[1][:2]))
                path.lineTo(QPointF(*pts[2][:2]))
                path.closeSubpath()
            if facing * FACING_SIGN <= 0 or _hidden(window, state, i):
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(r, g, b, 22)))
            painter.drawPath(path)
            q = project(face["pos"])
            if q is None:
                continue
            text = "F%d" % (i + 1)
            w = 12 + 7 * len(text)
            x, y = q[0] - w / 2, q[1] - 9
            painter.setPen(QPen(QColor(r, g, b), 1.5))
            painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
            painter.drawRoundedRect(int(x), int(y), int(w), 18, 4, 4)
            painter.setPen(QColor(r, g, b))
            painter.drawText(int(x), int(y), int(w), 18, Qt.AlignCenter,
                             text)
    finally:
        painter.restore()

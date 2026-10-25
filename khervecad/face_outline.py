"""The face you sketch on, shown in the sketch (2026-10-25, the user: "when
we select the face we should see that face in the 2D view … the centre
of the circle, this is where we would like the cut to start").

`outline(tris, point, normal)` (Qt-free): the triangles lying in the
clicked face's plane and facing its way, their boundary edges (an edge
used by one of them only) — the face's outline, holes included.
`for_group(group, tris)` maps it into the face sketch's own frame
(`face_sketch.to_local`), which is the 2D view's frame while that
sketch is open; `snap_points` gives its corners, the middle of each
straight side and the centre of each round run (`drawing.find_circles`)
— SolidWorks' snaps on the face's edges.

The 2D view draws the outline grey under the sketch and snaps to those
points (`SketchScene.face_outline`); nothing is stored in the document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

PLANE_TOL = 1e-3          # mm off the plane still on it
FACING = 0.999            # cos of the angle a triangle may tilt
SNAP_PX = 10


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def outline(tris, point, normal):
    """[((x, y, z), (x, y, z))] boundary edges of the face of *tris* in
    the plane through *point* square to *normal*."""
    n = _unit(normal)
    d0 = n[0] * point[0] + n[1] * point[1] + n[2] * point[2]
    size = 1.0
    for t in tris[:2000]:
        for v in t:
            size = max(size, abs(v[0]), abs(v[1]), abs(v[2]))
    tol = PLANE_TOL * size
    count = {}
    for t in tris:
        tn = _unit(_cross(_sub(t[1], t[0]), _sub(t[2], t[0])))
        if tn[0] * n[0] + tn[1] * n[1] + tn[2] * n[2] < FACING:
            continue
        if any(abs(v[0] * n[0] + v[1] * n[1] + v[2] * n[2] - d0) > tol
               for v in t):
            continue
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            ka = tuple(round(c, 4) for c in a)
            kb = tuple(round(c, 4) for c in b)
            key = (ka, kb) if ka <= kb else (kb, ka)
            count[key] = count.get(key, 0) + 1
    return [k for k, c in count.items() if c == 1]


def for_group(group, tris):
    """The clicked face's outline in *group*'s own 2D frame."""
    from . import face_sketch
    point = face_sketch.to_world(group, 0.0, 0.0)
    normal = face_sketch._normal_of(group)
    segs = []
    for a, b in outline(tris, point, normal):
        segs.append((face_sketch.to_local(group, a),
                     face_sketch.to_local(group, b)))
    return segs


def arcs(segs):
    """[((cx, cy), r)] of the round runs in the outline: along each loop,
    vertices that turn a little (a tessellated arc, between 0.3 and 40
    degrees) in a row; sharp corners and straight sides end a run."""
    from . import drawing
    out = []
    for points, _s, closed in drawing._chains(list(segs)):
        n = len(points)
        if n < 3:
            continue

        def turn(i):
            a, b, c = points[i - 1], points[i], points[(i + 1) % n]
            u = (b[0] - a[0], b[1] - a[1])
            v = (c[0] - b[0], c[1] - b[1])
            t = math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0],
                                        u[0] * v[0] + u[1] * v[1]))
            return abs(t)
        rng = range(n) if closed else range(1, n - 1)
        bent = {i: 0.3 < turn(i) < 40.0 for i in rng}
        if closed and all(bent.values()):
            got = drawing.fit_circle(points)
            if got:
                out.append(got)
            continue
        # walk from a vertex that is not bent so runs never wrap halfway
        start = next((i for i in rng if not bent[i]), None)
        if start is None:
            continue
        order = [(start + k) % n for k in range(n)] if closed else list(rng)
        run = []
        for i in order + [start]:
            if bent.get(i):
                run.append(i)
                continue
            if len(run) >= 2:
                pts = [points[(run[0] - 1) % n]] + [points[j] for j in run] \
                    + [points[(run[-1] + 1) % n]]
                got = drawing.fit_circle(pts)
                if got and got[1] > 1e-6:
                    out.append(got)
            run = []
    return out


def snap_points(segs):
    """[(x, y, label)]: corners, side middles, arc centres."""
    pts = {}
    for a, b in segs:
        for p in (a, b):
            pts[(round(p[0], 3), round(p[1], 3))] = "corner"
    out = [(x, y, k) for (x, y), k in pts.items()]
    for (cx, cy), _r in arcs(segs):
        out.append((cx, cy, "centre"))
    for a, b in segs:
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 5.0:   # a real side
            out.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "middle"))
    return out


# =================================================================== Qt
def show(window, group, part):
    """Hand the face's outline to the 2D view for *group*'s sketch."""
    from . import meshedit_ui
    tris = None
    for node, t in meshedit_ui._parts(window):
        if node is part or _inside(part, node):
            tris = t
            break
    scene = window.view2d.scene()
    if not tris:
        scene.face_outline = None
        return []
    segs = for_group(group, tris)
    points = snap_points(segs)
    try:
        points += sketch_points(group, part)
    except Exception:                        # never stop the sketch
        import traceback
        traceback.print_exc()
    scene.face_outline = {"segments": segs, "points": points}
    return segs


def _shape_local_points(node):
    """(x, y, kind) of a 2D shape in its own frame, or []."""
    p = node.params
    try:
        if node.type == "rect":
            x, y = float(p.get("x", 0)), float(p.get("y", 0))
            w, h = float(p.get("width", 0)), float(p.get("height", 0))
            return [(x + w / 2, y + h / 2, "centre"), (x, y, "corner"),
                    (x + w, y, "corner"), (x + w, y + h, "corner"),
                    (x, y + h, "corner")]
        if node.type == "circle":
            return [(float(p.get("x", 0)), float(p.get("y", 0)), "centre")]
        if node.type == "line":
            a = (float(p["x1"]), float(p["y1"]))
            b = (float(p["x2"]), float(p["y2"]))
            return [(a[0], a[1], "corner"), (b[0], b[1], "corner"),
                    ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "middle")]
        if node.type == "polygon":
            ox, oy = float(p.get("x", 0)), float(p.get("y", 0))
            pts = [(ox + float(q[0]), oy + float(q[1]))
                   for q in p.get("points") or []]
            out = [(x, y, "corner") for x, y in pts]
            if pts:
                out.append((sum(q[0] for q in pts) / len(pts),
                            sum(q[1] for q in pts) / len(pts), "centre"))
            return out
    except (TypeError, ValueError, KeyError):
        pass
    return []


def scope_points(scene):
    """Every sketch shape's centre / corners / ends in the scope the 2D
    view shows — HIDDEN ones too (a Regions' rectangle and circle), in
    the view's frame: what a new shape snaps and is pinned to."""
    from . import mesh
    from .model import SHAPE_2D
    if getattr(scene, "plane", "Top (XY)") not in ("Top (XY)", None):
        return []
    resolver = getattr(scene, "isolation_resolver", None)
    scope = (resolver() if resolver else None) or scene.model.root
    out = []
    for node in scope.walk():
        if node.category != SHAPE_2D:
            continue
        local = _shape_local_points(node)
        if not local:
            continue
        stop = None if scope is scene.model.root else scope
        try:
            m = mesh.mat_mul(mesh.ancestor_matrix(node, {}, stop=stop),
                             mesh.node_matrix(node, {}))
        except Exception:
            continue
        for x, y, kind in local:
            out.append((m[0][0] * x + m[0][1] * y + m[0][3],
                        m[1][0] * x + m[1][1] * y + m[1][3], kind, node))
    return out


def sketch_points(group, part):
    """The part's own sketch, seen on the face: the centres, corners
    and ends of the 2D shapes it was made from (a Regions' rectangle and
    circle, hidden or not) — "the centre of that rectangle"."""
    from . import face_sketch, mesh
    from .model import SHAPE_2D
    out = []
    for node in part.walk() if part is not None else ():
        if node.category != SHAPE_2D:
            continue
        p = node.params
        try:
            if node.type == "rect":
                x, y = float(p.get("x", 0)), float(p.get("y", 0))
                w, h = float(p.get("width", 0)), float(p.get("height", 0))
                local = [(x + w / 2, y + h / 2, "centre"),
                         (x, y, "corner"), (x + w, y, "corner"),
                         (x + w, y + h, "corner"), (x, y + h, "corner")]
            elif node.type == "circle":
                local = [(float(p.get("x", 0)), float(p.get("y", 0)),
                          "centre")]
            elif node.type == "line":
                a = (float(p["x1"]), float(p["y1"]))
                b = (float(p["x2"]), float(p["y2"]))
                local = [(a[0], a[1], "corner"), (b[0], b[1], "corner"),
                         ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, "middle")]
            else:
                continue
        except (TypeError, ValueError, KeyError):
            continue                          # expressions: skip
        m = mesh.mat_mul(mesh.ancestor_matrix(node, {}, stop=group.parent),
                         mesh.node_matrix(node, {}))
        for x, y, kind in local:
            w = [m[r][0] * x + m[r][1] * y + m[r][3] for r in range(3)]
            lx, ly = face_sketch.to_local(group, w)
            out.append((lx, ly, kind))
    return out


def pin(scene, model, node):
    """A shape just drawn on the face: each of its points sitting on a
    snap point of the face is fixed there (SolidWorks makes it
    coincident: the slot stays on the arc's centre)."""
    info = getattr(scene, "face_outline", None)
    if node is None or node.parent is None:
        return 0
    from . import sketch_constraints as sc
    from .sketch_constrain_ui import _entities
    targets = [(x, y) for x, y, _k in info["points"]] if info else []
    mine = set(id(n) for n in node.walk())
    try:
        # the sketch's own centres and corners too, hidden or not (not
        # the shape just drawn: it would pin to itself)
        targets += [(x, y) for x, y, kind, owner in scope_points(scene)
                    if id(owner) not in mine and kind == "centre"]
    except Exception:
        pass
    if not targets:
        return 0
    n = 0
    for shape in [node] + list(node.children):
        if shape.parent is None:
            continue
        try:
            ents = _entities(shape)
        except Exception:
            continue
        for name, kind in ents:
            if kind != "point":
                continue
            try:
                pt = sc._point(shape, name, {})
            except (KeyError, ValueError, IndexError):
                continue
            if any(abs(pt[0] - x) < 1e-6 and abs(pt[1] - y) < 1e-6
                   for x, y in targets):
                try:
                    sc.add(model, shape.parent, "fix",
                           [sc.ref_of(shape.parent, shape, name)])
                    n += 1
                except (ValueError, KeyError):
                    pass
    return n


def _inside(node, outer):
    while node is not None:
        if node is outer:
            return True
        node = node.parent
    return False


def clear(window):
    scene = window.view2d.scene()
    scene.face_outline = None


def paint(scene, painter):
    """Grey outline + small marks on the centres (scene coordinates)."""
    from PyQt5.QtCore import QLineF, QPointF
    from PyQt5.QtGui import QColor, QPen
    info = getattr(scene, "face_outline", None)
    if not info:
        return
    pen = QPen(QColor(110, 120, 135), 0)
    pen.setCosmetic(True)
    pen.setWidthF(1.6)
    painter.save()
    painter.setPen(pen)
    for a, b in info["segments"]:
        painter.drawLine(QLineF(QPointF(*a), QPointF(*b)))
    mark = QPen(QColor(200, 60, 40), 0)
    mark.setCosmetic(True)
    mark.setWidthF(1.4)
    painter.setPen(mark)
    views = scene.views()
    k = 1.0 / (abs(views[0].transform().m11()) or 1.0) if views else 1.0
    for x, y, kind in info["points"]:
        if kind == "centre":
            s = 5 * k
            painter.drawLine(QLineF(x - s, y, x + s, y))
            painter.drawLine(QLineF(x, y - s, x, y + s))
    painter.restore()


def _on_segment(px, py, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx +
                                                  (py - ay) * dy) / L2))
    return ax + dx * t, ay + dy * t


def snap(scene, pos):
    """(point, kind) of the face's snap point nearest *pos* within
    SNAP_PX — a centre, corner, middle or the sketch's origin — else the
    nearest point ON one of its edges; or None."""
    info = getattr(scene, "face_outline", None)
    if not info:
        return None
    views = scene.views()
    k = abs(views[0].transform().m11()) if views else 1.0
    best = None
    for x, y, kind in info["points"] + [(0.0, 0.0, "origin")]:
        d = math.hypot(pos.x() - x, pos.y() - y) * k
        if d <= SNAP_PX and (best is None or d < best[0]):
            best = (d, x, y, kind)
    from PyQt5.QtCore import QPointF
    if best is not None:
        return QPointF(best[1], best[2]), best[3]
    for a, b in info["segments"]:
        x, y = _on_segment(pos.x(), pos.y(), a, b)
        d = math.hypot(pos.x() - x, pos.y() - y) * k
        if d <= SNAP_PX / 2 and (best is None or d < best[0]):
            best = (d, x, y, "edge")
    if best is not None:
        return QPointF(best[1], best[2]), best[3]
    return None


#: what a snap marker says
LABELS = {"centre": "Centre", "corner": "Corner", "middle": "Midpoint",
          "origin": "Origin", "edge": "On edge", "point": "Point"}


def paint_hint(view, painter):
    """The point the cursor snaps to: an orange ring with its name, as
    SolidWorks shows it (the user did not see the snapping)."""
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QColor, QPen
    scene = view.scene()
    hint = getattr(scene, "_snap_hint", None)
    if not hint or getattr(scene, "tool", "select") == "select":
        return
    p, kind = hint
    k = abs(view.transform().m11()) or 1.0
    r = 6.0 / k
    painter.save()
    pen = QPen(QColor("#ff8c00"), 2.0)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QPointF(p), r, r)
    if kind == "centre":
        painter.drawLine(QPointF(p.x() - r, p.y()), QPointF(p.x() + r, p.y()))
        painter.drawLine(QPointF(p.x(), p.y() - r), QPointF(p.x(), p.y() + r))
    # the name, upright on screen
    painter.resetTransform()
    sp = view.mapFromScene(p)
    painter.setPen(QColor("#c26a00"))
    font = painter.font()
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(sp.x() + 9, sp.y() - 22, 120, 16),
                     int(Qt.AlignLeft | Qt.AlignVCenter),
                     LABELS.get(kind, "Point"))
    painter.restore()


def reference(scene, pos, want=None):
    """The face under a constraint / dimension click when no sketch shape
    is: SolidWorks lets you dimension to the model's edges. A fixed
    CONSTRUCTION copy is added to the sketch — a line along the edge, or
    a point on a corner / centre — and returned as a pick
    (node, entity, kind). None when the click is on nothing."""
    from . import sketch_constraints as sc
    info = getattr(scene, "face_outline", None)
    resolver = getattr(scene, "isolation_resolver", None)
    group = resolver() if resolver else None
    if not info or group is None:
        return None
    views = scene.views()
    k = abs(views[0].transform().m11()) if views else 1.0
    model = scene.model
    best = None
    if want in (None, "point"):
        for x, y, kind in info["points"] + [(0.0, 0.0, "origin")]:
            if kind == "middle":
                continue               # mid-edge: the EDGE is meant
            d = math.hypot(pos.x() - x, pos.y() - y) * k
            if d <= SNAP_PX and (best is None or d < best[0]):
                best = (d, "point", (x, y))
    if best is None and want in (None, "line", "curve"):
        for a, b in info["segments"]:
            x, y = _on_segment(pos.x(), pos.y(), a, b)
            d = math.hypot(pos.x() - x, pos.y() - y) * k
            if d <= SNAP_PX and math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6 \
                    and (best is None or d < best[0]):
                best = (d, "line", (a, b))
    if best is None:
        return None
    if best[1] == "point":
        x, y = best[2]
        node = model.add_node("circle", dict(x=round(x, 6), y=round(y, 6),
                                             radius=0.25), parent=group,
                              name="Reference point")
        model.set_modifier(node, "%")
        sc.add(model, group, "fix", [sc.ref_of(group, node, "c")])
        return node, "c", "point"
    (a, b) = best[2]
    # the whole straight edge: join collinear outline pieces into one
    a, b = _whole_edge(info["segments"], a, b)
    node = model.add_node("line", dict(x1=round(a[0], 6), y1=round(a[1], 6),
                                       x2=round(b[0], 6), y2=round(b[1], 6),
                                       width=0.2), parent=group,
                          name="Reference edge")
    model.set_modifier(node, "%")
    for end in ("p1", "p2"):
        sc.add(model, group, "fix", [sc.ref_of(group, node, end)])
    return node, "l", "line"


def _whole_edge(segs, a, b):
    """*a*-*b* grown along every outline piece lying on the same line."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    lo, hi = 0.0, L
    for p, q in segs:
        ok = True
        for r in (p, q):
            # on the line through a along u?
            if abs((r[0] - a[0]) * uy - (r[1] - a[1]) * ux) > 1e-4:
                ok = False
        if not ok:
            continue
        for r in (p, q):
            t = (r[0] - a[0]) * ux + (r[1] - a[1]) * uy
            lo, hi = min(lo, t), max(hi, t)
    return ((a[0] + ux * lo, a[1] + uy * lo),
            (a[0] + ux * hi, a[1] + uy * hi))

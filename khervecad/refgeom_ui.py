"""Reference geometry in the window (2026-10-27): the planes, axes and
points of `refgeom` drawn in the 3D view, made by clicking, and sketched
on — SolidWorks' Insert ▸ Reference Geometry.

- The three main planes (Front / Top / Right) are drawn see-through in
  the 3D view while View ▸ Show Planes is on (QSettings
  ``render_planes``, on by default), every ref_plane / ref_axis /
  ref_point of the scope always (blue, orange when selected).
- Plane: Offset from a face (click it, give the distance), Through three
  points, At an angle through an edge, Parallel to a main plane.
- Axis: Of a round face or along an edge (one click), Where two planes
  meet (two ref planes selected). Point: one click.
- Sketch on a plane: the tree's right-click on a Plane, a double-click on
  it, or `sketch3d` (Sketch in 3D) which also takes a click on a drawn
  plane.
- Extrude Up To Face: the selected Linear extrude goes up to the face
  clicked (extent.py ``up_to_face``).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language, refgeom

KINDS = ("ref_plane", "ref_axis", "ref_point")
BLUE = (60, 120, 220)
ORANGE = (240, 140, 30)
SMOOTH_TURN = 25.0                 # degrees: a round face's facets


# ------------------------------------------------------------ drawing

def show_planes(window):
    """The main planes are drawn: switched on (View / the 3D bar), or for
    a moment while Sketch in 3D waits for a plane to be picked."""
    return bool(getattr(window.view3d, "show_planes", False)) or \
        bool(getattr(window, "_ref_force_planes", False))


def scope(window):
    return window.builder.isolated_component() or window.model.root


def ref_nodes(window):
    root = scope(window)
    return [n for n in root.walk() if n.type in KINDS and n.visible
            and n is not root]


def _env(window):
    from .anchors import doc_env
    return doc_env(window.model)


def world(node, window, env=None):
    """(kind, origin, direction) of a ref node in the view's frame."""
    from . import mesh
    env = _env(window) if env is None else env
    m = mesh.ancestor_matrix(node, env, stop=scope(window))
    if node.type == "ref_plane":
        o, d = refgeom.plane_of(node, env)
    elif node.type == "ref_axis":
        o, d = refgeom.axis_of(node, env)
    else:
        p = mesh.rp(node, env)
        o, d = [p["x"], p["y"], p["z"]], [0.0, 0.0, 1.0]
    wo = list(mesh.transform_point(m, o))
    wd = [sum(m[i][j] * d[j] for j in range(3)) for i in range(3)]
    try:
        wd = refgeom.unit(wd)
    except ValueError:
        wd = [0.0, 0.0, 1.0]
    return node.type, wo, wd


def _half(window):
    from . import plane_pick
    try:
        return plane_pick._half(window)
    except Exception:                               # pragma: no cover
        return 50.0


def plane_corners(origin, normal, size):
    o, r, u, _n = refgeom.frame(origin, normal)
    h = size / 2.0
    return [[o[i] + r[i] * sr * h + u[i] * su * h for i in range(3)]
            for sr, su in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def planes_in_view(window):
    """[(label, origin, normal, size, node or view2d plane name)] of every
    plane drawn: the main three (when shown) and the ref planes."""
    out = []
    if show_planes(window):
        h = _half(window) * 2
        for name, plane, o, n in refgeom.MAIN_PLANES:
            out.append((name, list(o), list(n), h, plane))
    env = _env(window)
    from . import mesh
    for node in ref_nodes(window):
        if node.type != "ref_plane":
            continue
        _k, o, n = world(node, window, env)
        size = float(mesh.rp(node, env).get("size", 100.0))
        out.append((node.name, o, n, size, node))
    return out


def paint(window, painter, project):
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    try:
        selected = {n.id for n in window.builder.active_tree()
                    .selected_nodes()}
    except Exception:
        selected = set()
    hover = getattr(window, "_ref_hover", None)
    painter.save()
    try:
        painter.setRenderHint(painter.Antialiasing, True)
        for label, o, n, size, what in planes_in_view(window):
            pts = [project(c) for c in plane_corners(o, n, size)]
            if any(p is None or p[2] <= 0 for p in pts):
                continue
            hot = (getattr(what, "id", None) in selected) or \
                (hover is not None and hover[4] is what)
            rgb = ORANGE if hot else BLUE
            poly = QPolygonF([QPointF(p[0], p[1]) for p in pts])
            painter.setPen(QPen(QColor(*rgb, 220), 1.6 if hot else 1.0))
            painter.setBrush(QColor(*rgb, 70 if hot else 28))
            painter.drawPolygon(poly)
            painter.setPen(QColor(*rgb, 255))
            painter.drawText(QPointF(pts[3][0] + 4, pts[3][1] + 14),
                             language.tr(label))
        env = _env(window)
        for node in ref_nodes(window):
            if node.type == "ref_plane":
                continue
            kind, o, d = world(node, window, env)
            rgb = ORANGE if node.id in selected else BLUE
            if kind == "ref_axis":
                from . import mesh
                length = float(mesh.rp(node, env).get("length", 100.0))
                a = project([o[i] - d[i] * length / 2 for i in range(3)])
                b = project([o[i] + d[i] * length / 2 for i in range(3)])
                if a is None or b is None or a[2] <= 0 or b[2] <= 0:
                    continue
                pen = QPen(QColor(*rgb, 230), 1.6)
                pen.setStyle(Qt.DashDotLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
                painter.drawText(QPointF(b[0] + 4, b[1]), node.name)
            else:
                p = project(o)
                if p is None or p[2] <= 0:
                    continue
                painter.setPen(QPen(QColor(*rgb, 255), 1.6))
                painter.setBrush(QColor(255, 255, 255, 230))
                painter.drawEllipse(QPointF(p[0], p[1]), 4.0, 4.0)
                painter.drawLine(QPointF(p[0] - 7, p[1]),
                                 QPointF(p[0] + 7, p[1]))
                painter.drawLine(QPointF(p[0], p[1] - 7),
                                 QPointF(p[0], p[1] + 7))
                painter.drawText(QPointF(p[0] + 7, p[1] - 6), node.name)
    finally:
        painter.restore()


def plane_at(window, x, y):
    """The nearest drawn plane under the screen point, or None:
    (label, origin, normal, size, what, hit point)."""
    from .sculpt_ui import screen_ray
    origin, d = screen_ray(window.view3d, x, y)
    best = None
    for entry in planes_in_view(window):
        label, o, n, size, what = entry
        hit = refgeom.ray_plane(list(origin), list(d), o, n)
        if hit is None:
            continue
        _o, r, u, _n = refgeom.frame(o, n)
        rel = [hit[i] - o[i] for i in range(3)]
        if abs(sum(rel[i] * r[i] for i in range(3))) > size / 2 or \
                abs(sum(rel[i] * u[i] for i in range(3))) > size / 2:
            continue
        dist = math.dist(hit, origin)
        if best is None or dist < best[0]:
            best = (dist, entry + (hit,))
    return None if best is None else best[1]


# ------------------------------------------------------------- making

def _tell(window, text, ms=6000):
    window.statusBar().showMessage(language.tr(text), ms)
    try:
        window.view3d.flash(language.tr(text))
    except Exception:
        pass


def _next_name(window, base):
    names = {n.name for n in window.model.root.walk()}
    i = 1
    while f"{base} {i}" in names:
        i += 1
    return f"{base} {i}"


def add(window, kind, params, base):
    """A reference node at the END of the scope (so it is never a
    boolean's first child), named "<base> n", selected."""
    model = window.model
    parent = scope(window)
    name = _next_name(window, base)
    node = model.add_node(kind, params, parent=parent)
    model.rename(node, name)
    try:
        window.builder.active_tree().select_nodes([node])
    except Exception:
        pass
    _tell(window, f"{node.name} added — it stays in the tree; "
          "right-click it to sketch on it.", 6000)
    window.view3d.update()
    return node


def add_plane(window, origin, normal, size=None):
    size = size or round(_half(window) * 1.2, 1)
    o, n = list(origin), list(normal)
    return add(window, "ref_plane", dict(
        x=o[0], y=o[1], z=o[2], nx=n[0], ny=n[1], nz=n[2], size=size),
        "Plane")


def add_axis(window, point, direction, length=None):
    length = length or round(_half(window) * 1.6, 1)
    return add(window, "ref_axis", dict(
        x=point[0], y=point[1], z=point[2], dx=direction[0],
        dy=direction[1], dz=direction[2], length=length), "Axis")


def add_point(window, p):
    return add(window, "ref_point", dict(x=p[0], y=p[1], z=p[2]),
               "Point")


def _parts(window):
    from . import meshedit_ui
    return meshedit_ui._parts(window)


def _pick(window, banner, callback, kinds=("face", "edge")):
    """One click on a part's face / edge -> callback(desc, node, tris)."""
    parts = _parts(window)
    if not parts:
        _tell(window, "There is no part to click on — use 'Parallel to "
              "a main plane' or add a part first.")
        return False
    by_node = {id(n): t for n, t in parts}

    def picked(desc, node):
        if desc is None or node is None:
            return
        window.view3d.cancel_pick()
        if desc.get("kind") not in kinds:
            _tell(window, "Click a " + " or ".join(kinds) + ".")
            _pick(window, banner, callback, kinds)
            return
        callback(desc, node, by_node.get(id(node), []))
    _tell(window, banner, 10000)
    window.view3d.start_pick(picked, groups=parts,
                             banner=language.tr(banner + " · Esc cancels"))
    return True


def _ask_number(window, title, label, value, lo=-1e6, hi=1e6):
    from PyQt5.QtWidgets import QInputDialog
    v, ok = QInputDialog.getDouble(window, language.tr(title),
                                   language.tr(label), value, lo, hi, 3)
    return float(v) if ok else None


def plane_offset(window):
    def got(desc, node, tris):
        d = _ask_number(window, "Offset plane",
                        "Distance from the face (mm):", 10.0)
        if d is None:
            return
        o, n = refgeom.offset_plane(desc["pos"], desc["dir"], d)
        add_plane(window, o, n)
    return _pick(window, "Plane: click the face to offset from", got,
                 ("face",))


def plane_three_points(window):
    points = []

    def got(desc, node, tris):
        p = desc["pos"]
        seg = desc.get("seg")
        if seg:                        # an edge: its nearer end, a corner
            p = min(seg, key=lambda e: math.dist(e, desc["pos"]))
        points.append(list(p))
        if len(points) < 3:
            _pick(window, f"Plane: point {len(points) + 1} of 3", got)
            return
        try:
            o, n = refgeom.plane_three_points(*points)
        except ValueError as exc:
            _tell(window, str(exc))
            return
        add_plane(window, o, n)
    return _pick(window, "Plane: point 1 of 3 (faces give their middle, "
                 "edges a corner)", got)


def plane_at_angle(window):
    edge = []

    def got_face(desc, node, tris):
        a = _ask_number(window, "Plane at an angle",
                        "Angle from the face (degrees):", 45.0, -360, 360)
        if a is None:
            return
        o, n = refgeom.plane_at_angle(edge[0], edge[1], desc["dir"], a)
        add_plane(window, o, n)

    def got_edge(desc, node, tris):
        seg = desc.get("seg") or [desc["pos"], desc["pos"]]
        if math.dist(seg[0], seg[1]) < 1e-6:
            _tell(window, "That edge has no length.")
            return
        edge[:] = [list(seg[0]), list(seg[1])]
        _pick(window, "Plane: now click the face it turns from", got_face,
              ("face",))
    return _pick(window, "Plane: click the edge it turns about",
                 got_edge, ("edge",))


def plane_parallel(window):
    from PyQt5.QtWidgets import QInputDialog
    names = [language.tr(n + " Plane") for n, *_r in refgeom.MAIN_PLANES]
    item, ok = QInputDialog.getItem(window, language.tr("Plane"),
                                    language.tr("Parallel to:"), names, 1,
                                    False)
    if not ok or item not in names:
        return None
    _n, _p, o, n = refgeom.MAIN_PLANES[names.index(item)]
    d = _ask_number(window, "Plane", "Distance (mm):", 20.0)
    if d is None:
        return None
    o, n = refgeom.offset_plane(o, n, d)
    return add_plane(window, o, n)


def smooth_region(tris, seed, max_turn=SMOOTH_TURN):
    """The triangles of the smooth patch round *seed* (a round face):
    neighbours across shared edges turning less than *max_turn*."""
    import numpy as np
    t = np.asarray(tris, float).reshape(-1, 3, 3)
    if not len(t):
        return []
    c = t.mean(axis=1)
    start = int(np.argmin(((c - np.asarray(seed)) ** 2).sum(axis=1)))
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    ln[ln == 0] = 1
    nrm /= ln[:, None]
    key = lambda p: tuple(round(v, 4) for v in p)          # noqa: E731
    edges = {}
    for i, tri in enumerate(t):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            k = frozenset((key(tri[a]), key(tri[b])))
            edges.setdefault(k, []).append(i)
    cos = math.cos(math.radians(max_turn))
    seen, todo = {start}, [start]
    while todo:
        i = todo.pop()
        for a, b in ((0, 1), (1, 2), (2, 0)):
            k = frozenset((key(t[i][a]), key(t[i][b])))
            for j in edges.get(k, ()):
                if j not in seen and float(nrm[i] @ nrm[j]) >= cos:
                    seen.add(j)
                    todo.append(j)
    return [t[i].tolist() for i in sorted(seen)]


def axis_pick(window):
    def got(desc, node, tris):
        if desc["kind"] == "edge":
            seg = desc.get("seg")
            if not seg or math.dist(seg[0], seg[1]) < 1e-6:
                _tell(window, "That edge has no length.")
                return
            p, d = refgeom.axis_two_points(seg[0], seg[1])
            add_axis(window, desc["pos"], d)
            return
        try:
            region = smooth_region(tris, desc["pos"])
            p, d = refgeom.axis_of_cylinder(region)
        except ValueError:
            # a flat face: its normal through the clicked middle
            p, d = list(desc["pos"]), refgeom.unit(desc["dir"])
        add_axis(window, p, d)
    return _pick(window, "Axis: click a round face (its axis) or an edge",
                 got)


def axis_of_two_planes(window):
    planes = [n for n in window.builder.active_tree().selected_nodes()
              if n.type == "ref_plane"]
    if len(planes) != 2:
        _tell(window, "Select two Planes in the tree first (Ctrl+click), "
              "then Axis where two planes meet.")
        return None
    env = _env(window)
    _k, o1, n1 = world(planes[0], window, env)
    _k, o2, n2 = world(planes[1], window, env)
    try:
        p, d = refgeom.axis_of_planes(o1, n1, o2, n2)
    except ValueError as exc:
        _tell(window, str(exc))
        return None
    return add_axis(window, p, d)


def point_pick(window):
    def got(desc, node, tris):
        p = desc["pos"]
        seg = desc.get("seg")
        if seg:
            p = min(seg, key=lambda e: math.dist(e, desc["pos"]))
        add_point(window, p)
    return _pick(window, "Point: click a face (its middle) or an edge "
                 "(its nearer end)", got)


def sketch_on(window, node=None, origin=None, normal=None, label=None,
              open_2d=True):
    """A face-sketch Group lying on a plane (a ref_plane node, or an
    origin + normal) — the same Group Sketch on Face makes, so Exit,
    Edit Sketch, extrude and cut all work on it."""
    from . import face_sketch
    if node is not None:
        _k, origin, normal = world(node, window)
        label = node.name
    rx, ry, rz = face_sketch.euler_for(normal)
    model = window.model
    group = model.add_node("union", dict(
        x=round(float(origin[0]), 4), y=round(float(origin[1]), 4),
        z=round(float(origin[2]), 4), rx=rx, ry=ry, rz=rz),
        parent=scope(window))
    group.params[face_sketch.KEY] = True
    model.rename(group, "Sketch on " + (label or "plane"))
    if open_2d:
        face_sketch.open_sketch(window, group)
    return group


def up_to_face(window):
    from . import extent
    sel = [n for n in window.builder.active_tree().selected_nodes()]
    ext = None
    for n in sel:
        probe = n
        while probe is not None and probe.type != "linear_extrude":
            probe = probe.parent
        if probe is None:
            probe = next((c for c in n.walk()
                          if c.type == "linear_extrude"), None)
        if probe is not None:
            ext = probe
            break
    if ext is None:
        _tell(window, "Up To Face: select the Linear extrude (or the "
              "part holding it) first, then click the face.")
        return False

    def got(desc, node, tris):
        try:
            h = extent.set_extent(window.model, ext, "up_to_face",
                                  face=list(desc["pos"]) + list(desc["dir"]))
        except ValueError as exc:
            _tell(window, str(exc))
            return
        _tell(window, f"Extrude now goes up to that face: {h:g} mm. "
              "It follows the face when the part changes.")
    return _pick(window, "Up To Face: click the face the extrude stops at",
                 got, ("face",))


def set_show_planes(window, on):
    from PyQt5.QtCore import QSettings
    window.view3d.show_planes = bool(on)
    QSettings().setValue("render_planes", bool(on))
    window.view3d.update()
    _tell(window, "Main planes shown in 3D" if on else
          "Main planes hidden", 3000)


def tree_entries(window, menu, nodes):
    """The tree's right-click: a Plane sketches, an extrude goes up to a
    face, two Planes make an axis. The entries go FIRST (everyday)."""
    from PyQt5.QtWidgets import QAction
    from . import icons
    first = menu.actions()[0] if menu.actions() else None
    acts = []
    planes = [n for n in nodes if n.type == "ref_plane"]
    if len(planes) == 1:
        acts.append(("Sketch on This Plane in 3D", "mdi.vector-square-plus",
                     lambda: _sketch3d(window)))
        acts.append(("Sketch on This Plane (2D view)", "mdi.vector-square",
                     lambda: sketch_on(window, planes[0])))
    if len(planes) == 2:
        acts.append(("Axis Where These Planes Meet", "mdi.axis-z-arrow",
                     lambda: axis_of_two_planes(window)))
    if any(n.type == "linear_extrude" for n in nodes):
        acts.append(("Extrude Up To a Face…", "mdi.arrow-collapse-up",
                     lambda: up_to_face(window)))
    for text, glyph, slot in acts:
        act = QAction(icons.icon(glyph), language.tr(text), menu)
        act.triggered.connect(lambda _=False, s=slot: s())
        menu.insertAction(first, act)
    if acts and first is not None:
        menu.insertSeparator(first)


# --------------------------------------------------------------- menus

def install(window):
    from PyQt5.QtCore import QSettings
    # hidden by default, as in SolidWorks: shown while picking a plane
    v = QSettings().value("render_planes", False)
    window.view3d.show_planes = v in (True, "true", "1", 1)
    window.view3d.overlay_painters.append(
        lambda painter, project: paint(window, painter, project))


#: menu text -> painted icon key (icons_cad_ref)
KEYS = {'Plane offset from a face': 'ref_plane_offset',
        'Plane through three points': 'ref_plane_3pt',
        'Plane at an angle through an edge': 'ref_plane_angle',
        'Plane parallel to a main plane': 'ref_plane_parallel',
        'Axis of a round face or edge': 'ref_axis',
        'Axis where two planes meet': 'ref_axis_planes',
        'Point': 'ref_point',
        'Sketch in 3D (rectangle, circle, line)': 'ref_sketch3d',
        'Extrude up to a face': 'ref_up_to_face',
        'Measure (click two things)': 'ref_measure'}


#: hover help for each command (tooltips.TIPS shape)
TIPS = {
    "ref_plane_offset": ("Plane offset from a face",
        "A reference plane parallel to a flat face, a distance off it — "
        "to sketch above, inside or beside a part.",
        ["Click this, then a flat face in 3D.", "Type the distance."],
        "Right-click the plane in the tree ▸ Sketch on This Plane."),
    "ref_plane_3pt": ("Plane through three points",
        "A plane through three points of the model.",
        ["Click three faces or edges: an edge gives its nearer corner."],
        "Good for a slanted cut through corners."),
    "ref_plane_angle": ("Plane at an angle",
        "A plane through an edge, turned an angle from a face — a "
        "chamfer's plane, a rib's slope.",
        ["Click the edge, then the face it turns from.", "Type the "
         "angle."], "90° stands it square on the face."),
    "ref_plane_parallel": ("Plane parallel to a main plane",
        "A plane parallel to Front, Top or Right, a distance away — the "
        "middle of a part, or above it, with nothing to click.",
        ["Choose the main plane.", "Type the distance."],
        "A rib in the middle of a part: Front + half its depth."),
    "ref_axis": ("Axis", "An axis along a round face's centre or an "
        "edge.", ["Click a round face (its axis) or an edge."],
        "Use it to revolve or pattern about."),
    "ref_axis_planes": ("Axis where two planes meet",
        "The line where two reference planes cross.",
        ["Select two Planes in the tree (Ctrl+click), then click this."],
        "Parallel planes never meet."),
    "ref_point": ("Point", "A reference point on the model.",
        ["Click a face (its middle) or an edge (its nearer end)."],
        "It stays in the tree and draws nothing."),
    "ref_sketch3d": ("Sketch in 3D",
        "Draw rectangles, circles and lines straight on a plane in the 3D "
        "view, without leaving it.",
        ["Click a plane or a flat face.", "Rectangle: two corners; "
         "Circle: centre then rim; Line: point to point.",
         "Drag a corner to change it; Done or Esc ends."],
        "R / C / L switch tools; Alt draws off the grid."),
    "ref_up_to_face": ("Extrude up to a face",
        "The selected extrude stops exactly at the face you click, and "
        "follows it when the part changes.",
        ["Select the Linear extrude.", "Click this, then the face."],
        "Direction 2 depth (Properties) extrudes the other way too."),
    "ref_measure": ("Measure",
        "Click a face or an edge to read its size; click a second one to "
        "read the distance and angle between them.",
        ["Click a face or edge.", "Click another.", "Esc ends."],
        "Parallel faces also give the face-to-face distance."),
    "ref_show_planes": ("Show main planes",
        "Shows or hides the Front, Top and Right planes in the 3D view.",
        ["Click to switch."], "Also on the 3D view's own bar."),
}


def build_menu(window, menu):
    """Insert ▸ Reference Geometry."""
    from PyQt5.QtWidgets import QAction
    from . import icons
    sub = menu.addMenu(icons.icon("mdi.square-outline"),
                       language.tr("Reference &Geometry"))
    sub.setToolTipsVisible(True)
    entries = [
        ("Plane offset from a face", "mdi.layers-outline",
         plane_offset),
        ("Plane through three points", "mdi.triangle-outline",
         plane_three_points),
        ("Plane at an angle through an edge", "mdi.angle-acute",
         plane_at_angle),
        ("Plane parallel to a main plane", "mdi.layers-triple-outline",
         plane_parallel),
        None,
        ("Axis of a round face or edge", "mdi.axis-arrow", axis_pick),
        ("Axis where two planes meet", "mdi.axis-z-arrow",
         axis_of_two_planes),
        ("Point", "mdi.circle-small", point_pick),
        None,
        ("Sketch in 3D (rectangle, circle, line)",
         "mdi.vector-square-plus", lambda w: _sketch3d(w)),
        ("Extrude up to a face", "mdi.arrow-collapse-up", up_to_face),
        ("Measure (click two things)", "mdi.ruler", lambda w: _measure(w)),
    ]
    for entry in entries:
        if entry is None:
            sub.addSeparator()
            continue
        text, glyph, slot = entry
        act = QAction(icons.icon(glyph), language.tr(text), window)
        act.setData(KEYS[text])
        _tip(act, KEYS[text])
        act.triggered.connect(lambda _=False, s=slot: s(window))
        sub.addAction(act)
    sub.addSeparator()
    toggle = QAction(language.tr("Show main planes in 3D"), window)
    toggle.setData("ref_show_planes")
    _tip(toggle, "ref_show_planes")
    toggle.setCheckable(True)
    from PyQt5.QtCore import QSettings
    toggle.setChecked(QSettings().value("render_planes", False) in
                      (True, "true", "1", 1))
    toggle.toggled.connect(lambda on: set_show_planes(window, on))
    sub.addAction(toggle)
    window._ref_planes_act = toggle
    return sub


def _tip(act, key):
    from . import tooltips
    tooltips.TIPS.setdefault(key, TIPS[key])
    tooltips.apply(act, key)


def _sketch3d(window):
    from . import sketch3d
    return sketch3d.start(window)


def _measure(window):
    from . import measure3d
    return measure3d.start(window)

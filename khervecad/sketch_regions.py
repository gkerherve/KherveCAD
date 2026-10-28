"""Extrude chosen REGIONS of a sketch (2026-10-25, the user, from a
SolidWorks video: a rectangle with a perimeter circle at one end is
three regions — the rectangle's long part, the circle, the rectangle's
corners beyond it — and picking the first two extrudes a slot-ended
plate).

Overlapping 2D shapes in one container split into faces: every
combination of shapes in / out (`faces`), each split again into its
connected pieces (Manifold `CrossSection.decompose`), so the rectangle's
long part and its far corners are separate faces though both are
"rectangle, not circle". The Extrude regions tool (`REGIONS`, a scene
tool) toggles faces by clicking inside them; Enter, right-click or
double-click makes one `polygon` (outlines as `paths`) under a Linear
extrude in the same container, and hides the sketch shapes it used,
as SolidWorks absorbs a sketch into its feature. The polygon is the
regions as drawn: editing the sketch afterwards does not regrow it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

REGIONS = "regions"
MAKE = "make_region"     # Create Region: the Regions node, no extrude
MAX_SHAPES = 10        # 2^n combinations
HEIGHT = 10.0


def _cross_section(outlines):
    import manifold3d as m
    loops = [[(float(x), float(y)) for x, y in o] for o in outlines
             if len(o) >= 3]
    return m.CrossSection(loops, m.FillRule.Positive) if loops else None


def shapes_of(container, construction=False):
    """The sketch shapes of *container*; *construction* also takes the
    ones a regions extrude turned into construction (they keep the
    dimensions that drive it)."""
    from .model import SHAPE_2D
    return [n for n in container.children
            if n.visible and n.category == SHAPE_2D
            and (construction or n.params.get("modifier") != "%")]


def faces(shapes, any_state=False):
    """[(CrossSection, [loops], [shapes it lies in])] — every connected region the shapes'
    outlines cut the plane into."""
    from .mesh import collect_outlines, node_outlines, _oriented
    secs, owners = [], []
    # plain lines are EDGES: where they join end to end into a closed
    # loop, the loop is a shape (the user: lines like a polygon)
    from . import slot2d
    lines = [s for s in shapes if s.type == "line" and not slot2d.is_slot(s)]
    for loop, first in line_loops(lines):
        cs = _cross_section([loop])
        if cs is not None and not cs.is_empty():
            secs.append(cs)
            owners.append(shapes.index(first))
    closed_shapes = len(secs)
    for s in shapes[:MAX_SHAPES]:
        if s in lines:
            continue
        if any_state or s.params.get("modifier") == "%" or not s.visible:
            # construction (a regions extrude's sketch): its own outline,
            # which collect_outlines leaves out like OpenSCAD does
            outlines = _oriented(s, node_outlines(s, {}))
        else:
            outlines = collect_outlines(s)
        cs = _cross_section(outlines)
        if cs is not None and not cs.is_empty():
            secs.append(cs)
            owners.append(shapes.index(s))
    # two open runs of lines whose ends rest on other shapes close a
    # region between them (two circles joined by two lines)
    for loop, first in bridges(lines, secs[closed_shapes:]):
        cs = _cross_section([loop])
        if cs is not None and not cs.is_empty():
            secs.append(cs)
            owners.append(shapes.index(first))
    out = []
    n = len(secs)
    for mask in range(1, 1 << n):
        inside = [secs[i] for i in range(n) if mask >> i & 1]
        outside = [secs[i] for i in range(n) if not mask >> i & 1]
        cs = inside[0]
        for other in inside[1:]:
            cs = cs ^ other
            if cs.is_empty():
                break
        for other in outside:
            if cs.is_empty():
                break
            cs = cs - other
        if cs.is_empty() or cs.area() < 1e-6:
            continue
        for piece in _pieces(cs):
            if piece.area() > 1e-6:
                out.append((piece, [[(float(p[0]), float(p[1]))
                                     for p in loop]
                                    for loop in piece.to_polygons()],
                            [owners[i] for i in range(n) if mask >> i & 1]))
    return out


JOIN = 1e-3            # mm: line ends this close meet


def line_loops(lines):
    """[(points counter-clockwise, the loop's first line)] of the closed
    loops the *lines* make end to end."""
    def key(p):
        return (round(p[0] / JOIN), round(p[1] / JOIN))
    ends = {}
    segs = []
    for ln in lines:
        p = ln.params
        try:
            a = (float(p["x1"]), float(p["y1"]))
            b = (float(p["x2"]), float(p["y2"]))
        except (KeyError, TypeError, ValueError):
            continue
        i = len(segs)
        segs.append((a, b, ln))
        ends.setdefault(key(a), []).append(i)
        ends.setdefault(key(b), []).append(i)
    used = set()
    loops = []
    for start in range(len(segs)):
        if start in used:
            continue
        a, b, ln = segs[start]
        pts, cur, at = [a], start, b
        chain = {start}
        closed = False
        while True:
            pts.append(at)
            if key(at) == key(a) and len(chain) > 1:
                closed = True
                break
            nxt = [j for j in ends.get(key(at), ()) if j not in chain]
            if len(nxt) != 1:
                break
            cur = nxt[0]
            chain.add(cur)
            s0, s1, _l = segs[cur]
            at = s1 if key(s0) == key(at) else s0
        if closed and len(chain) >= 3:
            used |= chain
            pts = pts[:-1]
            area = sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                       for i in range(len(pts)))
            if area > 0:              # clockwise: turn it round
                pts.reverse()
            loops.append((pts, ln))
    return loops


REST = 0.5            # mm: a line end this near a shape rests on it


def _chains(lines):
    """[(points, first line)] of the OPEN runs the *lines* make end to
    end (a fork ends a run)."""
    def key(p):
        return (round(p[0] / JOIN), round(p[1] / JOIN))
    segs, ends = [], {}
    for ln in lines:
        p = ln.params
        try:
            a = (float(p["x1"]), float(p["y1"]))
            b = (float(p["x2"]), float(p["y2"]))
        except (KeyError, TypeError, ValueError):
            continue
        segs.append((a, b, ln))
        ends.setdefault(key(a), []).append(len(segs) - 1)
        ends.setdefault(key(b), []).append(len(segs) - 1)
    seen, out = set(), []
    for i, (a, b, ln) in enumerate(segs):
        if i in seen or len(ends[key(a)]) == 2 and len(ends[key(b)]) == 2:
            continue                  # inside a run, or part of a loop
        start = a if len(ends[key(a)]) != 2 else b
        pts, cur, at = [start], i, None
        seen.add(i)
        while True:
            s0, s1, _l = segs[cur]
            at = s1 if key(s0) == key(pts[-1]) else s0
            pts.append(at)
            nxt = [j for j in ends[key(at)] if j not in seen]
            if len(ends[key(at)]) != 2 or not nxt:
                break
            cur = nxt[0]
            seen.add(cur)
        out.append((pts, ln))
    return out


def _near(pt, cs):
    loops = [[(float(q[0]), float(q[1])) for q in lp]
             for lp in cs.to_polygons()]
    if sum(_inside(pt, lp) for lp in loops) % 2:
        return True
    x, y = pt
    for lp in loops:
        for (x1, y1), (x2, y2) in zip(lp, lp[1:] + lp[:1]):
            dx, dy = x2 - x1, y2 - y1
            t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)
            t = min(1.0, max(0.0, t))
            if math.hypot(x1 + t * dx - x, y1 + t * dy - y) < REST:
                return True
    return False


def bridges(lines, sections):
    """[(points counter-clockwise, first line)]: the region between each
    two open runs of lines whose four ends rest on the *sections* — the
    shapes then cut it back to their own edges."""
    rested = [(pts, ln) for pts, ln in _chains(lines)
              if any(_near(pts[0], cs) for cs in sections)
              and any(_near(pts[-1], cs) for cs in sections)]
    out = []
    for i in range(len(rested)):
        for j in range(i + 1, len(rested)):
            a, b = rested[i][0], rested[j][0]
            # join end to the nearer end, so the closing sides do not cross
            if math.dist(a[-1], b[0]) + math.dist(b[-1], a[0]) > \
                    math.dist(a[-1], b[-1]) + math.dist(b[0], a[0]):
                b = b[::-1]
            pts = a + b
            area = sum(pts[k][0] * pts[k - 1][1] - pts[k - 1][0] * pts[k][1]
                       for k in range(len(pts)))
            if abs(area) < 1e-6:
                continue
            if area > 0:
                pts.reverse()
            out.append((pts, rested[i][1]))
    return out


def _pieces(cs, eps=1e-3):
    """The connected pieces of *cs*, pieces that only TOUCH at a point
    kept apart: where a perimeter circle meets a rectangle's sides the
    long part and the far corners share just the tangent points, and
    `decompose` alone took them for one region."""
    import manifold3d as m
    shrunk = cs.offset(-eps, m.JoinType.Miter)
    parts = shrunk.decompose() if not shrunk.is_empty() else []
    if len(parts) <= 1:
        return cs.decompose()
    return [cs ^ p.offset(2 * eps, m.JoinType.Miter) for p in parts]


def _inside(pt, loop):
    x, y = pt
    hit = False
    for i in range(len(loop)):
        (x1, y1), (x2, y2) = loop[i], loop[i - 1]
        if (y1 > y) != (y2 > y) and \
                x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def face_at(face_list, pt):
    """Index of the face holding *pt* (even-odd over its loops)."""
    for i, (_cs, loops, *_m) in enumerate(face_list):
        if sum(_inside(pt, lp) for lp in loops) % 2:
            return i
    return None


def _outline(cs):
    """polygon params (points, + paths for several loops) of *cs*."""
    loops = [[[round(float(p[0]), 4), round(float(p[1]), 4)]
              for p in loop] for loop in cs.to_polygons() if len(loop) >= 3]
    if not loops:
        return None
    points, paths = [], []
    for loop in loops:
        paths.append(list(range(len(points), len(points) + len(loop))))
        points.extend(loop)
    params = {"points": points}
    if len(loops) > 1:
        params["paths"] = paths
    return params


def seed(cs):
    """A point surely inside *cs*: the centre of one of its triangles."""
    import manifold3d as m
    mesh_ = m.Manifold.extrude(cs, 1.0).to_mesh()
    v = mesh_.vert_properties
    best = None
    for tri in mesh_.tri_verts:
        if all(abs(v[i][2] - 1.0) < 1e-9 for i in tri):
            a, b, c = (v[i] for i in tri)
            area = abs((b[0] - a[0]) * (c[1] - a[1])
                       - (c[0] - a[0]) * (b[1] - a[1]))
            if best is None or area > best[0]:
                best = (area, [round(float(a[0] + b[0] + c[0]) / 3, 4),
                               round(float(a[1] + b[1] + c[1]) / 3, 4)])
    return best[1] if best else None


def union_of(face_list, picked):
    picked = sorted(set(picked))
    if not picked:
        return None
    cs = face_list[picked[0]][0]
    for i in picked[1:]:
        cs = cs + face_list[i][0]
    return cs


def extrude(model, container, face_list, picked, height=HEIGHT,
            hide=None):
    """A Linear extrude in *container* holding a **Regions** node (see
    `make`). The extrude."""
    reg = make(model, container, face_list, picked, hide)
    if reg is None:
        return None
    ext = model.wrap_nodes([reg], "linear_extrude")
    if ext is None:
        return None
    ext.params["height"] = height
    ext.name = "Extrude regions"
    model.node_changed.emit(ext)
    return ext


def make(model, container, face_list, picked, hide=None):
    """A **Regions** node in *container* where the sketch was, holding
    the sketch shapes (*hide*, moved in with their Smart Dimensions) and
    drawing the picked regions' union (regions2d). The Regions node."""
    picked = sorted(set(picked))
    shapes = [s for s in (hide or []) if s.parent is container]
    if not picked or not shapes:
        return None
    from . import sketch_constraints as sc
    at = min(container.children.index(s) for s in shapes)
    reg = model.add_node("regions", {
        "seeds": [seed(face_list[i][0]) for i in picked],
        "inside": [face_list[i][2] for i in picked]},
        parent=container, name="Regions")
    # the dimensions go with the shapes: rows naming only them, re-indexed
    old = [sc.ref_of(container, s, "").rstrip(".") for s in shapes]
    new_index = {o: str(i) for i, o in enumerate(old)}
    moved, kept = [], []
    for row in sc.rows(container):
        idxs = [r.partition(".")[0] for r in row["refs"]]
        if all(i in new_index for i in idxs):
            row = dict(row, refs=["%s.%s" % (new_index[i],
                                             r.partition(".")[2])
                                  for i, r in zip(idxs, row["refs"])])
            moved.append(row)
        elif not any(i in new_index for i in idxs):
            kept.append(row)
    for s in shapes:
        model.move_node(s, reg)
        s.params.pop("modifier", None)
    if moved:
        reg.params[sc.KEY] = moved
    # the container's own rows: re-indexed for the shapes taken out
    container.params[sc.KEY] = kept
    if not kept:
        container.params.pop(sc.KEY, None)
    else:
        _reindex(container, old)
    # Regions goes where the sketch was
    model.move_node(reg, container, at)
    model.node_changed.emit(reg)
    return reg


def _reindex(container, removed):
    """Rows left on *container* after shapes at *removed* (old child
    indices, as text) were taken out: later indices move down."""
    from . import sketch_constraints as sc
    gone = sorted(int(i) for i in removed)

    def fn(ref):
        idx, _, name = ref.partition(".")
        i = int(idx)
        return "%d.%s" % (i - sum(1 for g in gone if g < i), name)
    for row in sc.rows(container):
        row["refs"] = [fn(r) for r in row["refs"]]


_BUSY = False


def _match(face_list, point, inside):
    """The face standing for a remembered region: the one holding its
    seed when that face lies in the same shapes, else the nearest face
    that does, else the one under the seed."""
    under = face_at(face_list, tuple(point))
    if inside is None:
        return under
    if under is not None and face_list[under][2] == inside:
        return under
    same = [i for i, f in enumerate(face_list) if f[2] == inside]
    if not same:
        return under
    import math

    def dist(i):
        p = seed(face_list[i][0]) or point
        return math.hypot(p[0] - point[0], p[1] - point[1])
    return min(same, key=dist)


def refresh(model):
    """Every regions extrude follows its sketch: the faces holding its
    seed points, of the construction shapes beside it, re-unioned."""
    global _BUSY
    if _BUSY:
        return
    _BUSY = True
    try:
        from . import regions2d
        for node in list(model.root.walk()):
            if node.type == "regions":
                regions2d.track(node)        # its picks follow the shapes
        for poly in list(model.root.walk()):
            info = poly.params.get("regions") if poly.type == "polygon" \
                else None
            if not isinstance(info, dict) or poly.parent is None or \
                    poly.parent.parent is None:
                continue
            try:
                faces_ = faces(shapes_of(poly.parent.parent, True))
                picked = set()
                insides = info.get("inside") or []
                for k, p in enumerate(info.get("seeds") or []):
                    want = insides[k] if k < len(insides) else None
                    picked.add(_match(faces_, p, want))
                picked.discard(None)
                cs = union_of(faces_, picked)
                params = _outline(cs) if cs is not None else None
            except Exception:                 # no Manifold, odd shapes
                continue
            if not params:
                continue
            if params["points"] != poly.params.get("points") or \
                    params.get("paths") != poly.params.get("paths"):
                poly.params["points"] = params["points"]
                if "paths" in params:
                    poly.params["paths"] = params["paths"]
                else:
                    poly.params.pop("paths", None)
                # the seeds follow the regions they stand for
                info["seeds"] = [seed(faces_[i][0]) for i in sorted(picked)]
                info["inside"] = [faces_[i][2] for i in sorted(picked)]
                model.node_changed.emit(poly)
    finally:
        _BUSY = False


# ------------------------------------------------------- the scene tool
def _state(scene):
    st = getattr(scene, "_regions", None)
    if st is None:
        st = scene._regions = {"container": None, "faces": [],
                               "picked": set(), "items": [], "frame": None}
    return st


def drop(scene):
    st = _state(scene)
    for it in st["items"]:
        if it.scene() is not None:
            it.scene().removeItem(it)
    scene._regions = None


def _redraw(scene):
    from PyQt5.QtGui import QBrush, QColor, QPainterPath, QPen
    from PyQt5.QtWidgets import QGraphicsPathItem
    st = _state(scene)
    for it in st["items"]:
        if it.scene() is not None:
            it.scene().removeItem(it)
    st["items"] = []
    for i in st["picked"]:
        path = QPainterPath()
        path.setFillRule(0)                       # odd-even
        for loop in st["faces"][i][1]:
            path.moveTo(*loop[0])
            for p in loop[1:]:
                path.lineTo(*p)
            path.closeSubpath()
        item = QGraphicsPathItem(path, st["frame"])
        if st["frame"] is None:
            scene.addItem(item)
        item.setBrush(QBrush(QColor(60, 140, 255, 110)))
        item.setPen(QPen(QColor(30, 100, 230), 0))
        item.setZValue(50)
        st["items"].append(item)


def press(scene, event):
    from PyQt5.QtCore import Qt
    if event.button() == Qt.RightButton:
        finish(scene)
        event.accept()
        return
    if event.button() != Qt.LeftButton:
        return
    from .sketch_constrain_ui import _shape_items
    from .view2d_edit import in_frame_coords
    st = _state(scene)
    pos = event.scenePos()
    if st["container"] is None:
        for item in _shape_items(scene):
            q = in_frame_coords(item, pos)
            shapes = shapes_of(item.node.parent)
            got = faces(shapes)
            if face_at(got, (q.x(), q.y())) is not None:
                st.update(container=item.node.parent, faces=got,
                          shapes=shapes, frame=item.parentItem(),
                          probe=item)
                break
        else:
            scene.status.emit("Extrude regions: click inside a region "
                              "of the sketch.")
            event.accept()
            return
    q = in_frame_coords(st["probe"], pos)
    i = face_at(st["faces"], (q.x(), q.y()))
    if i is not None:
        st["picked"] ^= {i}
        _redraw(scene)
        scene.status.emit("Extrude regions: %d chosen — Enter or "
                          "right-click extrudes them." % len(st["picked"]))
    event.accept()


def finish(scene):
    st = _state(scene)
    ext = None
    if st["container"] is not None and st["picked"]:
        build = make if scene.tool == MAKE else extrude
        ext = build(scene.model, st["container"], st["faces"],
                    st["picked"], hide=st.get("shapes"))
    drop(scene)
    if ext is not None:
        scene.node_created.emit(ext)
    return ext


def key(scene, event):
    from PyQt5.QtCore import Qt
    if event.key() in (Qt.Key_Return, Qt.Key_Enter):
        finish(scene)
        return True
    if event.key() == Qt.Key_Escape:
        drop(scene)
        return True
    return False


# ------------------------------------------------------- in the 3D view
def _slab_tris(cs, matrix, height=0.02):
    """A face as a slab placed in the world: thin for picking, the
    extrude's height for the preview."""
    import manifold3d as m
    from .fillet_pick import _apply
    mesh_ = m.Manifold.extrude(cs, height).to_mesh()
    verts = [tuple(float(c) for c in v[:3]) for v in mesh_.vert_properties]
    return [tuple(_apply(matrix, verts[i]) for i in tri)
            for tri in mesh_.tri_verts]


#: what a sketch already made something of sits under
USED_BY = ("linear_extrude", "rotate_extrude", "regions", "sweep",
           "section_loft", "loft", "difference", "intersection")


def used(node):
    """True when *node* (a sketch or its container) is already part of
    a feature — an extruded Regions' rectangle is not a free sketch to
    pick regions of again (the user's side-face boss picked it)."""
    probe = node
    while probe is not None:
        if probe.type in USED_BY:
            return True
        probe = probe.parent
    return False


def free_shapes(window):
    """2D shapes in the scope that no feature uses yet."""
    from .model import SHAPE_2D
    scope = window._render_scope()[0]
    return [n for n in scope.walk() if n.category == SHAPE_2D
            and n.visible and not used(n)]


def sketch_container(window):
    """The group whose sketch shapes overlap into regions: the selected
    shape's, else the first in the scope with two or more."""
    from .model import SHAPE_2D
    scope = window._render_scope()[0]
    sel = [n for n in window.builder.active_tree().selected_nodes()] \
        if hasattr(window.builder.active_tree(), "selected_nodes") else []
    for n in sel:
        if n.category == SHAPE_2D and n.parent is not None:
            return n.parent
        if len(shapes_of(n)) >= 2:
            return n
    for n in scope.walk():
        if len(shapes_of(n)) >= 2 and not used(n):
            return n
    return None


def overlapping(container):
    """True when the container's shapes cut each other into more
    regions than there are shapes (a circle ON a rectangle)."""
    shapes = shapes_of(container)
    return len(shapes) >= 2 and len(faces(shapes)) > len(shapes)


def overlap_container(window, nodes):
    """The sketch an Extruded Boss on *nodes* (or nothing selected)
    should split into regions, or None."""
    from .model import SHAPE_2D
    if nodes:
        seen = []
        for n in nodes:
            c = n.parent if n.category == SHAPE_2D else n
            if c is not None and c not in seen:
                seen.append(c)
        cands = seen
    else:
        c = sketch_container(window)
        cands = [c] if c is not None else []
    for c in cands:
        if used(c):
            continue
        try:
            if overlapping(c):
                return c
        except Exception:                     # no Manifold, odd shapes
            return None
    return None


def start_3d(window, container=None, make_only=False):
    """Pick regions on the 3D view: the region under the mouse lights
    up, a click keeps it (again drops it), Esc or right-click extrudes
    what was picked. False when no sketch has regions."""
    from . import mesh
    container = container or sketch_container(window)
    if container is None:
        window.statusBar().showMessage(
            "Extrude regions: draw overlapping 2D shapes first (a "
            "rectangle and a circle on it).", 6000)
        return False
    shapes = shapes_of(container)
    face_list = faces(shapes)
    if not face_list:
        return False
    scope = window._render_scope()[0]
    iso = scope if scope is not window.model.root else None
    with window._isolated_frame(iso):
        mat = mesh.ancestor_matrix(container, {}, stop=iso)
        mat = mesh.mat_mul(mat, mesh.node_matrix(container, {}))
    groups = [(i, _slab_tris(cs, mat)) for i, (cs, *_l) in
              enumerate(face_list)]
    # what is picked shows as the solid it will make (SolidWorks' yellow
    # preview), the default height
    tris = {i: _slab_tris(cs, mat, HEIGHT) for i, (cs, *_l) in
            enumerate(face_list)}
    picked = set()
    view = window.view3d
    from .fillet_pick import _apply
    lift = 0.05                    # just above the sketch, never inside it
    lines = []
    for _cs, loops, *_m in face_list:
        for loop in loops:
            pts = [_apply(mat, (x, y, lift)) for x, y in loop]
            lines.append(pts + pts[:1])

    def banner():
        if make_only:
            return ("Create Region: click the regions to keep (%d picked) "
                    "· Esc or right-click makes it" % len(picked))
        return ("Extruded Boss/Base — Selected Contours: click the "
                "regions to extrude (%d picked) · Esc or right-click "
                "makes it" % len(picked))

    def on_pick(desc, key):
        if desc is None:                       # done
            view.set_highlight_mesh([])
            if make_only:
                reg = make(window.model, container, face_list, picked,
                           hide=shapes) if picked else None
                if reg is not None:
                    window.statusBar().showMessage(
                        "Regions made from %d region(s) — extrude or "
                        "revolve it when you like." % len(picked), 6000)
                return
            ext = extrude(window.model, container, face_list, picked,
                          hide=shapes) if picked else None
            if ext is not None:
                window.statusBar().showMessage(
                    "Extruded %d region(s) — drag the arrow or set the "
                    "height in Properties." % len(picked), 6000)
                try:
                    from . import drag_feature
                    drag_feature.start(window, ext, quiet=True,
                                       created=True)
                except Exception:              # pragma: no cover
                    pass
            return
        picked.symmetric_difference_update({key})
        view.set_highlight_mesh([t for i in sorted(picked)
                                 for t in tris[i]])
        arm()

    def arm():
        view.pick_lines = lines        # every region's edges, seen
        view.start_pick(on_pick, groups=groups, banner=banner(),
                        labeler=lambda _d, k: "Region — click to %s" % (
                            "drop" if k in picked else "keep"))
    arm()
    return True


def from_selection(window):
    """Create Region on the shapes selected (in the sketch or the tree):
    the area they enclose — closed lines, a polygon, shapes on shapes —
    becomes one Regions node holding them. False when nothing usable is
    selected (the tool then asks for clicks on the regions)."""
    from .model import SHAPE_2D
    nodes = window.builder.active_tree().selected_nodes()
    shapes = [n for n in nodes if n.category == SHAPE_2D
              and n.parent is not None]
    if not shapes:
        return False
    container = shapes[0].parent
    shapes = [s for s in shapes if s.parent is container]
    face_list = faces(shapes)
    if not face_list:
        window.statusBar().showMessage(
            "Create Region: the selected shapes enclose nothing — join "
            "the lines end to end into a closed shape.", 7000)
        return True
    reg = make(window.model, container, face_list,
               range(len(face_list)), hide=shapes)
    if reg is not None:
        window.builder.active_tree().select_nodes([reg])
        window.statusBar().showMessage(
            "Region made from %d shape(s)." % len(shapes), 6000)
    return True

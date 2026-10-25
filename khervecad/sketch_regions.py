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

REGIONS = "regions"
MAX_SHAPES = 10        # 2^n combinations
HEIGHT = 10.0


def _cross_section(outlines):
    import manifold3d as m
    loops = [[(float(x), float(y)) for x, y in o] for o in outlines
             if len(o) >= 3]
    return m.CrossSection(loops, m.FillRule.Positive) if loops else None


def shapes_of(container):
    from .model import SHAPE_2D
    return [n for n in container.children
            if n.visible and n.category == SHAPE_2D
            and n.params.get("modifier") != "%"]


def faces(shapes):
    """[(CrossSection, [loops])] — every connected region the shapes'
    outlines cut the plane into."""
    from .mesh import collect_outlines
    secs = []
    for s in shapes[:MAX_SHAPES]:
        cs = _cross_section(collect_outlines(s))
        if cs is not None and not cs.is_empty():
            secs.append(cs)
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
                                    for loop in piece.to_polygons()]))
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
    for i, (_cs, loops) in enumerate(face_list):
        if sum(_inside(pt, lp) for lp in loops) % 2:
            return i
    return None


def extrude(model, container, face_list, picked, height=HEIGHT,
            hide=None):
    """One polygon of the picked faces under a Linear extrude in
    *container*; *hide* (the sketch shapes) are hidden. The extrude."""
    picked = sorted(set(picked))
    if not picked:
        return None
    cs = face_list[picked[0]][0]
    for i in picked[1:]:
        cs = cs + face_list[i][0]
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
    ext = model.add_node("linear_extrude", {"height": height},
                         parent=container, name="Extrude regions")
    model.add_node("polygon", params, parent=ext, name="Regions")
    for s in hide or []:
        model.set_visible(s, False)
    return ext


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
        ext = extrude(scene.model, st["container"], st["faces"],
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
        if len(shapes_of(n)) >= 2:
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
        try:
            if overlapping(c):
                return c
        except Exception:                     # no Manifold, odd shapes
            return None
    return None


def start_3d(window, container=None):
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
    groups = [(i, _slab_tris(cs, mat)) for i, (cs, _l) in
              enumerate(face_list)]
    # what is picked shows as the solid it will make (SolidWorks' yellow
    # preview), the default height
    tris = {i: _slab_tris(cs, mat, HEIGHT) for i, (cs, _l) in
            enumerate(face_list)}
    picked = set()
    view = window.view3d

    def banner():
        return ("Extruded Boss/Base — Selected Contours: click the "
                "regions to extrude (%d picked) · Esc or right-click "
                "makes it" % len(picked))

    def on_pick(desc, key):
        if desc is None:                       # done
            view.set_highlight_mesh([])
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
        view.start_pick(on_pick, groups=groups, banner=banner(),
                        labeler=lambda _d, k: "Region — click to %s" % (
                            "drop" if k in picked else "keep"))
    arm()
    return True

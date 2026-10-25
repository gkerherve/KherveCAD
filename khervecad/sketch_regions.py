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

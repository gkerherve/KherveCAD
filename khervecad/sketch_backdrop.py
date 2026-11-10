"""The MODEL behind a 2D sketch on a face (2026-11-10, the user: "when
we go from 3D to 2D ... whatever we select is what should be sketched in
the 2D. Take great effort in making sure that the 2D just look exactly
what it should be ... just like SolidWorks").

The 2D sketch on a face showed the face as a hatched outline and nothing
else of the part: a boss standing on the face, the hole through it, what
lies beside it were not there, so one could not tell where on the part
one was drawing. SolidWorks turns the view Normal To the sketch plane
and keeps showing the shaded model.

So does the 2D view now. Behind the sketch it paints the part rendered
by the 3D view's own renderer, looking straight at the sketch plane, in
orthographic, at the 2D view's scale and place — the same picture the 3D
view ends its turn on, so it is exact by construction, not a second
drawing of the part:

- what is rendered is the part AS BUILT BEFORE THE SKETCH (`built_before`,
  through sketch_focus — which also says WHICH sketch is on show):
  editing the sketch of an earlier feature shows the part rolled back to
  it, as SolidWorks does, and the shapes being drawn are not in it twice;
- the camera is `face_sketch.camera_for(normal)` (screen right / up are
  the sketch's X / Y), its target the middle of the picture on the sketch
  plane, its distance what makes one millimetre as many pixels as in the
  2D view (`View3D._focal() / distance`);
- the picture covers more than is on screen (`MARGIN`), is painted in
  scene coordinates so it pans and zooms with the sketch, and is rendered
  again (after `DELAY_MS`) once the view leaves it, zooms in past its
  sharpness, or the model changes.

`paint` is called from SketchView.drawBackground; the face's own outline
and tint go over it (face_outline.paint).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: how much more than the visible rectangle is rendered, each side, as a
#: fraction of it
MARGIN = 0.5
#: the picture's longest side, in pixels
MAX_PX = 2800
#: wait this long after the last change before rendering again
DELAY_MS = 120
#: zoomed in past this many times the picture's own scale, it is redone
BLUR = 1.5


def focus_of(window):
    """The sketch on show in the 2D view (sketch_focus), or None."""
    from . import sketch_focus
    try:
        return sketch_focus.current(window)
    except Exception:
        return None


def tessellate(window, nodes):
    """(triangles, colours) of *nodes*, each whole and alone, in the
    scope's world."""
    from . import anchors, mesh
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    env = anchors.doc_env(window.model)
    fn = window.model.effective_fn()
    tris, cols = [], []
    with window._isolated_frame(iso):
        for node in nodes:
            if not node.visible or node.type in ("assign", "variables"):
                continue
            above = _colour_above(node)
            m = mesh.ancestor_matrix(node, env, stop=iso)
            got = mesh.tessellate_colored(node, env, fn=fn)
            tris += mesh.transform_mesh(m, [t for t, _c in got])
            cols += [c if c is not None else above for _t, c in got]
    if not any(c is not None for c in cols):
        cols = None
    return tris, cols


def built_before(window, node):
    """(triangles, colours) of the part as it was built BEFORE *node*'s
    sketch: the earlier siblings at every level up to the scope — never
    the sketch's own feature nor a later one. Flat sketch shapes are not
    part of it."""
    from .view2d import _produces_3d
    root = window._render_scope()[0]
    nodes = []
    probe = node
    while probe is not root and probe.parent is not None:
        kids = probe.parent.children
        nodes += [k for k in kids[:kids.index(probe)] if _produces_3d(k)]
        probe = probe.parent
    return tessellate(window, nodes)


def _colour_above(node):
    """The colour a `color` node above *node* gives it, or None."""
    probe = node.parent
    while probe is not None:
        if probe.type == "color":
            p = probe.params
            out = (str(p.get("color", "#4a90d9")),
                   float(p.get("alpha", 1.0) or 1.0))
            material = str(p.get("material", "") or "")
            return out + ((material,) if material and
                          material != "Default" else ())
        probe = probe.parent
    return None


def camera(focus, centre, px_per_mm, width, height):
    """The 3D camera that shows the sketch of *focus* square on, sketch
    point *centre* (x, y) in the middle of a *width* x *height* picture
    at *px_per_mm*: dict(yaw, pitch, target, distance)."""
    yaw, pitch = focus.angles()
    focal = 1.2 * min(width, height)          # View3D._focal
    return dict(yaw=yaw, pitch=pitch,
                target=focus.to_world(centre[0], centre[1]),
                distance=focal / max(px_per_mm, 1e-9))


def render(window, focus, rect, px_per_mm, pixel_ratio=1.0):
    """The picture of the part behind the sketch over scene rectangle
    *rect* (x, y, w, h — the sketch's own coordinates) at *px_per_mm*:
    (QImage ready to draw in a Y-up scene, rect, the scale it was really
    rendered at), or None when there is nothing to show."""
    tris, cols = focus.mesh()
    if not tris:
        return None
    x, y, w, h = rect
    k = float(px_per_mm)
    if max(w, h) * k > MAX_PX:
        k = MAX_PX / max(w, h)
    width, height = max(int(round(w * k)), 8), max(int(round(h * k)), 8)
    # whole pixels: the picture is as wide and high as they make it
    w2, h2 = width / k, height / k
    cam = camera(focus, (x + w / 2.0, y + h / 2.0), k, width, height)
    ratio = max(1.0, float(pixel_ratio or 1.0))
    image, _state = window.view3d.snapshot(
        int(round(width * ratio)), int(round(height * ratio)),
        yaw=cam["yaw"], pitch=cam["pitch"], distance=cam["distance"],
        target=cam["target"], projection="Orthographic", clean=True,
        transparent=True, pixel_ratio=ratio, mesh=tris, colors=cols,
        edges=True, cavity=False)
    # the scene is Y-up: drawn through its flipped transform the picture
    # comes out the right way round only when stored upside down
    rect = (x + (w - w2) / 2.0, y + (h - h2) / 2.0, w2, h2)
    return image.mirrored(False, True), rect, k


def _state(window):
    st = getattr(window, "_sketch_backdrop", None)
    if st is None:
        from PyQt5.QtCore import QTimer
        st = window._sketch_backdrop = dict(
            key=None, image=None, rect=None, k=0.0, dirty=True,
            timer=QTimer(window))
        st["timer"].setSingleShot(True)
        st["timer"].setInterval(DELAY_MS)
        st["timer"].timeout.connect(lambda: refresh(window))
        # the model changed: the picture is of the old one
        window.model.structure_changed.connect(lambda *a: invalidate(window))
        window.model.node_changed.connect(lambda *a: invalidate(window))
    return st


def invalidate(window):
    st = getattr(window, "_sketch_backdrop", None)
    if st is None:
        return
    st["dirty"] = True
    if focus_of(window) is not None:
        st["timer"].start()


def _visible(view):
    r = view.mapToScene(view.viewport().rect()).boundingRect()
    return r.x(), r.y(), r.width(), r.height()


def refresh(window):
    """Render the picture for what the 2D view shows now."""
    st = _state(window)
    focus = focus_of(window)
    view = window.view2d
    if focus is None:
        st.update(key=None, image=None, rect=None)
        return False
    x, y, w, h = _visible(view)
    if w <= 0 or h <= 0:
        return False
    k = abs(view.transform().m11())
    rect = (x - w * MARGIN, y - h * MARGIN, w * (1 + 2 * MARGIN),
            h * (1 + 2 * MARGIN))
    try:
        ratio = float(view.devicePixelRatioF())
    except Exception:
        ratio = 1.0
    try:
        got = render(window, focus, rect, k, ratio)
    except Exception:                    # never stop the sketch
        import traceback
        traceback.print_exc()
        got = None
    if got is None:
        st.update(key=focus.key(), image=None, rect=None, k=k, dirty=False)
    else:
        st.update(key=focus.key(), image=got[0], rect=got[1], k=got[2],
                  dirty=False)
    view.viewport().update()
    return got is not None


def _covers(rect, vis):
    return rect[0] <= vis[0] + 1e-9 and rect[1] <= vis[1] + 1e-9 and \
        rect[0] + rect[2] >= vis[0] + vis[2] - 1e-9 and \
        rect[1] + rect[3] >= vis[1] + vis[3] - 1e-9


def paint(view, painter):
    """Draw the picture under the sketch (from drawBackground). True
    while a sketch is on show (one-canvas Sketch Mode), whether or not a
    picture is ready yet."""
    window = view.window()
    if getattr(window, "view2d", None) is not view:
        return False                     # a twin of the view: no model
    focus = focus_of(window)
    if focus is None:
        return False
    st = _state(window)
    key = focus.key()
    k = abs(view.transform().m11())
    vis = _visible(view)
    same = st["key"] == key and not st["dirty"]
    fresh = same and st["rect"] is not None and \
        _covers(st["rect"], vis) and k <= st["k"] * BLUR + 1e-9
    empty = same and st["image"] is None and st["rect"] is None
    if not fresh and not empty and not st["timer"].isActive():
        st["timer"].start(0 if st["key"] != key else DELAY_MS)
    if st["image"] is not None and st["key"] == key:
        from PyQt5.QtCore import QRectF
        from PyQt5.QtGui import QPainter
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        x, y, w, h = st["rect"]
        painter.drawImage(QRectF(x, y, w, h), st["image"])
        painter.restore()
    return True


def face_rect(window, group, margin=0.18):
    """The scene rectangle (x, y, w, h) round the face the sketch stands
    on — its outline — with *margin* of its size left free all round;
    None when there is no outline."""
    info = getattr(window.view2d.scene(), "face_outline", None) or {}
    pts = [p for seg in info.get("segments") or () for p in seg]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    pad = max(w, h) * margin
    if not math.isfinite(pad) or max(w, h) <= 0:
        return None
    return (min(xs) - pad, min(ys) - pad, w + 2 * pad, h + 2 * pad)

# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Smart Dimension in the 2D sketch on an extrusion's DEPTH (2026-11-16,
the user: a boss seen in the 2D view, its edge clicked with Smart
Dimension, "should create a smart dimension"). The part's edges in the
sketch plane (`face_outline`) were copied in as FIXED reference lines, so
a length on one could only be driven — or "cannot hold with the other
constraints". An edge that runs along a Linear extrude's axis, within its
profile, IS that extrude's depth: the value typed sets its height."""

import math


def _world_of(scene, window):
    """sketch (u, v) -> world (x, y, z) for the sketch on show."""
    resolver = getattr(scene, "isolation_resolver", None)
    group = resolver() if resolver else None
    if group is not None and group is not window._render_scope()[0]:
        import numpy as np
        from . import model_refs
        m = model_refs.sketch_matrix(window, group)
        return lambda u, v: (m @ np.array([u, v, 0.0, 1.0]))[:3].tolist()
    plane = getattr(scene, "plane", "Top (XY)")
    if plane.startswith("Front"):
        return lambda u, v: [u, 0.0, v]
    if plane.startswith("Side"):
        return lambda u, v: [0.0, u, v]
    return lambda u, v: [u, v, 0.0]


def edge_at(scene, pos):
    """The part's straight edge in the sketch plane under *pos* (sketch
    coordinates (a, b)), or None."""
    from . import face_outline
    info = getattr(scene, "face_outline", None) or {}
    segs = info.get("segments") or []
    views = scene.views()
    k = abs(views[0].transform().m11()) if views else 1.0
    best = None
    for a, b in segs:
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
            continue
        x, y = face_outline._on_segment(pos.x(), pos.y(), a, b)
        d = math.hypot(pos.x() - x, pos.y() - y) * k
        if d <= face_outline.SNAP_PX and (best is None or d < best[0]):
            best = (d, a, b)
    if best is None:
        return None
    return face_outline._whole_edge(segs, best[1], best[2])


def press(scene, pos):
    """A Smart Dimension click with nothing picked: on an extrusion's
    depth edge it asks the depth and sets it. True when used."""
    views = scene.views()
    window = views[0].window() if views else None
    if window is None or not hasattr(window, "_render_scope"):
        return False
    edge = edge_at(scene, pos)
    if edge is None:
        return False
    from . import feature_dims
    try:
        world = _world_of(scene, window)
        seg = [world(*edge[0]), world(*edge[1])]
        ext = feature_dims.depth_at(window, dict(kind="edge", seg=seg))
    except Exception:
        return False
    if ext is None:
        return False
    from .sketch_constrain_ui import _ask_value, _value
    env = feature_dims._env(window)
    now = feature_dims._num(ext, "height", env, 10.0)
    scene.status.emit("Smart Dimension: that edge is the depth of %s."
                      % ext.name)
    text = _ask_value(scene, "length", now)
    if text is None:
        return True
    window.model.set_param(ext, "height", _value(text))
    scene.status.emit("%s depth set to %s." % (ext.name, text))
    return True

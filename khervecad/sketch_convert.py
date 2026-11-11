"""SolidWorks' **Convert Entities** (2026-11-11, the user): the part's
edges become sketch entities on the sketch being drawn.

Click an edge of the part (in the 2D sketch or the 3D one): its WHOLE
edge comes in — a straight side as one line, a round edge as an arc (a
`line` with a bulge, `sketch_arc`) or a circle when it closes. Click
inside the face sketched on: its whole outline comes in. The converted
entities are ordinary sketch shapes: dimension, trim, extrude them; a
point left on the part's edge is tied to it when the sketch closes
(`model_refs.adopt`), so they follow the part.

The geometry (`convert`, `edge_at`) is Qt-free and works on the face
outline's segments in the sketch's own coordinates
(`face_outline` info "segments").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

TOOL = "sk_convert"
LINE_W = 0.2


def _r(v):
    return round(float(v), 4) + 0.0


def _on(arc, p):
    (cx, cy), r = arc
    return abs(math.hypot(p[0] - cx, p[1] - cy) - r) < max(r * 0.02, 1e-3)


def _piece_on(arc, p, q):
    """The piece p-q runs along the arc: both ends AND its middle on it
    (a chord across the circle has its ends on it too)."""
    m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    return _on(arc, p) and _on(arc, q) and _on(arc, m)


def whole_edge(segs, a, b):
    """The outline pieces the edge through a-b belongs to: the whole
    straight side, or every piece of its arc / circle."""
    from . import face_outline
    for arc in face_outline.arcs(segs):
        if _piece_on(arc, a, b):
            return [(p, q) for p, q in segs if _piece_on(arc, p, q)]
    return [face_outline._whole_edge(segs, a, b)]


def convert(segs, outline=None):
    """[(type, params)] of sketch shapes along *segs* (pieces of an
    outline): circles where a loop is one whole arc, bulged lines for
    partial arcs, lines for straight runs."""
    from . import drawing, face_outline, sketch_arc
    outline = list(outline if outline is not None else segs)
    round_ = face_outline.arcs(outline)
    out = []
    for points, _s, closed in drawing._chains(list(segs)):
        if len(points) < 2:
            continue
        for arc in round_:
            if closed and all(_piece_on(arc, points[i],
                                        points[(i + 1) % len(points)])
                              for i in range(len(points))):
                (cx, cy), r = arc
                out.append(("circle", dict(x=_r(cx), y=_r(cy), radius=_r(r))))
                break
        else:
            run = points + [points[0]] if closed else points
            pieces = drawing.merge_collinear(list(zip(run, run[1:])))
            # consecutive pieces on one arc: one bulged line through them
            group, which = [], None
            for p, q in pieces + [(None, None)]:
                arc = None
                if p is not None:
                    arc = next((k for k, c in enumerate(round_)
                                if _piece_on(c, p, q)), None)
                if group and (arc != which or arc is None or p is None):
                    out.append(_shape(group, which is not None))
                    group = []
                if p is None:
                    break
                group.append((p, q))
                which = arc
    return out


def _shape(group, curved):
    from . import sketch_arc
    a, b = group[0][0], group[-1][1]
    params = dict(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]), y2=_r(b[1]),
                  width=LINE_W)
    if curved and len(group) >= 2:
        pts = [g[0] for g in group] + [b]
        m = pts[len(pts) // 2]
        bulge = sketch_arc.bulge_through(a, b, m)
        if bulge:
            params["bulge"] = round(bulge, 10)
    return ("line", params)


def edge_at(segs, p, tol):
    """The outline piece nearest *p* within *tol*, or None."""
    from . import face_outline
    best = None
    for a, b in segs:
        ex, ey = face_outline._on_segment(p[0], p[1], a, b)
        d = math.hypot(ex - p[0], ey - p[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, a, b)
    return None if best is None else (best[1], best[2])


def inside(segs, p):
    """Is *p* inside the outline (even-odd)?"""
    x, y = p
    n = 0
    for a, b in segs:
        if (a[1] > y) != (b[1] > y):
            t = (y - a[1]) / (b[1] - a[1])
            if a[0] + t * (b[0] - a[0]) > x:
                n += 1
    return n % 2 == 1


def click(model, parent, segs, p, tol, create=None):
    """One click of Convert Entities at sketch point *p*: the edge near
    it, else the whole face when *p* is inside. Returns the new nodes.
    *create(type, params)* makes a node where the sketch's shapes go."""
    segs = [(tuple(a[:2]), tuple(b[:2])) for a, b in segs]
    hit = edge_at(segs, p, tol)
    if hit is not None:
        pieces = whole_edge(segs, *hit)
        shapes = convert(pieces, segs)
    elif segs and inside(segs, p):
        shapes = convert(segs, segs)
    else:
        return []
    made = []
    for t, params in shapes:
        node = create(t, params) if create is not None else \
            model.add_node(t, params, parent=parent)
        model.rename(node, "Converted " + ("circle" if t == "circle"
                                           else "arc" if "bulge" in params
                                           else "edge"))
        made.append(node)
    return made


TIPS = {TOOL: (
    "Convert Entities",
    "Brings the part's edges into the sketch as sketch lines, arcs and "
    "circles — to dimension from, trim, or extrude again.",
    ["Open a sketch on a face (or a plane through the part).",
     "Click this, then click an edge of the part: the whole edge comes "
     "in. Click inside the face: its whole outline comes in.",
     "Esc or Select when done."],
    "A converted edge's ends stay on the part's edge when the sketch is "
    "closed, so it follows the part.")}

# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The sketch a selected feature was drawn from, outlined in 3D.

The selection tint is depth-tested (glrender._draw_highlight): it only
paints where the selected solid IS the surface you see. A boss reversed
into the part, or fused into it, has no surface of its own left, so
selecting its sketch lit nothing (2026-11-10, the user: "I expected
parts to be highlighted ... it's not"). SolidWorks highlights the
sketch's lines when a sketch is picked; so here a selected SKETCH (a
face sketch's Group, a Regions) also outlines the 2D shapes it holds,
on their plane. A selected extrude stays its solid alone (2026-11-01,
the user: each tree step as itself)."""

from .model import SHAPE_2D

#: a sketch, besides a face sketch's Group
HOLDERS = ("regions",)
#: at most this many shapes outlined for one selection
MAX_SHAPES = 200


def _holds_sketch(node):
    return node.type in HOLDERS or bool(node.params.get("face_sketch"))


def shape_ids(model, ids):
    """Ids of the drawn 2D shapes under the selected sketch holders —
    not construction (%), not the kept model edges."""
    from . import sketch_section
    out = []
    for nid in ids:
        node = model.find(nid)
        if node is None or not _holds_sketch(node):
            continue
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type == "regions":
                # the area it keeps, not every shape it was cut from
                out.append(n.id)
                continue
            stack.extend(reversed(n.children))
            if n.category != SHAPE_2D:
                continue
            if n.params.get("modifier") == "%" or not n.visible:
                continue
            if sketch_section.is_section(n):
                continue
            out.append(n.id)
            if len(out) >= MAX_SHAPES:
                return out
    return out

"""The AREA a Regions node keeps, drawn in the 2D sketch (2026-10-28, the
user: in a region "I expect whatever is in the region highlighted").

Its shapes are drawn as outlines once a Regions node holds them
(view2d._shape_fill), so the solid would otherwise not show at all: this
draws the union of its picks (`mesh.collect_outlines`, holes even-odd)
light blue under the shapes, in the frame of their sketch — and outlined
in the selection blue, filled stronger, when the Regions node is the one
selected. A selected shape inside it shows its own blue outline
(ShapeItem.paint). Never takes a click.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QBrush, QColor, QPainterPath, QPen
from PyQt5.QtWidgets import QGraphicsPathItem

SELECTED_INK = "#1f7ae0"


class RegionArea(QGraphicsPathItem):
    def __init__(self, node, selected):
        super().__init__()
        self.node = node
        from . import mesh
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        try:
            loops = mesh.collect_outlines(node)
        except Exception:
            loops = []
        for lp in loops:
            if len(lp) < 3:
                continue
            path.moveTo(QPointF(*lp[0][:2]))
            for p in lp[1:]:
                path.lineTo(QPointF(*p[:2]))
            path.closeSubpath()
        self.setPath(path)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(-1)                  # under its shapes
        if selected:
            pen = QPen(QColor(SELECTED_INK), 2.6)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setBrush(QBrush(QColor(31, 122, 224, 95)))
        else:
            self.setPen(QPen(Qt.NoPen))
            self.setBrush(QBrush(QColor(33, 118, 199, 45)))


def add_all(scene, scope, selected):
    """A RegionArea for every visible Regions node in *scope* whose
    shapes lie on the view's plane."""
    from PyQt5.QtWidgets import QGraphicsItem  # noqa: F401
    from . import view2d_edit
    from .model import SHAPE_2D
    for old in getattr(scene, "_region_areas", []):
        # the last rebuild's (stacked, they turned the sketch dark blue)
        try:
            if old.scene() is scene and old.parentItem() is None:
                scene.removeItem(old)
        except RuntimeError:                 # went with its frame
            pass
    out = []
    for node in scope.walk():
        if node.type != "regions" or not node.visible:
            continue
        kid = next((c for c in node.children if c.category == SHAPE_2D),
                   None)
        if kid is None or not view2d_edit.on_view_plane(scene, kid):
            continue
        area = RegionArea(node, node.id in selected)
        t = view2d_edit.frame_transform(scene, kid)
        if t is None:
            scene.addItem(area)
        else:
            frame = view2d_edit.Frame()
            frame.setTransform(t)
            frame.setZValue(-1)
            scene.addItem(frame)
            area.setParentItem(frame)
            scene._frames.append((frame, node))
        out.append(area)
    scene._region_areas = out
    return out

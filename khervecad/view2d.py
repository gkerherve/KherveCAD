"""2D sketch view — draw, select, move and resize the 2D profiles.

Top-right frame of the main window: a QGraphicsView (Y axis up, like
CAD) showing every visible 2D shape in the tree. The shape tools draw
new objects by dragging; the select tool moves shapes and drags their
resize handles. Every edit writes straight back into the node params,
so the properties panel, code tab and 3D preview follow live.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath,
                         QPen, QPolygonF)
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem, QGraphicsPathItem,
                             QGraphicsPolygonItem, QGraphicsRectItem,
                             QGraphicsScene, QGraphicsView)

from . import expr
from .model import SHAPE_2D, SHAPE_3D, CadNode, DocumentModel

SELECT, LINE, RECT, CIRCLE, POLYGON, TEXT, MEASURE, DIMENSION = (
    "select", "line", "rect", "circle", "polygon", "text",
    "measure", "dimension")

#: click within this many pixels of a shape feature (corner, centre,
#: edge midpoint) to snap the measure/dimension tools onto it.
FEATURE_SNAP_PX = 12.0

#: assembly view planes: name -> (horizontal axis, vertical axis)
#: as indices into (x, y, z) and the translate-param keys they map to.
PLANES = {
    "Top (XY)": ((0, 1), ("x", "y")),
    "Front (XZ)": ((0, 2), ("x", "z")),
    "Side (YZ)": ((1, 2), ("y", "z")),
}

_SHAPE_PEN_W = 1.6
HANDLE_SIZE = 9.0


def _pen(color: str, width=_SHAPE_PEN_W) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCosmetic(True)
    return pen


def _fmt_mm(value: float) -> str:
    """A tidy millimetre label: no trailing zeros (30, 30.5, 36.06)."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text or '0'} mm"


def _point_seg_dist(p: QPointF, a: QPointF, b: QPointF) -> float:
    """Shortest distance from point *p* to segment *a*-*b*."""
    vx, vy = b.x() - a.x(), b.y() - a.y()
    wx, wy = p.x() - a.x(), p.y() - a.y()
    seg2 = vx * vx + vy * vy
    tval = 0.0 if seg2 < 1e-12 else (wx * vx + wy * vy) / seg2
    tval = max(0.0, min(1.0, tval))
    dx, dy = a.x() + tval * vx - p.x(), a.y() + tval * vy - p.y()
    return (dx * dx + dy * dy) ** 0.5


class HandleItem(QGraphicsRectItem):
    """Square resize handle, constant size on screen."""

    def __init__(self, role: str, parent, snap=True, hot=False):
        size = HANDLE_SIZE
        super().__init__(-size / 2, -size / 2, size, size, parent)
        self.role = role
        self._snap = snap                  # dimension handles opt out
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        if hot:                            # the point picked in the table
            self.setBrush(QBrush(QColor("#e53935")))
            self.setPen(_pen("#b71c1c", 1.6))
        else:
            self.setBrush(QBrush(QColor("#ffffff")))
            self.setPen(_pen("#2176c7", 1.2))
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptedMouseButtons(Qt.LeftButton)

    def mousePressEvent(self, event):
        parent = self.parentItem()
        if hasattr(parent, "handle_pressed"):
            # record the grab point so the drag is measured as a delta
            parent.handle_pressed(self.role, event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event):
        # the cursor's scene position directly — robust even though the
        # handle ignores view transforms and slides out from under the
        # cursor (mapToScene of event.pos() jitters in that case)
        pos = event.scenePos()
        if self._snap:
            pos = self.scene().snap(pos)
        self.parentItem().handle_dragged(self.role, pos)

    def mouseReleaseEvent(self, event):
        event.accept()


class ShapeItem:
    """Mixin for scene items bound to a CadNode."""

    def init_node(self, node, scene):
        self.node = node
        self._scene = scene
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.handles = []
        self._hot_vertex = -1              # point picked in the table

    def rv(self, key, default=0.0) -> float:
        """Param as a number — expressions preview with loop start
        values (editing writes plain numbers back)."""
        return expr.resolve(self.node.params.get(key),
                            self._scene.env_for(self.node), default)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and \
                not self._scene.updating:
            value = self._scene.snap(value)
        elif change == QGraphicsItem.ItemPositionHasChanged and \
                not self._scene.updating:
            self._scene.push_move(self)
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.refresh_handles()
            if not self._scene.updating:
                self._scene.emit_selection()
        return super().itemChange(change, value)

    # -------- handles: subclasses define handle roles + positions
    def handle_spec(self):
        return []                                  # [(role, local pos)]

    def refresh_handles(self):
        for handle in self.handles:
            self._scene.removeItem(handle)
        self.handles = []
        if self.isSelected():
            hot = f"v{self._hot_vertex}"
            for role, pos in self.handle_spec():
                handle = HandleItem(role, self, hot=(role == hot))
                handle.setPos(pos)
                self.handles.append(handle)

    def set_hot_vertex(self, index):
        """Mark one polygon vertex (the point selected in the properties
        table) so its handle stands out red in the sketch."""
        if index != self._hot_vertex:
            self._hot_vertex = index
            self.refresh_handles()

    def reposition_handles(self):
        spec = dict(self.handle_spec())
        for handle in self.handles:
            if handle.role in spec:
                handle.setPos(spec[handle.role])

    def handle_dragged(self, role, scene_pos):
        pass

    def apply_node(self):
        """Model -> item geometry (called inside scene.updating)."""
        raise NotImplementedError

    def push_pos(self):
        """Item position -> model params after a move."""
        raise NotImplementedError


class LineShapeItem(ShapeItem, QGraphicsLineItem):
    def __init__(self, node, scene):
        super().__init__()
        self.init_node(node, scene)
        self.apply_node()

    def apply_node(self):
        x1, y1 = self.rv("x1"), self.rv("y1")
        self.setPos(x1, y1)
        self.setLine(0, 0, self.rv("x2") - x1, self.rv("y2") - y1)
        pen = _pen("#2e3440", max(self.rv("width", 1.0), 0.5))
        pen.setCosmetic(False)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.reposition_handles()

    def push_pos(self):
        p = self.node.params
        dx = self.pos().x() - p["x1"]
        dy = self.pos().y() - p["y1"]
        p["x1"] += dx
        p["y1"] += dy
        p["x2"] += dx
        p["y2"] += dy
        self._scene.model.node_changed.emit(self.node)

    def handle_spec(self):
        line = self.line()
        return [("p1", line.p1()), ("p2", line.p2())]

    def handle_dragged(self, role, scene_pos):
        p = self.node.params
        key_x, key_y = ("x1", "y1") if role == "p1" else ("x2", "y2")
        p[key_x], p[key_y] = scene_pos.x(), scene_pos.y()
        self._scene.model.node_changed.emit(self.node)


class RectShapeItem(ShapeItem, QGraphicsRectItem):
    def __init__(self, node, scene):
        super().__init__()
        self.init_node(node, scene)
        self.setPen(_pen("#2e3440"))
        self.setBrush(QBrush(QColor(33, 118, 199, 40)))
        self.apply_node()

    def apply_node(self):
        self.setPos(self.rv("x"), self.rv("y"))
        self.setRect(0, 0, self.rv("width", 1.0),
                     self.rv("height", 1.0))
        self.reposition_handles()

    def push_pos(self):
        p = self.node.params
        p["x"], p["y"] = self.pos().x(), self.pos().y()
        self._scene.model.node_changed.emit(self.node)

    def handle_spec(self):
        rect = self.rect()
        return [("br", rect.bottomRight()), ("tr", rect.topRight()),
                ("bl", rect.bottomLeft()), ("tl", rect.topLeft())]

    def handle_dragged(self, role, scene_pos):
        p = self.node.params
        left, bottom = self.rv("x"), self.rv("y")
        right = left + self.rv("width", 1.0)
        top = bottom + self.rv("height", 1.0)
        if "r" in role:
            right = scene_pos.x()
        else:
            left = scene_pos.x()
        # note: local "t"op handles are at larger y (Y-up view)
        if role in ("tr", "tl"):
            top = scene_pos.y()
        else:
            bottom = scene_pos.y()
        p["x"], p["y"] = min(left, right), min(bottom, top)
        p["width"] = max(abs(right - left), 0.01)
        p["height"] = max(abs(top - bottom), 0.01)
        self._scene.model.node_changed.emit(self.node)


class CircleShapeItem(ShapeItem, QGraphicsEllipseItem):
    def __init__(self, node, scene):
        super().__init__()
        self.init_node(node, scene)
        self.setPen(_pen("#2e3440"))
        self.setBrush(QBrush(QColor(33, 118, 199, 40)))
        self.apply_node()

    def apply_node(self):
        r = self.rv("radius", 1.0)
        self.setPos(self.rv("x"), self.rv("y"))
        self.setRect(-r, -r, 2 * r, 2 * r)
        angle = self.rv("angle", 360.0)
        if angle < 360.0:
            # Qt draws a pie when the span is partial; angles match
            # world CCW because the whole view is Y-flipped.
            self.setStartAngle(int(self.rv("start_angle") * 16))
            self.setSpanAngle(int(angle * 16))
        else:
            self.setStartAngle(0)
            self.setSpanAngle(360 * 16)
        self.reposition_handles()

    def push_pos(self):
        p = self.node.params
        p["x"], p["y"] = self.pos().x(), self.pos().y()
        self._scene.model.node_changed.emit(self.node)

    def handle_spec(self):
        return [("radius", QPointF(self.rv("radius", 1.0), 0))]

    def handle_dragged(self, role, scene_pos):
        p = self.node.params
        center = self.pos()
        radius = ((scene_pos.x() - center.x()) ** 2 +
                  (scene_pos.y() - center.y()) ** 2) ** 0.5
        p["radius"] = max(radius, 0.01)
        self._scene.model.node_changed.emit(self.node)


class PolygonShapeItem(ShapeItem, QGraphicsPolygonItem):
    def __init__(self, node, scene):
        super().__init__()
        self.init_node(node, scene)
        self.setPen(_pen("#2e3440"))
        self.setBrush(QBrush(QColor(33, 118, 199, 40)))
        self.apply_node()

    def apply_node(self):
        p = self.node.params
        env = self._scene.env_for(self.node)
        self.setPos(self.rv("x"), self.rv("y"))
        self.setPolygon(QPolygonF(
            [QPointF(expr.resolve(x, env), expr.resolve(y, env))
             for x, y in p["points"]]))
        self.reposition_handles()

    def push_pos(self):
        p = self.node.params
        p["x"], p["y"] = self.pos().x(), self.pos().y()
        self._scene.model.node_changed.emit(self.node)

    def handle_spec(self):
        return [(f"v{i}", QPointF(x, y))
                for i, (x, y) in enumerate(self.node.params["points"])]

    def handle_dragged(self, role, scene_pos):
        index = int(role[1:])
        local = scene_pos - self.pos()
        self.node.params["points"][index] = [local.x(), local.y()]
        self._scene.model.node_changed.emit(self.node)


class TextShapeItem(ShapeItem, QGraphicsPathItem):
    def __init__(self, node, scene):
        super().__init__()
        self.init_node(node, scene)
        self.setPen(_pen("#2e3440", 1.0))
        self.setBrush(QBrush(QColor(33, 118, 199, 90)))
        self.apply_node()

    def apply_node(self):
        p = self.node.params
        self.setPos(self.rv("x"), self.rv("y"))
        font = QFont("DejaVu Sans")
        font.setPointSizeF(max(self.rv("size", 10.0), 0.5))
        path = QPainterPath()
        path.addText(0, 0, font, str(p["text"]))
        # The view is Y-flipped; flip the glyphs back upright.
        self.setPath(path * self._flip())
        self.reposition_handles()

    @staticmethod
    def _flip():
        from PyQt5.QtGui import QTransform
        return QTransform(1, 0, 0, -1, 0, 0)

    def push_pos(self):
        p = self.node.params
        p["x"], p["y"] = self.pos().x(), self.pos().y()
        self._scene.model.node_changed.emit(self.node)


_ITEM_CLASSES = dict(line=LineShapeItem, rect=RectShapeItem,
                     circle=CircleShapeItem, polygon=PolygonShapeItem,
                     text=TextShapeItem)


def _produces_3d(node) -> bool:
    """True if the subtree makes solid geometry (an assemblable part).
    A Linked copy renders its master, so it counts too."""
    return any(n.category == SHAPE_3D
               or n.type in ("linear_extrude", "rotate_extrude",
                             "reference")
               for n in node.walk())


class PartItem(QGraphicsPathItem):
    """A part (a subtree) shown in the assembly plane. Two flavours:

    - *outline* (dashed, theme accent): the assembly overview — one per
      top-level part, draggable to position it (the move commits into a
      translate node so assemblies are ordinary tree structure);
    - *silhouette* (solid amber): the true projected shape of the
      selected object, shown alone so you see exactly that part in its
      real orientation.
    """

    def __init__(self, node, scene, path, label, movable=True,
                 dashed=True, dims=None):
        super().__init__()
        self.node = node
        self._scene = scene
        self._movable = movable
        self._dims = dims or []            # dimension-edit handle specs
        self.handles = []
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if movable:
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        if dashed:
            from .style import tokens
            color = QColor(tokens()["select"])
            pen = QPen(color, 1.4, Qt.DashLine)
            pen.setCosmetic(True)
            fill_alpha = 26
        else:
            # solid filled silhouette — no pen, or the internal
            # triangle edges would show as a wireframe
            color = QColor("#ff8c1a")         # isolated-part accent
            pen = QPen(Qt.NoPen)
            fill_alpha = 150
        self.setPen(pen)
        self._label_color = QColor(color)
        fill = QColor(color)
        fill.setAlpha(fill_alpha)
        self.setBrush(QBrush(fill))
        if not dashed:
            # the silhouette is a heavy static path; cache its raster
            # so panning/redraw stay smooth (re-rasters only on zoom)
            self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.setPath(path)
        rect = path.boundingRect()
        self._label = label
        self._label_pos = QPointF(rect.left(), rect.bottom())

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.save()
        painter.translate(self._label_pos)
        painter.scale(1, -1)                  # the view is Y-flipped
        font = painter.font()
        size = max(self.path().boundingRect().height() * 0.09, 2.0)
        font.setPointSizeF(size)
        painter.setFont(font)
        painter.setPen(self._label_color)
        painter.drawText(QPointF(0, -size * 0.4), self._label)
        painter.restore()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and \
                not self._scene.updating:
            return self._scene.snap(value)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._refresh_dim_handles()
            if not self._scene.updating:
                self._scene.emit_selection()
        return super().itemChange(change, value)

    # -------- dimension handles (editable primitive sizes in 2D)
    def _refresh_dim_handles(self):
        for handle in self.handles:
            if handle.scene() is not None:
                self._scene.removeItem(handle)
        self.handles = []
        if self.isSelected() and self._dims:
            for spec in self._dims:
                handle = HandleItem(spec["role"], self, snap=False)
                handle.setPos(spec["tip"])
                self.handles.append(handle)

    def handle_pressed(self, role, scene_pos):
        """Remember the grab point and starting value so the drag is a
        stable delta rather than an absolute re-projection each frame."""
        spec = next((d for d in self._dims if d["role"] == role), None)
        if spec is not None:
            spec["_grab"] = scene_pos
            spec["_start"] = spec["value"]

    def handle_dragged(self, role, scene_pos):
        spec = next((d for d in self._dims if d["role"] == role), None)
        if spec is None or "_grab" not in spec:
            return
        ax, ay = spec["axis"]
        denom = ax * ax + ay * ay
        if denom < 1e-12:
            return
        # how far the cursor has moved *along the handle's axis* since
        # the grab, in local mm — measured from a fixed reference so it
        # never jitters, and unaffected by the handle itself moving
        travel = ((scene_pos.x() - spec["_grab"].x()) * ax
                  + (scene_pos.y() - spec["_grab"].y()) * ay) / denom
        value = spec["_start"] + travel * spec["factor"]
        # snap the resulting dimension to the grid (not the cursor — that
        # was what made the drag erratic); a plain round keeps radii on
        # nice increments without any jitter
        if self._scene.snap_enabled:
            g = self._scene.grid_size
            value = round(value / g) * g
        value = max(value, spec["minval"])
        self.node.params[spec["param"]] = round(value, 4)
        self._scene.model.node_changed.emit(self.node)
        # slide the grabbed handle to reflect the new size (feedback)
        mag = value / spec["factor"]
        for handle in self.handles:
            if handle.role == role:
                handle.setPos(QPointF(spec["anchor"].x() + mag * ax,
                                      spec["anchor"].y() + mag * ay))

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._movable:
            # committing may rebuild the scene, so do it after our own
            # mouse handling is completely finished
            self._scene.commit_part_move(self.node, self.pos())


# ------------------------------------------------------------------ scene

class SketchScene(QGraphicsScene):
    """All visible 2D shapes of the document + the drawing tools."""

    selection_changed = pyqtSignal(list)      # list of CadNode
    node_created = pyqtSignal(object)         # CadNode
    measure_changed = pyqtSignal(str)         # live mm readout

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(-2000, -2000, 4000, 4000, parent)
        self.model = model
        self.tool = SELECT
        self.plane = "Top (XY)"                # assembly view plane
        self.grid_size = 0.5
        self.snap_enabled = True
        self.show_grid = True
        self.show_dims = True                  # auto size on selection
        self.updating = False
        self._items = {}                       # node id -> shape item
        self._part_items = {}                  # node id -> part item
        self._draft = None                     # item being drawn
        self._draft_start = None
        self._poly_points = []
        self._part_dirty = False
        self._highlight_ids = set()            # selected nodes
        self._highlight_items = []
        self._point_hl = (None, -1)            # (polygon id, vertex idx)
        # measure/dimension tools: two scene points (mm) + the live end
        self._measure_a = None
        self._measure_b = None
        self._measure_cursor = None
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._node_changed)
        model.dimensions_changed.connect(self.update)
        # repaint the overlay so auto size-on-selection follows the pick
        self.selectionChanged.connect(self.update)
        self.rebuild()

    def set_plane(self, plane: str):
        if plane in PLANES and plane != self.plane:
            self.plane = plane
            self.clear_measure()               # points belong to a plane
            self.rebuild()

    # ------------------------------------------------------------ sync
    def env_for(self, node) -> dict:
        """Variables visible to *node* for preview purposes: document
        assigns plus ancestor loop variables at their first value."""
        env = {}
        for n in self.model.root.walk():
            if n.type == "assign" and n.visible:
                var = str(n.params.get("variable", "")).strip()
                if var:
                    env[var] = expr.resolve(n.params.get("value", 0),
                                            env, 0.0)
        ancestor = node.parent
        while ancestor is not None:
            if ancestor.type in ("for_loop", "while_loop"):
                values = ancestor.loop_values(env)
                var = str(ancestor.params.get("variable", "i")) or "i"
                env.setdefault(var, values[0] if values else 0.0)
            ancestor = ancestor.parent
        return env

    def snap(self, pos: QPointF) -> QPointF:
        if not self.snap_enabled:
            return pos
        g = self.grid_size
        return QPointF(round(pos.x() / g) * g, round(pos.y() / g) * g)

    # -------------------------------------------------- feature snapping
    def _item_feature_points(self, item):
        """Snap targets for one shape/part item, in *scene* coords:
        corners, centres and edge midpoints — the points you dimension
        to on a drawing."""
        pts = []
        if isinstance(item, QGraphicsLineItem):
            ln = item.line()
            a, b = ln.p1(), ln.p2()
            pts = [a, b, (a + b) / 2.0]
        elif isinstance(item, QGraphicsEllipseItem):
            r = item.rect()
            c = r.center()
            pts = [c, QPointF(c.x(), r.top()), QPointF(c.x(), r.bottom()),
                   QPointF(r.left(), c.y()), QPointF(r.right(), c.y())]
        elif isinstance(item, QGraphicsRectItem):
            r = item.rect()
            tl, tr = r.topLeft(), r.topRight()
            bl, br = r.bottomLeft(), r.bottomRight()
            pts = [tl, tr, bl, br, r.center(),
                   (tl + tr) / 2.0, (bl + br) / 2.0,
                   (tl + bl) / 2.0, (tr + br) / 2.0]
        elif isinstance(item, QGraphicsPolygonItem):
            pts = list(item.polygon())
        elif isinstance(item, QGraphicsPathItem):
            for poly in item.path().toSubpathPolygons():
                pts += list(poly)
            pts.append(item.boundingRect().center())
        return [item.mapToScene(p) for p in pts]

    def feature_points(self):
        """Every snap target on every visible shape/part."""
        pts = []
        for item in self.items():
            if isinstance(item, (ShapeItem, PartItem)):
                pts += self._item_feature_points(item)
        return pts

    def snap_feature(self, scene_pos):
        """Snap to the nearest shape feature within a few pixels; else
        grid-snap. Returns ``(point, on_feature)``."""
        views = self.views()
        ppm = views[0].px_per_mm() if views else 4.0
        tol = FEATURE_SNAP_PX / max(ppm, 1e-6)
        best, best_d = None, tol
        for p in self.feature_points():
            d = ((p.x() - scene_pos.x()) ** 2 +
                 (p.y() - scene_pos.y()) ** 2) ** 0.5
            if d < best_d:
                best, best_d = p, d
        if best is not None:
            return best, True
        return self.snap(scene_pos), False

    # ----------------------------------------------------- measure tool
    def clear_measure(self):
        if self._measure_a is not None or self._measure_b is not None:
            self._measure_a = self._measure_b = self._measure_cursor = None
            self.measure_changed.emit("")
            self.update()

    def _emit_measure(self, a, b):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        dist = (dx * dx + dy * dy) ** 0.5
        self.measure_changed.emit(
            f"distance: {dist:.2f} mm    Δ {dx:.2f}, {dy:.2f} mm")

    def rebuild(self):
        self.updating = True
        selected = {n.id for n in self.selected_nodes()}
        for item in list(self._items.values()) \
                + list(self._part_items.values()) \
                + self._highlight_items:
            self.removeItem(item)
        self._items.clear()
        self._part_items.clear()
        self._highlight_items = []

        focus = self._focus_shapes()
        if focus:
            # profile-edit mode: the selected 2D profile is shown alone
            # and fully editable (drag points to resize, drag the shape
            # to move) in its own sketch coordinates, at any plane — so
            # a profile buried in a part can be reshaped from the 2D
            # view without opening the Top plane.
            for node in focus:
                cls = _ITEM_CLASSES.get(node.type)
                if cls is None:
                    continue
                item = cls(node, self)
                self.addItem(item)
                self._items[node.id] = item
                item.setSelected(True)
                self._apply_point_hl(item, node)
            self.updating = False
            return

        if self._isolating():
            # show only the selected object(s), as their true projected
            # shape in the current plane
            seen = set()
            for node_id in self._highlight_ids:
                node = self.model.find(node_id)
                target = self._isolate_target(node) if node else None
                if target is None or target.id in seen:
                    continue
                seen.add(target.id)
                item = self._make_silhouette(target)
                if item is not None:
                    self.addItem(item)
                    self._part_items[target.id] = item
                    item.setSelected(True)
            self.updating = False
            return

        if self.plane == "Top (XY)":
            # sketch mode: individual 2D shapes are editable
            for node in self.model.root.walk():
                if node.category == SHAPE_2D and \
                        self._branch_visible(node):
                    item = _ITEM_CLASSES[node.type](node, self)
                    self.addItem(item)
                    self._items[node.id] = item
                    if node.id in selected:
                        item.setSelected(True)
                        self._apply_point_hl(item, node)
        # assembly mode: every top-level part gets a draggable outline
        for node in self.model.root.children:
            if node.visible and _produces_3d(node):
                item = self._make_part_item(node)
                if item is not None:
                    self.addItem(item)
                    self._part_items[node.id] = item
                    if node.id in selected:
                        item.setSelected(True)
        self.updating = False

    def _apply_point_hl(self, item, node):
        if self._point_hl[0] == node.id \
                and hasattr(item, "set_hot_vertex"):
            item.set_hot_vertex(self._point_hl[1])

    def set_point_highlight(self, node, index):
        """Highlight one polygon vertex in red — the point the user
        picked in the properties Points table."""
        self._point_hl = (node.id if node is not None else None, index)
        item = self._items.get(node.id) if node is not None else None
        if item is not None and hasattr(item, "set_hot_vertex"):
            item.set_hot_vertex(index)

    # ------------------------------------------------------- highlight
    def set_highlight(self, nodes):
        """Select these objects: a 3D part isolates in the 2D view
        (only it is shown, in its real projected shape); 2D sketch
        shapes just get selected in place."""
        self._highlight_ids = {n.id for n in nodes}
        self._point_hl = (None, -1)            # fresh selection, no point
        self.rebuild()

    def _isolate_target(self, node):
        """The object to show alone for *node*: the node itself if it
        makes 3D geometry, else the nearest ancestor part that does
        (so clicking a flange's profile or revolve shows the flange).
        Returns None for a bare top-level 2D sketch shape."""
        if node is None:
            return None
        if _produces_3d(node):
            return node
        probe = node.parent
        while probe is not None and probe is not self.model.root:
            if _produces_3d(probe):
                return probe
            probe = probe.parent
        return None

    def _isolating(self) -> bool:
        """True when the selection is (or lives inside) a solid part we
        should show alone, rather than editing 2D sketch shapes."""
        return any(self._isolate_target(self.model.find(nid))
                   is not None for nid in self._highlight_ids)

    def _focus_shapes(self):
        """Selected 2D profiles that live *inside* a solid part — shown
        alone and directly editable in the sketch view, at any plane.
        Takes priority over isolating the 3D part they belong to. Bare
        top-level sketch shapes are left to normal sketch mode."""
        out, seen = [], set()
        for nid in self._highlight_ids:
            node = self.model.find(nid)
            if node is not None and node.category == SHAPE_2D \
                    and node.id not in seen \
                    and self._isolate_target(node) is not None:
                seen.add(node.id)
                out.append(node)
        return out

    def focus_shape_rect(self):
        """Scene bounds of the profile(s) in profile-edit mode, so the
        view can frame them; None when not editing a profile."""
        rect = None
        for node in self._focus_shapes():
            item = self._items.get(node.id)
            if item is None:
                continue
            box = item.sceneBoundingRect()
            rect = box if rect is None else rect.united(box)
        return rect

    def isolated_bounds(self):
        """Scene bounds of the object shown alone — a 3D part silhouette
        or an edited 2D profile — so the view can zoom to fit it on
        selection. None when the whole assembly is on screen."""
        if not (self._isolating() or self._focus_shapes()):
            return None
        rect = None
        for item in list(self._part_items.values()) \
                + list(self._items.values()):
            box = item.sceneBoundingRect()
            rect = box if rect is None else rect.united(box)
        return rect

    def _make_silhouette(self, node):
        """The selected node's real projected outline in the current
        plane — the union of its projected triangles, so concavities
        and bores show and the shape is correctly oriented."""
        from . import mesh as mesh_mod
        (ai, bi), _keys = PLANES[self.plane]
        # a low-detail tessellation keeps the silhouette light; the
        # winding-fill union of the projected triangles is the real
        # filled shape (holes and concavities included), built
        # instantly — no simplify() (it explodes on helical threads).
        tris = mesh_mod.selected_world_tris(
            self.model.root, {node.id}, detail=14,
            fn=self.model.effective_fn())
        if not tris:
            return None
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        for tri in tris:
            p0, p1, p2 = ((v[ai], v[bi]) for v in tri)
            # a closed solid's front and back faces project with
            # opposite winding and would cancel under WindingFill, so
            # force every projected triangle the same way (CCW) — then
            # the union fills solidly into the true silhouette
            area = ((p1[0] - p0[0]) * (p2[1] - p0[1])
                    - (p2[0] - p0[0]) * (p1[1] - p0[1]))
            pts = (p0, p1, p2) if area >= 0 else (p0, p2, p1)
            path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        movable = node.parent is self.model.root
        return PartItem(node, self, path, node.name, movable=movable,
                        dashed=False, dims=self._dim_handles(node))

    def _world_matrix(self, node):
        """4x4 transform mapping *node*'s local coordinates to world —
        the product of its ancestor translate/rotate/scale/mirror nodes,
        with expressions resolved (loop vars at their first value)."""
        from . import mesh as mesh_mod
        chain = []
        probe = node.parent
        while probe is not None:
            chain.append(probe)
            probe = probe.parent
        mat = mesh_mod.mat_identity()
        builders = dict(translate=mesh_mod.mat_translate,
                        rotate=mesh_mod.mat_rotate,
                        scale=mesh_mod.mat_scale,
                        mirror=mesh_mod.mat_mirror)
        for anc in reversed(chain):                # root .. parent order
            if anc.type in builders:
                p = mesh_mod.rp(anc, self.env_for(anc))
                default = 1.0 if anc.type == "scale" else 0.0
                mat = mesh_mod.mat_mul(mat, builders[anc.type](
                    p.get("x", default), p.get("y", default),
                    p.get("z", default)))
        return mat

    def _dim_handles(self, node):
        """Editable size handles for a 3D primitive in the current plane
        — cylinder radii + height, cube sides, sphere radius — mapped
        through the node's ancestor transforms so a drag in the plane
        changes the right parameter. Handles whose axis points along the
        view direction (invisible here) are dropped."""
        from . import mesh as mesh_mod
        if node.type not in ("cylinder", "cube", "sphere"):
            return []
        (ai, bi), _keys = PLANES[self.plane]
        env = self.env_for(node)
        mat = self._world_matrix(node)

        def val(key, default=0.0):
            return expr.resolve(node.params.get(key, default), env,
                                default)

        def project(p):                            # local point -> 2D
            w = mesh_mod.transform_point(mat, p)
            return QPointF(w[ai], w[bi])

        def direction(d):                          # local dir -> 2D vec
            w = (mat[0][0] * d[0] + mat[0][1] * d[1] + mat[0][2] * d[2],
                 mat[1][0] * d[0] + mat[1][1] * d[1] + mat[1][2] * d[2],
                 mat[2][0] * d[0] + mat[2][1] * d[1] + mat[2][2] * d[2])
            return (w[ai], w[bi])

        px, py, pz = val("x"), val("y"), val("z")
        center = bool(node.params.get("center"))
        out = []

        def add(role, param, anchor3, dir3, mag, factor):
            ax = direction(dir3)
            if ax[0] * ax[0] + ax[1] * ax[1] < 1e-9:
                return                             # edge-on in this plane
            anchor = project(anchor3)
            out.append(dict(
                role=role, param=param, anchor=anchor, axis=ax,
                factor=factor, minval=0.1, value=mag * factor,
                tip=QPointF(anchor.x() + ax[0] * mag,
                            anchor.y() + ax[1] * mag)))

        if node.type == "cylinder":
            h = val("height")
            z0 = pz - (h / 2 if center else 0.0)
            z1 = z0 + h
            # radius direction most visible in this plane
            radial = max(((1, 0, 0), (0, 1, 0)),
                         key=lambda d: sum(c * c for c in direction(d)))
            add("radius_bottom", "radius_bottom", (px, py, z0), radial,
                val("radius_bottom"), 1.0)
            add("radius_top", "radius_top", (px, py, z1), radial,
                val("radius_top"), 1.0)
            add("height", "height", (px, py, z0), (0, 0, 1), h, 1.0)
        elif node.type == "sphere":
            radial = max(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                         key=lambda d: sum(c * c for c in direction(d)))
            add("radius", "radius", (px, py, pz), radial,
                val("radius"), 1.0)
        else:                                       # cube
            w, d, hh = val("width"), val("depth"), val("height")
            if center:
                # grows symmetrically about the centre: dragging a face
                # by t changes the dimension by 2t
                add("width", "width", (px, py, pz), (1, 0, 0), w / 2, 2.0)
                add("depth", "depth", (px, py, pz), (0, 1, 0), d / 2, 2.0)
                add("height", "height", (px, py, pz), (0, 0, 1),
                    hh / 2, 2.0)
            else:
                # anchored at its min corner: drag the far face, the
                # dimension is just the distance to it
                cx, cy, cz = px + w / 2, py + d / 2, pz + hh / 2
                add("width", "width", (px, cy, cz), (1, 0, 0), w, 1.0)
                add("depth", "depth", (cx, py, cz), (0, 1, 0), d, 1.0)
                add("height", "height", (cx, cy, pz), (0, 0, 1), hh, 1.0)
        return out

    def _make_part_item(self, node):
        from . import mesh as mesh_mod
        tris = mesh_mod.tessellate(node, self.env_for(node),
                                   fn=self.model.effective_fn())
        if not tris:
            return None
        (ai, bi), _keys = PLANES[self.plane]
        points = [(v[ai], v[bi]) for tri in tris for v in tri]
        outline = mesh_mod.convex_hull_2d(points)
        if len(outline) < 3:
            return None
        path = QPainterPath()
        path.moveTo(QPointF(*outline[0]))
        for point in outline[1:]:
            path.lineTo(QPointF(*point))
        path.closeSubpath()
        return PartItem(node, self, path, node.name)

    def commit_part_move(self, node, delta):
        """A part outline was dropped: bake the move into the object.
        Translate nodes and Groups carry their own position, so those
        are edited in place; anything else is wrapped in a translate."""
        if abs(delta.x()) < 1e-9 and abs(delta.y()) < 1e-9:
            return
        _axes, (kx, ky) = PLANES[self.plane]
        # a Group or Linked copy is a part with its own move params
        if node.type in ("translate", "union", "reference"):
            env = self.env_for(node)
            node.params[kx] = round(
                expr.resolve(node.params.get(kx, 0.0), env, 0.0)
                + delta.x(), 4)
            node.params[ky] = round(
                expr.resolve(node.params.get(ky, 0.0), env, 0.0)
                + delta.y(), 4)
            self.model.node_changed.emit(node)
            return
        parent, index = node.parent, node.index()
        wrapper = CadNode("translate",
                          self.model.unique_name("translate"),
                          {kx: round(delta.x(), 4),
                           ky: round(delta.y(), 4)})
        wrapper.name = f"Position ({node.name})"
        parent.remove(node)
        wrapper.add(node)
        parent.add(wrapper, index)
        self.model.structure_changed.emit()

    @staticmethod
    def _branch_visible(node):
        while node is not None:
            if not node.visible:
                return False
            node = node.parent
        return True

    def _node_changed(self, node):
        if node.is_container():
            # A group's visibility change affects every descendant.
            self.rebuild()
            return
        item = self._items.get(node.id)
        if node.id in {n.id for n in self._focus_shapes()}:
            # editing the isolated profile: update it in place so an
            # in-progress point drag is never torn down by a rebuild
            if item is not None:
                self.updating = True
                item.apply_node()
                self.updating = False
            else:
                self.rebuild()
            return
        if self._in_part(node):
            if self.mouseGrabberItem() is not None:
                self._part_dirty = True        # refresh after the drag
            else:
                self.rebuild()                 # part outline changed
            return
        should_show = (self.plane == "Top (XY)"
                       and node.category == SHAPE_2D
                       and self._branch_visible(node))
        if (item is not None) != should_show:
            self.rebuild()
        elif item is not None:
            self.updating = True
            item.apply_node()
            self.updating = False
            self.update()                # auto dims track a live resize

    def _in_part(self, node) -> bool:
        probe = node
        while probe is not None:
            if probe.id in self._part_items:
                return True
            probe = probe.parent
        return False

    def push_move(self, item):
        self.updating = True
        item.push_pos()
        item.apply_node()
        self.updating = False

    def selected_nodes(self):
        return [item.node for item in self.selectedItems()
                if isinstance(item, (ShapeItem, PartItem))]

    def emit_selection(self):
        self.selection_changed.emit(self.selected_nodes())

    def select_nodes(self, nodes):
        self.updating = True
        self.clearSelection()
        for node in nodes:
            item = self._items.get(node.id) \
                or self._part_items.get(node.id)
            if item:
                item.setSelected(True)
        self.updating = False

    def _item_under(self, scene_pos):
        """Top-most item under *scene_pos* (handles included), or None
        for genuinely empty space. Uses the view transform so
        constant-size handles hit-test correctly."""
        views = self.views()
        if views:
            return self.itemAt(scene_pos, views[0].transform())
        hits = self.items(scene_pos)
        return hits[0] if hits else None

    def _isolated(self) -> bool:
        """True while a single object is shown alone — a 3D part
        silhouette or a 2D profile in edit mode."""
        return self._isolating() or bool(self._focus_shapes())

    # ------------------------------------------------------------ tools
    def mousePressEvent(self, event):
        if self.tool in (MEASURE, DIMENSION) \
                and event.button() == Qt.LeftButton:
            pt, _ = self.snap_feature(event.scenePos())
            if self._measure_a is None or self._measure_b is not None:
                self._measure_a = self._measure_cursor = pt   # (re)start
                self._measure_b = None
            else:
                self._measure_b = pt                          # finish
                self._emit_measure(self._measure_a, self._measure_b)
                if self.tool == DIMENSION:                    # keep it
                    self.model.add_dimension(
                        (self._measure_a.x(), self._measure_a.y()),
                        (self._measure_b.x(), self._measure_b.y()),
                        self.plane)
                    self._measure_a = self._measure_b = None
                    self._measure_cursor = None
            self.update()
            event.accept()
            return
        pos = self.snap(event.scenePos())
        if event.button() != Qt.LeftButton or self.tool == SELECT:
            if (self.tool == SELECT and event.button() == Qt.LeftButton
                    and self._isolated()
                    and self._item_under(event.scenePos()) is None):
                # while a part or profile is isolated, empty-space clicks
                # must not clear the selection — you deselect from the
                # object tree only. Clicks on the shape (or its resize
                # handles) still fall through to super() so it stays
                # editable and draggable.
                event.accept()
                return
            super().mousePressEvent(event)
            return
        if self.tool == LINE:
            self._draft_start = pos
            self._draft = self.addLine(pos.x(), pos.y(), pos.x(), pos.y(),
                                       _pen("#2176c7"))
        elif self.tool == RECT:
            self._draft_start = pos
            self._draft = self.addRect(QRectF(pos, pos), _pen("#2176c7"))
        elif self.tool == CIRCLE:
            self._draft_start = pos
            self._draft = self.addEllipse(QRectF(pos, pos),
                                          _pen("#2176c7"))
        elif self.tool == POLYGON:
            self._poly_points.append(pos)
            self._update_poly_draft(pos)
        elif self.tool == TEXT:
            node = self.model.add_node(
                "text", dict(x=pos.x(), y=pos.y()))
            self.node_created.emit(node)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.tool in (MEASURE, DIMENSION):
            if self._measure_a is not None and self._measure_b is None:
                pt, _ = self.snap_feature(event.scenePos())
                self._measure_cursor = pt
                self._emit_measure(self._measure_a, pt)
                self.update()
            event.accept()
            return
        pos = self.snap(event.scenePos())
        if self._draft is not None and self._draft_start is not None:
            start = self._draft_start
            if self.tool == LINE:
                self._draft.setLine(start.x(), start.y(),
                                    pos.x(), pos.y())
                length = ((pos.x() - start.x()) ** 2 +
                          (pos.y() - start.y()) ** 2) ** 0.5
                self.measure_changed.emit(
                    f"length: {length:.1f} mm   "
                    f"Δ {pos.x() - start.x():.1f}, "
                    f"{pos.y() - start.y():.1f} mm")
            elif self.tool == RECT:
                rect = QRectF(start, pos).normalized()
                self._draft.setRect(rect)
                self.measure_changed.emit(
                    f"{rect.width():.1f} × {rect.height():.1f} mm")
            elif self.tool == CIRCLE:
                radius = ((pos.x() - start.x()) ** 2 +
                          (pos.y() - start.y()) ** 2) ** 0.5
                self._draft.setRect(start.x() - radius,
                                    start.y() - radius,
                                    2 * radius, 2 * radius)
                self.measure_changed.emit(
                    f"r = {radius:.1f} mm   Ø {2 * radius:.1f} mm")
            event.accept()
            return
        if self.tool == POLYGON and self._poly_points:
            self._update_poly_draft(pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._draft is None or self._draft_start is None:
            super().mouseReleaseEvent(event)
            if self._part_dirty and self.mouseGrabberItem() is None:
                self._part_dirty = False
                self.rebuild()
            return
        pos = self.snap(event.scenePos())
        start = self._draft_start
        self.removeItem(self._draft)
        self._draft = None
        self._draft_start = None
        node = None
        if self.tool == LINE and (pos - start).manhattanLength() > 0.5:
            node = self.model.add_node("line", dict(
                x1=start.x(), y1=start.y(), x2=pos.x(), y2=pos.y()))
        elif self.tool == RECT:
            rect = QRectF(start, pos).normalized()
            if rect.width() > 0.5 and rect.height() > 0.5:
                node = self.model.add_node("rect", dict(
                    x=rect.x(), y=rect.y(),
                    width=rect.width(), height=rect.height()))
        elif self.tool == CIRCLE:
            radius = ((pos.x() - start.x()) ** 2 +
                      (pos.y() - start.y()) ** 2) ** 0.5
            if radius > 0.5:
                node = self.model.add_node("circle", dict(
                    x=start.x(), y=start.y(), radius=radius))
        if node is not None:
            self.node_created.emit(node)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.tool == POLYGON and len(self._poly_points) >= 3:
            self.finish_polygon()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _update_poly_draft(self, cursor):
        if self._draft is not None:
            self.removeItem(self._draft)
        path = QPainterPath(self._poly_points[0])
        for point in self._poly_points[1:]:
            path.lineTo(point)
        path.lineTo(cursor)
        self._draft = self.addPath(path, _pen("#2176c7"))

    def finish_polygon(self):
        points = self._poly_points
        self._poly_points = []
        if self._draft is not None:
            self.removeItem(self._draft)
            self._draft = None
        if len(points) < 3:
            return
        origin = points[0]
        node = self.model.add_node("polygon", dict(
            x=origin.x(), y=origin.y(),
            points=[[p.x() - origin.x(), p.y() - origin.y()]
                    for p in points]))
        self.node_created.emit(node)

    def cancel_tool(self):
        self._poly_points = []
        if self._draft is not None:
            self.removeItem(self._draft)
            self._draft = None
        self._draft_start = None
        self.clear_measure()

    def delete_selection(self):
        for node in self.selected_nodes():
            self.model.remove_node(node)


# ------------------------------------------------------------------- view

class SketchView(QGraphicsView):
    """Y-up graphics view with grid, pan and zoom."""

    cursor_moved = pyqtSignal(QPointF)
    clipboard_op = pyqtSignal(str)          # "cut" | "copy" | "paste"
    zoom_changed = pyqtSignal(float)        # pixels per mm
    step_object = pyqtSignal(int)           # +1 next / -1 previous

    def __init__(self, scene: SketchScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(4, -4)                     # Y up, sensible start zoom
        self.centerOn(30, 20)

    def px_per_mm(self) -> float:
        return abs(self.transform().m11())

    # ------------------------------------------------ middle-button pan
    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._pan_last = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, "_pan_last", None) is not None:
            delta = event.pos() - self._pan_last
            self._pan_last = event.pos()
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.value() - delta.x())
            v.setValue(v.value() - delta.y())
            event.accept()
            return
        self.cursor_moved.emit(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and \
                getattr(self, "_pan_last", None) is not None:
            self._pan_last = None
            self.setCursor(Qt.CrossCursor if self.scene().tool != SELECT
                           else Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_tool(self, tool):
        scene = self.scene()
        if tool not in (MEASURE, DIMENSION):
            scene.clear_measure()
        scene.tool = tool
        if tool == SELECT:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        scene = self.scene()
        if not scene.show_grid:
            return
        from .style import tokens
        t = tokens()
        g = scene.grid_size
        if g * self.transform().m11() < 4:
            g *= 5                              # keep the grid readable
        minor = QPen(QColor(t["border"]))
        minor.setCosmetic(True)
        major = QPen(QColor(t["border"]).darker(115))
        major.setCosmetic(True)
        left = int(rect.left() / g) - 1
        right = int(rect.right() / g) + 1
        bottom = int(rect.top() / g) - 1
        top = int(rect.bottom() / g) + 1
        for i in range(left, right + 1):
            painter.setPen(major if i % 5 == 0 else minor)
            painter.drawLine(QPointF(i * g, rect.top()),
                             QPointF(i * g, rect.bottom()))
        for j in range(bottom, top + 1):
            painter.setPen(major if j % 5 == 0 else minor)
            painter.drawLine(QPointF(rect.left(), j * g),
                             QPointF(rect.right(), j * g))
        axis = QPen(QColor(t["gutter"]))
        axis.setCosmetic(True)
        axis.setWidthF(1.4)
        painter.setPen(axis)
        painter.drawLine(QPointF(rect.left(), 0),
                         QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()),
                         QPointF(0, rect.bottom()))

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        from .style import tokens
        t = tokens()
        painter.save()
        painter.resetTransform()
        color = QColor(t["gutter"])
        painter.setPen(QPen(color, 1.4))
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        # axis letters for the active plane (X/Y/Z)
        (ai, bi), _keys = PLANES[self.scene().plane]
        h_axis, v_axis = "XYZ"[ai], "XYZ"[bi]
        w, h = self.viewport().width(), self.viewport().height()
        painter.drawText(w - 46, h - 12, f"{h_axis} →")
        painter.drawText(10, 34, f"{v_axis}")
        painter.drawText(8, 46, "↑")

        # scale bar (everything is millimetres)
        ppm = self.px_per_mm()
        bar_mm = None
        for k in range(-3, 6):
            for m in (1, 2, 5):
                length = m * 10 ** k
                if 60 <= length * ppm <= 170:
                    bar_mm = length
                    break
            if bar_mm:
                break
        if bar_mm:
            px = bar_mm * ppm
            x0, y0 = 14, h - 16
            painter.setPen(QPen(QColor(t["text"]), 1.6))
            painter.drawLine(x0, y0, int(x0 + px), y0)
            painter.drawLine(x0, y0 - 5, x0, y0 + 5)
            painter.drawLine(int(x0 + px), y0 - 5, int(x0 + px),
                             y0 + 5)
            label = f"{bar_mm:g} mm"
            painter.setFont(font)
            painter.drawText(int(x0 + px / 2 - 20), y0 - 8, label)
        # measurement + dimension annotations, drawn in view space so
        # text and arrows keep a constant size at any zoom
        self._draw_placed_dims(painter)
        self._draw_auto_dims(painter)
        self._draw_measure(painter)
        painter.restore()

    # ----------------------------------------------------- dimensions
    def _dim_screen(self, painter, pa, pb, *, color, bg, text,
                    offset=0.0, dots=True):
        """Core dimension renderer in *view/pixel* space: an offset
        dimension line with extension lines, arrowheads and a value
        chip. ``pa``/``pb`` are the measured points (QPointF, px)."""
        from math import hypot
        vx, vy = pb.x() - pa.x(), pb.y() - pa.y()
        plen = hypot(vx, vy)
        if plen < 1e-6:
            return
        ux, uy = vx / plen, vy / plen           # along the line
        nx, ny = -uy, ux                         # perpendicular
        oa = QPointF(pa.x() + nx * offset, pa.y() + ny * offset)
        ob = QPointF(pb.x() + nx * offset, pb.y() + ny * offset)
        pen = QPen(color, 1.5)
        pen.setCosmetic(True)
        thin = QPen(color, 1.0)
        thin.setCosmetic(True)
        if abs(offset) > 0.5:                    # extension lines
            gx, gy = nx * 3, ny * 3              # small gap off geometry
            over = QPointF(nx * (offset + 4), ny * (offset + 4))
            painter.setPen(thin)
            painter.drawLine(QPointF(pa.x() + gx, pa.y() + gy),
                             QPointF(pa.x() + over.x(), pa.y() + over.y()))
            painter.drawLine(QPointF(pb.x() + gx, pb.y() + gy),
                             QPointF(pb.x() + over.x(), pb.y() + over.y()))
        painter.setPen(pen)
        painter.drawLine(oa, ob)
        painter.setBrush(QBrush(color))
        for tip, sgn in ((oa, 1.0), (ob, -1.0)):
            base = QPointF(tip.x() + sgn * ux * 9, tip.y() + sgn * uy * 9)
            painter.drawPolygon(QPolygonF([
                tip,
                QPointF(base.x() + nx * 4, base.y() + ny * 4),
                QPointF(base.x() - nx * 4, base.y() - ny * 4)]))
        if dots:
            for p in (pa, pb):
                painter.drawEllipse(p, 2.6, 2.6)
        mid = QPointF((oa.x() + ob.x()) / 2 + nx * 12,
                      (oa.y() + ob.y()) / 2 + ny * 12)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw, th = fm.horizontalAdvance(text), fm.height()
        chip = QRectF(mid.x() - tw / 2 - 5, mid.y() - th / 2 - 2,
                      tw + 10, th + 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(chip, 4, 4)
        painter.setPen(QPen(color, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawText(chip, Qt.AlignCenter, text)

    def _draw_dim(self, painter, a_scene, b_scene, *, color, bg,
                  text=None, offset=0.0, dots=True):
        """Dimension between two *scene* points (mm)."""
        from math import hypot
        if text is None:
            dist = hypot(a_scene.x() - b_scene.x(),
                         a_scene.y() - b_scene.y())
            text = _fmt_mm(dist)
        self._dim_screen(painter,
                         QPointF(self.mapFromScene(a_scene)),
                         QPointF(self.mapFromScene(b_scene)),
                         color=color, bg=bg, text=text,
                         offset=offset, dots=dots)

    def _draw_measure(self, painter):
        scene = self.scene()
        a = getattr(scene, "_measure_a", None)
        b = scene._measure_b if scene._measure_b is not None \
            else scene._measure_cursor
        if a is None or b is None:
            return
        from .style import tokens
        t = tokens()
        self._draw_dim(painter, a, b,
                       color=QColor(t["select"]), bg=QColor(t["card"]))

    # ------------------------------------------------- placed dimensions
    def _draw_placed_dims(self, painter):
        """Saved dimension annotations for the current plane."""
        scene = self.scene()
        dims = getattr(scene.model, "dimensions", [])
        if not dims:
            return
        from .style import tokens
        t = tokens()
        color, bg = QColor(t["gutter"]), QColor(t["card"])
        for d in dims:
            if d.get("plane") != scene.plane:
                continue
            self._draw_dim(painter,
                           QPointF(d["a"][0], d["a"][1]),
                           QPointF(d["b"][0], d["b"][1]),
                           color=color, bg=bg, dots=True)

    def _dimension_at(self, view_pos):
        """Index of the placed dimension whose line lies under *view_pos*
        (a viewport QPoint), or None."""
        scene = self.scene()
        p = QPointF(view_pos)
        best, best_d = None, FEATURE_SNAP_PX
        for i, d in enumerate(getattr(scene.model, "dimensions", [])):
            if d.get("plane") != scene.plane:
                continue
            pa = QPointF(self.mapFromScene(QPointF(d["a"][0], d["a"][1])))
            pb = QPointF(self.mapFromScene(QPointF(d["b"][0], d["b"][1])))
            dist = _point_seg_dist(p, pa, pb)
            if dist < best_d:
                best, best_d = i, dist
        return best

    def contextMenuEvent(self, event):
        model = self.scene().model
        dims = getattr(model, "dimensions", [])
        if not dims:
            super().contextMenuEvent(event)
            return
        from PyQt5.QtWidgets import QMenu
        menu = QMenu(self)
        idx = self._dimension_at(event.pos())
        if idx is not None:
            menu.addAction("Delete dimension",
                           lambda: model.remove_dimension(idx))
        menu.addAction("Clear all dimensions", model.clear_dimensions)
        menu.exec_(event.globalPos())

    # ---------------------------------------------- auto size on select
    def _draw_auto_dims(self, painter):
        """When shapes are selected, annotate each one's own size — the
        way a part is dimensioned on a 2D drawing."""
        scene = self.scene()
        if not getattr(scene, "show_dims", True) or scene.tool != SELECT:
            return
        from .style import tokens
        t = tokens()
        color, bg = QColor(t["gutter"]), QColor(t["card"])
        for item in scene.selectedItems():
            if isinstance(item, (ShapeItem, PartItem)):
                self._auto_dim_item(painter, item, color, bg)

    def _auto_dim_item(self, painter, item, color, bg):
        if isinstance(item, CircleShapeItem):        # ⌀ across the centre
            c = item.mapToScene(item.rect().center())
            r = abs(item.rect().width()) / 2.0
            self._draw_dim(painter,
                           QPointF(c.x() - r, c.y()),
                           QPointF(c.x() + r, c.y()),
                           color=color, bg=bg, dots=False,
                           text="⌀ " + _fmt_mm(2 * r))
            return
        if isinstance(item, LineShapeItem):          # length beside it
            ln = item.line()
            self._draw_dim(painter, item.mapToScene(ln.p1()),
                           item.mapToScene(ln.p2()),
                           color=color, bg=bg, dots=False, offset=18)
            return
        r = item.sceneBoundingRect()                 # bounding W × H
        if r.width() < 1e-6 or r.height() < 1e-6:
            return
        pts = [QPointF(self.mapFromScene(c)) for c in
               (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight())]
        xs = [p.x() for p in pts]
        ys = [p.y() for p in pts]
        sl, sr, stop, sbot = min(xs), max(xs), min(ys), max(ys)
        # width below the box, height on the right (screen space)
        self._dim_screen(painter, QPointF(sl, sbot), QPointF(sr, sbot),
                         color=color, bg=bg, text=_fmt_mm(r.width()),
                         offset=22, dots=False)
        self._dim_screen(painter, QPointF(sr, sbot), QPointF(sr, stop),
                         color=color, bg=bg, text=_fmt_mm(r.height()),
                         offset=22, dots=False)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom(factor)

    def zoom(self, factor):
        current = abs(self.transform().m11())
        if 0.05 < current * factor < 400:
            self.scale(factor, factor)
        self.zoom_changed.emit(self.px_per_mm())

    def zoom_reset(self):
        self.resetTransform()
        self.scale(4, -4)
        self.centerOn(30, 20)
        self.zoom_changed.emit(self.px_per_mm())

    def _fit_rect(self, rect):
        if rect.isNull() or rect.width() < 1e-6:
            return
        rect = rect.adjusted(-rect.width() * 0.08,
                             -rect.height() * 0.08,
                             rect.width() * 0.08,
                             rect.height() * 0.08)
        scale = min(self.viewport().width() / rect.width(),
                    self.viewport().height() / rect.height())
        scale = max(min(scale, 400.0), 0.05)
        self.resetTransform()
        self.scale(scale, -scale)
        self.centerOn(rect.center())
        self.zoom_changed.emit(self.px_per_mm())

    def frame_rect(self, rect):
        """Fit a specific scene rectangle (used when a profile opens
        for editing)."""
        self._fit_rect(rect)

    def fit_content(self):
        """Fit everything drawn in the sketch (Ctrl+Shift+F)."""
        self._fit_rect(self.scene().itemsBoundingRect())

    def zoom_selection(self):
        """Fit the selected objects."""
        items = self.scene().selectedItems()
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        self._fit_rect(rect)

    def event(self, e):
        from PyQt5.QtCore import QEvent
        if e.type() == QEvent.KeyPress and \
                e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            self.step_object.emit(1 if e.key() == Qt.Key_Tab else -1)
            return True
        return super().event(e)

    def keyPressEvent(self, event):
        from PyQt5.QtGui import QKeySequence
        scene = self.scene()
        if event.key() == Qt.Key_Q:
            self.step_object.emit(-1)         # Q: up / previous
        elif event.key() == Qt.Key_A:
            self.step_object.emit(1)          # A: down / next
        elif event.matches(QKeySequence.Copy):
            self.clipboard_op.emit("copy")
        elif event.matches(QKeySequence.Cut):
            self.clipboard_op.emit("cut")
        elif event.matches(QKeySequence.Paste):
            self.clipboard_op.emit("paste")
        elif event.key() == Qt.Key_Escape:
            scene.cancel_tool()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter) and \
                scene.tool == POLYGON:
            scene.finish_polygon()
        elif event.key() == Qt.Key_Delete:
            scene.delete_selection()
        else:
            super().keyPressEvent(event)

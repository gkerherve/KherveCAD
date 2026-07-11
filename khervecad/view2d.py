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
from .model import SHAPE_2D, DocumentModel

SELECT, LINE, RECT, CIRCLE, POLYGON, TEXT = (
    "select", "line", "rect", "circle", "polygon", "text")

_SHAPE_PEN_W = 1.6
HANDLE_SIZE = 9.0


def _pen(color: str, width=_SHAPE_PEN_W) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCosmetic(True)
    return pen


class HandleItem(QGraphicsRectItem):
    """Square resize handle, constant size on screen."""

    def __init__(self, role: str, parent):
        size = HANDLE_SIZE
        super().__init__(-size / 2, -size / 2, size, size, parent)
        self.role = role
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(_pen("#2176c7", 1.2))
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptedMouseButtons(Qt.LeftButton)

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        scene = self.scene()
        pos = scene.snap(self.parentItem().mapToScene(
            self.mapToParent(event.pos())))
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
            for role, pos in self.handle_spec():
                handle = HandleItem(role, self)
                handle.setPos(pos)
                self.handles.append(handle)

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


# ------------------------------------------------------------------ scene

class SketchScene(QGraphicsScene):
    """All visible 2D shapes of the document + the drawing tools."""

    selection_changed = pyqtSignal(list)      # list of CadNode
    node_created = pyqtSignal(object)         # CadNode

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(-2000, -2000, 4000, 4000, parent)
        self.model = model
        self.tool = SELECT
        self.grid_size = 5.0
        self.snap_enabled = True
        self.show_grid = True
        self.updating = False
        self._items = {}                       # node id -> item
        self._draft = None                     # item being drawn
        self._draft_start = None
        self._poly_points = []
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._node_changed)
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

    def rebuild(self):
        self.updating = True
        selected = {n.id for n in self.selected_nodes()}
        for item in self._items.values():
            self.removeItem(item)
        self._items.clear()
        for node in self.model.root.walk():
            if node.category == SHAPE_2D and self._branch_visible(node):
                item = _ITEM_CLASSES[node.type](node, self)
                self.addItem(item)
                self._items[node.id] = item
                if node.id in selected:
                    item.setSelected(True)
        self.updating = False

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
        should_show = (node.category == SHAPE_2D
                       and self._branch_visible(node))
        item = self._items.get(node.id)
        if (item is not None) != should_show:
            self.rebuild()
        elif item is not None:
            self.updating = True
            item.apply_node()
            self.updating = False

    def push_move(self, item):
        self.updating = True
        item.push_pos()
        item.apply_node()
        self.updating = False

    def selected_nodes(self):
        return [item.node for item in self.selectedItems()
                if isinstance(item, ShapeItem)]

    def emit_selection(self):
        self.selection_changed.emit(self.selected_nodes())

    def select_nodes(self, nodes):
        self.updating = True
        self.clearSelection()
        for node in nodes:
            item = self._items.get(node.id)
            if item:
                item.setSelected(True)
        self.updating = False

    # ------------------------------------------------------------ tools
    def mousePressEvent(self, event):
        pos = self.snap(event.scenePos())
        if event.button() != Qt.LeftButton or self.tool == SELECT:
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
        pos = self.snap(event.scenePos())
        if self._draft is not None and self._draft_start is not None:
            start = self._draft_start
            if self.tool == LINE:
                self._draft.setLine(start.x(), start.y(),
                                    pos.x(), pos.y())
            elif self.tool == RECT:
                self._draft.setRect(QRectF(start, pos).normalized())
            elif self.tool == CIRCLE:
                radius = ((pos.x() - start.x()) ** 2 +
                          (pos.y() - start.y()) ** 2) ** 0.5
                self._draft.setRect(start.x() - radius,
                                    start.y() - radius,
                                    2 * radius, 2 * radius)
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

    def delete_selection(self):
        for node in self.selected_nodes():
            self.model.remove_node(node)


# ------------------------------------------------------------------- view

class SketchView(QGraphicsView):
    """Y-up graphics view with grid, pan and zoom."""

    cursor_moved = pyqtSignal(QPointF)
    clipboard_op = pyqtSignal(str)          # "cut" | "copy" | "paste"

    def __init__(self, scene: SketchScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(4, -4)                     # Y up, sensible start zoom
        self.centerOn(30, 20)

    def set_tool(self, tool):
        self.scene().tool = tool
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

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom(factor)

    def zoom(self, factor):
        current = abs(self.transform().m11())
        if 0.05 < current * factor < 400:
            self.scale(factor, factor)

    def zoom_reset(self):
        self.resetTransform()
        self.scale(4, -4)
        self.centerOn(30, 20)

    def mouseMoveEvent(self, event):
        self.cursor_moved.emit(self.mapToScene(event.pos()))
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        from PyQt5.QtGui import QKeySequence
        scene = self.scene()
        if event.matches(QKeySequence.Copy):
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

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

SELECT, LINE, RECT, CIRCLE, POLYGON, TEXT = (
    "select", "line", "rect", "circle", "polygon", "text")

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


def _produces_3d(node) -> bool:
    """True if the subtree makes solid geometry (an assemblable part)."""
    return any(n.category == SHAPE_3D
               or n.type in ("linear_extrude", "rotate_extrude")
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
                handle = HandleItem(spec["role"], self)
                handle.setPos(spec["tip"])
                self.handles.append(handle)

    def handle_dragged(self, role, scene_pos):
        spec = next((d for d in self._dims if d["role"] == role), None)
        if spec is None:
            return
        ax, ay = spec["axis"]
        denom = ax * ax + ay * ay
        if denom < 1e-12:
            return
        # project the cursor onto the handle's axis line -> local length
        s = ((scene_pos.x() - spec["anchor"].x()) * ax
             + (scene_pos.y() - spec["anchor"].y()) * ay) / denom
        value = max(s * spec["factor"], spec["minval"])
        self.node.params[spec["param"]] = round(value, 4)
        self._scene.model.node_changed.emit(self.node)
        # keep the grabbed handle under the cursor for live feedback
        new_s = value / spec["factor"]
        for handle in self.handles:
            if handle.role == role:
                handle.setPos(QPointF(spec["anchor"].x() + new_s * ax,
                                      spec["anchor"].y() + new_s * ay))

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
        self.grid_size = 5.0
        self.snap_enabled = True
        self.show_grid = True
        self.updating = False
        self._items = {}                       # node id -> shape item
        self._part_items = {}                  # node id -> part item
        self._draft = None                     # item being drawn
        self._draft_start = None
        self._poly_points = []
        self._part_dirty = False
        self._highlight_ids = set()            # selected nodes
        self._highlight_items = []
        model.structure_changed.connect(self.rebuild)
        model.node_changed.connect(self._node_changed)
        self.rebuild()

    def set_plane(self, plane: str):
        if plane in PLANES and plane != self.plane:
            self.plane = plane
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

    # ------------------------------------------------------- highlight
    def set_highlight(self, nodes):
        """Select these objects: a 3D part isolates in the 2D view
        (only it is shown, in its real projected shape); 2D sketch
        shapes just get selected in place."""
        self._highlight_ids = {n.id for n in nodes}
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
            self.model.root, {node.id}, detail=14)
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
                factor=factor, minval=0.1,
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
            cx = px + (0.0 if center else w / 2)
            cy = py + (0.0 if center else d / 2)
            cz = pz + (0.0 if center else hh / 2)
            add("width", "width", (cx, cy, cz), (1, 0, 0), w / 2, 2.0)
            add("depth", "depth", (cx, cy, cz), (0, 1, 0), d / 2, 2.0)
            add("height", "height", (cx, cy, cz), (0, 0, 1), hh / 2, 2.0)
        return out

    def _make_part_item(self, node):
        from . import mesh as mesh_mod
        tris = mesh_mod.tessellate(node, self.env_for(node))
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
        """A part outline was dropped: bake the move into a translate
        node so the assembly is plain, editable tree structure."""
        if abs(delta.x()) < 1e-9 and abs(delta.y()) < 1e-9:
            return
        _axes, (kx, ky) = PLANES[self.plane]
        if node.type == "translate":
            env = self.env_for(node)
            node.params[kx] = round(
                expr.resolve(node.params.get(kx), env) + delta.x(), 4)
            node.params[ky] = round(
                expr.resolve(node.params.get(ky), env) + delta.y(), 4)
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
        painter.restore()

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

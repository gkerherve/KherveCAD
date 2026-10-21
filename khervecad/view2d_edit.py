"""Editing what is selected in the tree, directly in the 2D view
(2026-10-19, the user: "when we press on an item in the tree — polygon,
linear extrude, rotate — this is what we should be able to change in the
2D view").

- **Shapes through their transforms.** A 2D shape inside a Rotate (or a
  Move, Scale, Mirror, Group...) is drawn as that transform places it —
  a rectangle under rotate(30) shows turned, as in the 3D view — by
  hanging its item under a `Frame` whose transform is the ancestors'
  matrix (`SketchScene._world_matrix`). The item keeps its own params
  as coordinates, so moving it or dragging its points still writes the
  shape's own x / y / points; HandleItem maps the cursor into the frame.
- **Rotate.** Selecting a Rotate shows a dial at its pivot: drag the
  knob and the contents turn (about Z in the Top plane, Y in Front, X in
  Side), 5° steps while snapping is on.
- **Linear extrude.** Its height gets a size handle like a cube's
  (`extrude_dims`), in the Front or Side plane, which the selection
  jumps to.

While a handle is held, an edit of a container (the rotate, the
extrude) must not rebuild the scene — that would delete the handle under
the cursor — so `live_update` re-places the frames and re-draws the
selected silhouette in place, and the rebuild follows the release.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainterPath, QPen, QTransform
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem, QGraphicsPathItem)

#: the dial's radius on screen (pixels) and its knob
DIAL_PX = 46.0
KNOB_PX = 7.0
DIAL = "#e07b39"
#: rotation axis edited in each plane, and its sign as seen on screen
#: (positive screen angle = counter-clockwise)
ROTATE_AXIS = {"Top (XY)": ("z", 1.0), "Front (XZ)": ("y", -1.0),
               "Side (YZ)": ("x", 1.0)}
SNAP_DEG = 5.0


class Frame(QGraphicsItem):
    """An invisible parent placing its children through a transform."""

    def boundingRect(self):
        return QRectF()

    def paint(self, painter, option, widget=None):
        pass


def on_view_plane(scene, node) -> bool:
    """Does 2D shape *node* lie in the plane the view looks at — its
    flat side square on (a Top sketch in Top, a Front sketch in Front)?"""
    from .view2d import PLANES
    (ai, bi), _keys = PLANES.get(scene.plane, PLANES["Top (XY)"])
    m = scene._world_matrix(node)
    return abs(m[ai][2]) < 1e-6 and abs(m[bi][2]) < 1e-6 and \
        abs(m[ai][0] * m[bi][1] - m[ai][1] * m[bi][0]) > 1e-9


def frame_transform(scene, node):
    """The QTransform of *node*'s ancestors onto the view's plane, or
    None when it is the identity (no frame needed)."""
    from .view2d import PLANES
    (ai, bi), _keys = PLANES.get(scene.plane, PLANES["Top (XY)"])
    m = scene._world_matrix(node)
    t = QTransform(m[ai][0], m[bi][0], m[ai][1], m[bi][1], m[ai][3],
                   m[bi][3])
    return None if t.isIdentity() else t


def add_shape(scene, item, node):
    """Put a sketch shape *item* in *scene*, inside a Frame when its
    ancestors move, turn or scale it."""
    t = frame_transform(scene, node)
    if t is None:
        scene.addItem(item)
        return
    frame = Frame()
    frame.setTransform(t)
    scene.addItem(frame)
    item.setParentItem(frame)
    scene._frames.append((frame, node))


def clear(scene):
    """Remove the frames (with their shapes) and the dial."""
    for frame, _node in getattr(scene, "_frames", []):
        if frame.scene() is scene:
            scene.removeItem(frame)
    scene._frames = []
    for item in getattr(scene, "_gizmos", []):
        if item.scene() is scene:
            scene.removeItem(item)
    scene._gizmos = []


def in_frame_coords(item, scene_pos):
    """*scene_pos* in the coordinates a shape's params use (its frame's,
    or the scene's when it has none)."""
    frame = item.parentItem() if item is not None else None
    if isinstance(frame, Frame):
        return frame.mapFromScene(scene_pos)
    return scene_pos


# ------------------------------------------- only the selection's edit
#: containers whose drag moves them: they carry their own x / y / z
MOVES = ("translate", "union", "component", "reference")
#: what to say when a locked container's contents are clicked
WHY = {"rotate": "Rotate selected: turn it with the dial's knob (drag "
                 "its centre to move it).",
       "scale": "Scale selected: set its factors in Properties.",
       "mirror": "Mirror selected: set its plane in Properties.",
       "linear_extrude": "Linear extrude selected: drag its height "
                         "handle in the Front or Side view."}


def _selected_container(scene, node):
    """The nearest SELECTED ancestor of *node* (not *node* itself)."""
    stop = scene.scope_root()
    probe = node.parent
    while probe is not None and probe is not stop:
        if probe.id in scene._highlight_ids:
            return probe
        probe = probe.parent
    return None


def lock_contents(scene):
    """Shapes inside a selected container are shown, tinted, but cannot
    be selected, moved or resized — the container's own edit is the
    only one (a Move drags, a Rotate turns). One `ContainerArea` per
    container takes the clicks."""
    groups = {}
    for node_id, item in list(scene._items.items()):
        node = getattr(item, "node", None)
        if node is None or node.id in scene._highlight_ids:
            continue
        container = _selected_container(scene, node)
        if container is None:
            continue
        item.setSelected(False)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setFlag(QGraphicsItem.ItemIsMovable, False)
        item.setAcceptedMouseButtons(Qt.NoButton)
        groups.setdefault(container.id, (container, []))[1].append(item)
    for container, items in groups.values():
        area = ContainerArea(scene, container, items)
        scene.addItem(area)
        scene._gizmos.append(area)


class ContainerArea(QGraphicsPathItem):
    """The outline of what a selected container holds. A Move (or a
    Group / Object with its own position) is dragged by it; anything
    else only explains what to use."""

    def __init__(self, scene, container, items):
        super().__init__()
        self._scene = scene
        self.node = container
        self.items = items
        self.refresh()
        pen = QPen(QColor(DIAL), 1.4)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        fill = QColor(DIAL)
        fill.setAlpha(45)
        self.setBrush(QBrush(fill))
        self.setZValue(1e4)
        self.movable = container.type in MOVES
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setCursor(Qt.SizeAllCursor if self.movable
                       else Qt.ArrowCursor)
        self.setToolTip("Drag to move it" if self.movable else
                        WHY.get(container.type, "Edit it in Properties"))
        self._grab = None

    def refresh(self):
        """Outline the contents as they stand now."""
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        for item in self.items:
            path = path.united(item.sceneTransform().map(item.shape()))
        self.setPos(0, 0)
        self.setPath(path)

    def mousePressEvent(self, event):
        if not self.movable:
            self._scene.status.emit(WHY.get(
                self.node.type, f"{self.node.name} selected: edit it in "
                "Properties — select a shape inside to edit the shape."))
            event.accept()
            return
        self._grab = (self._scene.snap(event.scenePos()),
                      [float(self.node.params.get(k, 0.0) or 0.0)
                       for k in ("x", "y", "z")])
        event.accept()

    def mouseMoveEvent(self, event):
        if self._grab is None:
            return
        start, origin = self._grab
        delta = self._scene.snap(event.scenePos()) - start
        local = self._scene._local_move(self.node, delta)
        values = [round(o + d, 4) for o, d in zip(origin, local)]
        if [self.node.params.get(k) for k in ("x", "y", "z")] != values:
            self.node.params.update(x=values[0], y=values[1], z=values[2])
            self._scene.model.node_changed.emit(self.node)
        self.setPos(delta)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._grab = None
        end_live_edit(self._scene)
        event.accept()


# --------------------------------------------------------- live edits
def live_update(scene):
    """A container changed while a handle is held: re-place the frames
    and re-draw the selected silhouettes, without a rebuild."""
    for frame, node in scene._frames:
        t = frame_transform(scene, node)
        frame.setTransform(t if t is not None else QTransform())
    for node_id, item in list(scene._part_items.items()):
        node = scene.model.find(node_id)
        if node is None or not item.isSelected():
            continue
        fresh = scene._make_silhouette(node)
        if fresh is not None:
            item.setPath(fresh.path())
    grabbed = scene.mouseGrabberItem()
    for gizmo in scene._gizmos:
        if isinstance(gizmo, RotateDial):
            gizmo.place()
        elif isinstance(gizmo, ContainerArea) and gizmo is not grabbed:
            gizmo.refresh()                    # the dial turned it
    scene._part_dirty = True


def end_live_edit(scene):
    """After the release: rebuild on the next turn (never under the
    item still delivering the event)."""
    if getattr(scene, "_part_dirty", False):
        scene._part_dirty = False
        QTimer.singleShot(0, scene.rebuild)


# -------------------------------------------------------------- rotate
def add_gizmos(scene):
    """The dial for a single selected Rotate, in any plane."""
    ids = list(scene._highlight_ids)
    if len(ids) != 1:
        return
    node = scene.model.find(ids[0])
    if node is None or node.type != "rotate":
        return
    dial = RotateDial(scene, node)
    scene.addItem(dial)
    scene._gizmos.append(dial)


def _pivot_local(scene, node):
    from . import expr
    env = scene.env_for(node)
    return [expr.resolve(node.params.get(k, 0.0), env, 0.0)
            for k in ("px", "py", "pz")]


def _pivot(scene, node):
    """Where the rotate turns, on the sketch: its pivot (px, py, pz,
    the origin by default) through the transforms above it."""
    from . import mesh as mesh_mod
    from .view2d import PLANES
    (ai, bi), _keys = PLANES[scene.plane]
    w = mesh_mod.transform_point(scene._world_matrix(node),
                                 tuple(_pivot_local(scene, node)))
    return QPointF(w[ai], w[bi])


def _scene_to_pivot(scene, node, scene_pos):
    """The pivot (px, py, pz) whose sketch position is *scene_pos*:
    the plane's two axes solved through the transforms above the rotate,
    the third kept."""
    from .view2d import PLANES
    (ai, bi), _keys = PLANES[scene.plane]
    m = scene._world_matrix(node)
    local = _pivot_local(scene, node)
    # world_a = m[ai] . local + t: solve for local[ai], local[bi]
    rest_a = sum(m[ai][k] * local[k] for k in range(3)
                 if k not in (ai, bi)) + m[ai][3]
    rest_b = sum(m[bi][k] * local[k] for k in range(3)
                 if k not in (ai, bi)) + m[bi][3]
    a11, a12 = m[ai][ai], m[ai][bi]
    a21, a22 = m[bi][ai], m[bi][bi]
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-12:
        return local
    u, v = scene_pos.x() - rest_a, scene_pos.y() - rest_b
    local[ai] = (a22 * u - a12 * v) / det
    local[bi] = (-a21 * u + a11 * v) / det
    return local


class RotateDial(QGraphicsEllipseItem):
    """A ring at the rotate's pivot with a knob at its angle: drag the
    knob to turn the contents."""

    def __init__(self, scene, node):
        r = DIAL_PX
        super().__init__(-r, -r, 2 * r, 2 * r)
        self._scene = scene
        self.node = node
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        pen = QPen(QColor(DIAL), 1.6)
        pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.NoBrush))
        self.setZValue(1e5)
        self.setAcceptedMouseButtons(Qt.NoButton)   # only the knob grabs
        self.spoke = QGraphicsLineItem(self)
        self.spoke.setPen(QPen(QColor(DIAL), 1.2))
        self.knob = _Knob(self)
        self.centre = _PivotHandle(self)
        self.place()

    def axis(self):
        return ROTATE_AXIS[self._scene.plane]

    def value(self):
        from . import expr
        key, _sign = self.axis()
        return expr.resolve(self.node.params.get(key, 0.0),
                            self._scene.env_for(self.node), 0.0)

    def place(self):
        """Pivot and knob from the node as it stands."""
        self.setPos(_pivot(self._scene, self.node))
        _key, sign = self.axis()
        a = math.radians(self.value() * sign)
        # the item ignores the view's flip: local y runs DOWN the screen
        tip = QPointF(DIAL_PX * math.cos(a), -DIAL_PX * math.sin(a))
        self.knob.setPos(tip)
        self.spoke.setLine(0, 0, tip.x(), tip.y())
        self.setToolTip(f"Rotate {self.axis()[0].upper()}: "
                        f"{self.value():g}°")


class _PivotHandle(QGraphicsEllipseItem):
    """The dial's centre. Dragged, it MOVES the rotated part: a Move
    (translate) is put above the Rotate — or the one already there is
    used — so the part and its rotation point travel together (the
    user's own picture of it, 2026-10-19). Shift-dragged, it moves the
    rotation point alone (the rotate's pivot), and the part then turns
    about the new point."""

    def __init__(self, dial):
        r = KNOB_PX - 1.0
        super().__init__(-r, -r, 2 * r, 2 * r, dial)
        self.dial = dial
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor(DIAL), 2.0))
        self.setCursor(Qt.SizeAllCursor)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setToolTip("Drag to move the rotated part (a Move is added "
                        "above the Rotate); Shift+drag moves only the "
                        "rotation point")
        self._move = None

    def mousePressEvent(self, event):
        scene = self.dial._scene
        self._move = None
        self._moving = not (event.modifiers() & Qt.ShiftModifier)
        self._start = scene.snap(event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event):
        scene = self.dial._scene
        pos = scene.snap(event.scenePos())
        if self._moving and self._move is None:
            # made on the first MOVE, not the press: by now this handle
            # is the mouse grabber, so the rebuild the new node asks for
            # waits for the release instead of deleting the handle
            self._move = _move_above(scene, self.dial.node)
            self._origin = [float(self._move.params.get(k, 0.0) or 0.0)
                            for k in ("x", "y", "z")]
        if self._move is not None:
            d = pos - self._start
            dx, dy, dz = _scene_delta_to_local(scene, self._move,
                                               d.x(), d.y())
            values = [round(o + v, 4) for o, v in
                      zip(self._origin, (dx, dy, dz))]
            if [self._move.params.get(k) for k in ("x", "y", "z")] != values:
                self._move.params.update(x=values[0], y=values[1],
                                         z=values[2])
                scene.model.node_changed.emit(self._move)
        else:
            node = self.dial.node
            px, py, pz = (round(v, 4) for v in
                          _scene_to_pivot(scene, node, pos))
            if [node.params.get(k, 0.0) for k in ("px", "py", "pz")] != \
                    [px, py, pz]:
                node.params.update(px=px, py=py, pz=pz)
                scene.model.node_changed.emit(node)
        self.dial.place()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._move = None
        self._moving = False
        end_live_edit(self.dial._scene)
        event.accept()


def _move_above(scene, rotate):
    """The Move (translate) holding just this Rotate — made if there is
    none, as the tree's own Move & transform ▸ Translate would."""
    parent = rotate.parent
    if parent is not None and parent.type == "translate" \
            and len(parent.children) == 1:
        return parent
    return scene.model.wrap_nodes([rotate], "translate")


def _scene_delta_to_local(scene, node, dx, dy):
    """A sketch move (dx, dy) as the change of *node*'s own x / y / z:
    through the inverse of the transforms ABOVE it (its own offset lives
    in its parent's frame)."""
    from .view2d import PLANES
    (ai, bi), _keys = PLANES[scene.plane]
    m = scene._world_matrix(node)
    a11, a12 = m[ai][ai], m[ai][bi]
    a21, a22 = m[bi][ai], m[bi][bi]
    det = a11 * a22 - a12 * a21
    out = [0.0, 0.0, 0.0]
    if abs(det) < 1e-12:
        return out
    out[ai] = (a22 * dx - a12 * dy) / det
    out[bi] = (-a21 * dx + a11 * dy) / det
    return out


class _Knob(QGraphicsEllipseItem):
    def __init__(self, dial):
        r = KNOB_PX
        super().__init__(-r, -r, 2 * r, 2 * r, dial)
        self.dial = dial
        self.setBrush(QBrush(QColor(DIAL)))
        self.setPen(QPen(QColor("#ffffff"), 1.4))
        self.setCursor(Qt.OpenHandCursor)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setToolTip("Drag to rotate")
        self._grab = None

    def _cursor_angle(self, scene_pos):
        c = self.dial.pos()                  # the pivot, in scene (Y up)
        return math.degrees(math.atan2(scene_pos.y() - c.y(),
                                       scene_pos.x() - c.x()))

    def mousePressEvent(self, event):
        self._grab = (self._cursor_angle(event.scenePos()),
                      self.dial.value())
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event):
        if self._grab is None:
            return
        start_angle, start_value = self._grab
        delta = self._cursor_angle(event.scenePos()) - start_angle
        delta = (delta + 180.0) % 360.0 - 180.0
        key, sign = self.dial.axis()
        value = start_value + delta * sign
        scene = self.dial._scene
        if scene.snap_enabled and not (event.modifiers() & Qt.ShiftModifier):
            value = round(value / SNAP_DEG) * SNAP_DEG
        value = round((value + 180.0) % 360.0 - 180.0, 3)
        node = self.dial.node
        if node.params.get(key) != value:
            node.params[key] = value
            scene.model.node_changed.emit(node)
        self.dial.place()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._grab = None
        self.setCursor(Qt.OpenHandCursor)
        end_live_edit(self.dial._scene)
        event.accept()


# ------------------------------------------------------------ extrude
def extrude_dims(scene, node, plane, add, val, direction):
    """The height handle of a Linear extrude, through `_dim_handles`'
    own helpers (*add*, *val*, *direction*)."""
    from . import mesh as mesh_mod
    h = val("height", 10.0)
    z0 = -h / 2.0 if node.params.get("center") else 0.0
    cx = cy = 0.0
    try:
        pts = [p for o in mesh_mod._children_outlines(
            node, scene.env_for(node)) for p in o]
    except Exception:                            # noqa: BLE001
        pts = []
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    add("height", "height", (cx, cy, z0), (0, 0, 1), h, 1.0)

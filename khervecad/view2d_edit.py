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
from PyQt5.QtGui import QBrush, QColor, QPen, QTransform
from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem,
                             QGraphicsLineItem)

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


def frame_transform(scene, node):
    """The Top-plane QTransform of *node*'s ancestors, or None when it
    is the identity (no frame needed)."""
    m = scene._world_matrix(node)
    t = QTransform(m[0][0], m[1][0], m[0][1], m[1][1], m[0][3], m[1][3])
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


def selected_under(scene, node, selected):
    """Is *node* selected, or inside a selected container?"""
    stop = scene.scope_root()
    probe = node
    while probe is not None and probe is not stop:
        if probe.id in selected:
            return True
        probe = probe.parent
    return False


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
    for gizmo in scene._gizmos:
        if isinstance(gizmo, RotateDial):
            gizmo.place()
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


def _pivot(scene, node):
    from . import mesh as mesh_mod
    from .view2d import PLANES
    (ai, bi), _keys = PLANES[scene.plane]
    w = mesh_mod.transform_point(scene._world_matrix(node), (0, 0, 0))
    return QPointF(w[ai], w[bi])


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

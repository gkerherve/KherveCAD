"""The Blueprint window's tools: snapping onto a view's geometry, and
the click sequences that place dimensions, notes, symbols, sketch lines
and detail views.

A tool receives scene positions from the sheet view (`press`, `move`,
`release`) and builds a PREVIEW of what it is making — the real item,
half transparent — so what the user aims is what lands. Finishing
hands the item's data to the window (`add_note`), which makes it one
undo step and saves it into the document.

Snapping works in the view's local frame (sheet mm): endpoints,
midpoints, circle centres and quadrants, nearest point on an edge, and
round edges found by `drawing.find_circles`. A cell grid keeps it quick
on a threaded part with tens of thousands of lines.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsItem

from . import blueprint_items as bi

SNAP_NAMES = {"end": "Endpoint", "mid": "Midpoint", "centre": "Centre",
              "quad": "Quadrant", "edge": "On edge"}


class ViewSnap:
    """Snap targets of one view, in its local frame."""

    CELL = 4.0

    def __init__(self, view):
        self.view = view
        self.points = {}
        self.cells = {}
        self.segs = []
        self.circles = []
        to = view.to_local
        for key in ("visible", "hidden"):
            for a, b in view.lines.get(key, ()):
                self._seg(to(a), to(b))
        for outline in view.outlines:
            pts = [to(p) for p in outline]
            for a, b in zip(pts, pts[1:] + pts[:1]):
                self._seg(a, b)
        for c in view.circles:
            C = to(c["centre"])
            R = c["r"] * view.scale_
            self.circles.append((C, R, c))
            self._point(C, "centre")
            if c.get("closed"):
                for dx, dy in ((R, 0), (-R, 0), (0, R), (0, -R)):
                    self._point((C[0] + dx, C[1] + dy), "quad")

    def _key(self, x, y):
        return int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))

    def _point(self, p, kind):
        self.points.setdefault(self._key(*p), []).append((p[0], p[1], kind))

    def _seg(self, a, b):
        index = len(self.segs)
        self.segs.append((a, b))
        self._point(a, "end")
        self._point(b, "end")
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length > 3.0:
            self._point(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), "mid")
        steps = max(1, int(length / self.CELL) + 1)
        seen = set()
        for i in range(steps + 1):
            t = i / steps
            key = self._key(a[0] + (b[0] - a[0]) * t,
                            a[1] + (b[1] - a[1]) * t)
            if key not in seen:
                seen.add(key)
                self.cells.setdefault(key, []).append(index)

    def _near(self, table, x, y, tol):
        reach = int(math.ceil(tol / self.CELL))
        cx, cy = self._key(x, y)
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cy - reach, cy + reach + 1):
                yield from table.get((i, j), ())

    def point(self, x, y, tol):
        """The nearest snap point within *tol*: (x, y, kind) or None.
        A centre wins over an endpoint at the same distance."""
        best, best_d = None, tol
        order = {"centre": 0, "end": 1, "quad": 2, "mid": 3}
        for px, py, kind in self._near(self.points, x, y, tol):
            d = math.hypot(px - x, py - y) + order.get(kind, 4) * 1e-6
            if d <= best_d:
                best, best_d = (px, py, kind), d
        return best

    def segment(self, x, y, tol):
        """The nearest edge within *tol*: (a, b, foot) or None."""
        best, best_d = None, tol
        for index in set(self._near(self.cells, x, y, tol)):
            a, b = self.segs[index]
            foot = _foot(a, b, (x, y))
            d = math.hypot(foot[0] - x, foot[1] - y)
            if d <= best_d:
                best, best_d = (a, b, foot), d
        return best

    def circle(self, x, y, tol):
        """The round edge under (x, y): the circle dict, or None."""
        best, best_d = None, tol
        for C, R, c in self.circles:
            d = abs(math.hypot(x - C[0], y - C[1]) - R)
            if d <= best_d:
                best, best_d = c, d
        return best

    def on_rim(self, p, c, slack=0.5):
        """True when the snap point *p* lies on the round edge *c* — the
        vertex of its polygon, which snaps as an endpoint. A finely
        faceted circle has vertices closer together than the click
        tolerance, so without this its rim never reads as a rim."""
        for C, R, other in self.circles:
            if other is c:
                return abs(math.hypot(p[0] - C[0], p[1] - C[1]) - R) <= slack
        return False


def _foot(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    if n < 1e-18:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return a[0] + dx * t, a[1] + dy * t


class SnapMarker(QGraphicsItem):
    """The glyph under the cursor showing what a click would catch:
    square endpoint, triangle midpoint, circle centre, diamond quadrant,
    cross on an edge. Fixed size on screen."""

    transient = True

    def __init__(self):
        super().__init__()
        self.kind = None
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setZValue(1000)
        self.hide()

    def show_at(self, pos, kind):
        self.kind = kind
        self.setPos(pos)
        self.setVisible(kind is not None)
        self.update()

    def boundingRect(self):
        return QRectF(-9, -9, 18, 18)

    def paint(self, painter, option, widget=None):
        pen = QPen(QColor("#e8741e"), 2.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        k = self.kind
        if k == "end":
            painter.drawRect(QRectF(-5, -5, 10, 10))
        elif k == "mid":
            painter.drawPolygon(QPointF(0, -6), QPointF(6, 5),
                                QPointF(-6, 5))
        elif k == "centre":
            painter.drawEllipse(QPointF(0, 0), 5.5, 5.5)
            painter.drawLine(QPointF(-3, 0), QPointF(3, 0))
            painter.drawLine(QPointF(0, -3), QPointF(0, 3))
        elif k == "quad":
            painter.drawPolygon(QPointF(0, -6), QPointF(6, 0), QPointF(0, 6),
                                QPointF(-6, 0))
        else:
            painter.drawLine(QPointF(-5, -5), QPointF(5, 5))
            painter.drawLine(QPointF(-5, 5), QPointF(5, -5))


# ── tools ──────────────────────────────────────────────────────────

class Tool:
    """A click sequence. *win* is the Blueprint window (scene, sheet
    view, status line, `add_note`, `ask_text`)."""

    key = "select"
    hint = "Click to select; drag views and labels to move them."

    def __init__(self, win):
        self.win = win
        self.scene = win.scene
        self.preview = None
        self.reset()

    def reset(self):
        self.clear_preview()

    def activate(self):
        self.win.status(self.hint)

    def deactivate(self):
        self.reset()
        self.scene.marker.show_at(QPointF(), None)

    def press(self, pos, event=None):
        pass

    def move(self, pos, event=None):
        self.hover(pos)

    def release(self, pos, event=None):
        pass

    def cancel(self):
        """Esc: drop what is half made; True if there was something."""
        busy = self.preview is not None
        self.reset()
        return busy

    # -- helpers
    def tol(self):
        return self.win.sheet.px_to_mm(9.0)

    def locate(self, pos, want_view=True):
        """What the cursor is on: (view, local (x, y), snap kind). With
        no view under it: (None, sheet (x, y), None)."""
        view = self.scene.view_at(pos) if want_view else None
        if view is None:
            return None, (pos.x(), pos.y()), None
        q = view.mapFromScene(pos)
        snap = self.scene.snapper(view)
        hit = snap.point(q.x(), q.y(), self.tol())
        if hit:
            return view, (hit[0], hit[1]), hit[2]
        seg = snap.segment(q.x(), q.y(), self.tol() * 0.7)
        if seg:
            return view, seg[2], "edge"
        return view, (q.x(), q.y()), None

    def hover(self, pos):
        view, p, kind = self.locate(pos)
        if view is not None and kind:
            self.scene.marker.show_at(view.mapToScene(QPointF(*p)), kind)
            self.win.status(f"{self.hint}   ·   {SNAP_NAMES.get(kind, '')}")
        else:
            self.scene.marker.show_at(QPointF(), None)
        return view, p, kind

    def show_preview(self, data, view):
        self.clear_preview()
        item = bi.note_from_dict(data, view)
        if item is None:
            return None
        item.transient = True
        item.setOpacity(0.75)
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setAcceptedMouseButtons(Qt.NoButton)
        if view is None:
            self.scene.addItem(item)
        self.preview = item
        return item

    def clear_preview(self):
        if self.preview is not None:
            item, self.preview = self.preview, None
            if item.scene() is not None:
                item.scene().removeItem(item)

    def finish(self, label):
        """Hand the preview's data over as a real note."""
        item = self.preview
        if item is None:
            return
        data, view = item.to_dict(), item.view
        self.clear_preview()
        self.win.add_note(data, view, label)


class SelectTool(Tool):
    key = "select"


class PanTool(Tool):
    key = "pan"
    hint = "Drag to pan the sheet; the wheel zooms."


class DimensionTool(Tool):
    """Smart, horizontal, vertical, aligned, radius and diameter.

    Smart picks by what is clicked: a round edge gives Ø (R for an
    arc), a straight edge its length, two points their distance — and
    where the cursor goes decides horizontal, vertical or aligned, as in
    SolidWorks' Smart Dimension."""

    HINTS = {
        "smart": "Smart dimension: click a round edge, a straight edge, "
                 "or two points — then place it.",
        "horizontal": "Horizontal dimension: click two points, then place.",
        "vertical": "Vertical dimension: click two points, then place.",
        "aligned": "Aligned dimension: click two points, then place.",
        "diameter": "Diameter: click a round edge, then place the "
                    "number.",
        "radius": "Radius: click a round edge or fillet, then place.",
    }

    def __init__(self, win, kind="smart"):
        self.kind = kind
        self.key = "dim_" + kind
        self.hint = self.HINTS[kind]
        super().__init__(win)

    def reset(self):
        super().reset()
        self.view = None
        self.points = []
        self.stage = "first"

    def _place_radial(self, view, c, pos):
        kind = self.kind if self.kind in ("radius", "diameter") else (
            "diameter" if c.get("closed") else "radius")
        data = {"type": "dim", "kind": kind,
                "centre": list(c["centre"]), "r": c["r"], "offset": 8.0,
                "angle": 45.0}
        self.view = view
        item = self.show_preview(data, view)
        q = view.mapFromScene(pos)
        item.drag_to((q.x(), q.y()))
        item.rebuild()
        self.stage = "place"

    def press(self, pos, event=None):
        if self.stage == "place":
            self.finish("Add dimension")
            self.reset()
            return
        view, p, kind = self.locate(pos)
        if view is None:
            self.win.status("Click on a view: a dimension measures the "
                            "model.")
            return
        q = view.mapFromScene(pos)
        snap = self.scene.snapper(view)
        if not self.points and self.kind in ("smart", "radius",
                                             "diameter"):
            c = snap.circle(q.x(), q.y(), self.tol())
            if c is not None and (kind != "centre" and (
                    kind != "end" or snap.on_rim(p, c))):
                self._place_radial(view, c, pos)
                return
            if self.kind != "smart":
                self.win.status("That is not a round edge: click the rim "
                                "of a hole, a boss or a fillet.")
                return
        if not self.points:
            seg = snap.segment(q.x(), q.y(), self.tol() * 0.7)
            if kind in (None, "edge") and seg is not None:
                self.view = view
                self.points = [view.to_model(seg[0]), view.to_model(seg[1])]
                self._begin_place(pos)
                return
            self.view = view
            self.points = [view.to_model(p)]
            self.stage = "second"
            self.win.status("Now click the second point.")
            return
        if view is not self.view:
            self.win.status("Pick the second point in the same view.")
            return
        second = view.to_model(p)
        if math.hypot(second[0] - self.points[0][0],
                      second[1] - self.points[0][1]) < 1e-9:
            return
        self.points.append(second)
        self._begin_place(pos)

    def _begin_place(self, pos):
        kind = self.kind if self.kind in ("horizontal", "vertical",
                                          "aligned") else "aligned"
        self.show_preview({"type": "dim", "kind": kind,
                           "a": list(self.points[0]),
                           "b": list(self.points[1]), "offset": 10.0},
                          self.view)
        self.stage = "place"
        self.move(pos)

    def move(self, pos, event=None):
        if self.stage != "place" or self.preview is None:
            self.hover(pos)
            return
        item = self.preview
        q = self.view.mapFromScene(pos)
        q = (q.x(), q.y())
        if item.data["kind"] in ("horizontal", "vertical", "aligned") \
                and self.kind == "smart":
            item.data["kind"] = self._smart_kind(q)
        item.drag_to(q)
        item.rebuild()

    def _smart_kind(self, q):
        A = self.view.to_local(self.points[0])
        B = self.view.to_local(self.points[1])
        if abs(A[0] - B[0]) < 1e-6:
            return "vertical"
        if abs(A[1] - B[1]) < 1e-6:
            return "horizontal"
        x0, x1 = sorted((A[0], B[0]))
        y0, y1 = sorted((A[1], B[1]))
        inside_x = x0 <= q[0] <= x1
        inside_y = y0 <= q[1] <= y1
        if inside_x and not inside_y:
            return "horizontal"
        if inside_y and not inside_x:
            return "vertical"
        return "aligned"


class AngleTool(Tool):
    key = "dim_angle"
    hint = "Angle: click two straight edges, then place the arc."

    def reset(self):
        super().reset()
        self.view = None
        self.first = None

    def press(self, pos, event=None):
        if self.preview is not None:
            self.finish("Add angle")
            self.reset()
            return
        view = self.scene.view_at(pos)
        if view is None:
            return
        q = view.mapFromScene(pos)
        seg = self.scene.snapper(view).segment(q.x(), q.y(), self.tol())
        if seg is None:
            self.win.status("Click a straight edge.")
            return
        edge = (view.to_model(seg[0]), view.to_model(seg[1]))
        if self.first is None:
            self.view, self.first = view, edge
            self.win.status("Now click the second edge.")
            return
        if view is not self.view:
            self.win.status("Pick the second edge in the same view.")
            return
        vertex = _intersect(self.first, edge)
        if vertex is None:
            self.win.status("Those edges are parallel — no angle.")
            return

        def far(e):
            return max(e, key=lambda p: math.hypot(p[0] - vertex[0],
                                                   p[1] - vertex[1]))
        item = self.show_preview({"type": "dim", "kind": "angle",
                                  "vertex": list(vertex),
                                  "p1": list(far(self.first)),
                                  "p2": list(far(edge)), "offset": 15.0,
                                  "decimals": 1}, view)
        item.drag_to((q.x(), q.y()))
        item.rebuild()

    def move(self, pos, event=None):
        if self.preview is None:
            self.hover(pos)
            return
        q = self.view.mapFromScene(pos)
        self.preview.drag_to((q.x(), q.y()))
        self.preview.rebuild()


def _intersect(e1, e2):
    (x1, y1), (x2, y2) = e1
    (x3, y3), (x4, y4) = e2
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return None
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den,
            (a * (y3 - y4) - (y1 - y2) * b) / den)


class TaggedTool(Tool):
    """Notes that point at something: click the spot, then where the
    label goes. Leader note, balloon, datum, geometric tolerance."""

    HINTS = {
        "leader": "Note: click what it points at, then where the text "
                  "goes.",
        "balloon": "Balloon: click the part, then where the balloon "
                   "goes (numbered like the parts list).",
        "datum": "Datum: click the datum edge, then where its letter "
                 "box goes.",
        "fcf": "Geometric tolerance: click the feature, then where the "
               "frame goes.",
    }

    def __init__(self, win, kind):
        self.kind = kind
        self.key = kind
        self.hint = self.HINTS[kind]
        super().__init__(win)

    def reset(self):
        super().reset()
        self.view = None

    def press(self, pos, event=None):
        if self.preview is None:
            view, p, _kind = self.locate(pos)
            tip = view.to_model(p) if view is not None else p
            self.view = view
            data = {"type": self.kind, "tip": list(tip), "at": [12.0, -10.0]}
            if self.kind == "balloon":
                data["number"] = self.scene.next_balloon()
            elif self.kind == "datum":
                data["letter"] = self.scene.next_datum()
                data["at"] = [0.0, -14.0]
            self.show_preview(data, view)
            self.win.status("Now click where the label goes.")
            return
        if self.kind == "leader":
            value = self.win.ask_text("Note", "Note text:", "NOTE", True)
            if value is None:
                self.reset()
                return
            self.preview.data["text"] = value
        elif self.kind == "fcf":
            got = self.win.ask_fcf()
            if got is None:
                self.reset()
                return
            self.preview.data.update(got)
        self.preview.rebuild()
        self.finish("Add " + self.preview.TITLE.lower())
        self.reset()

    def move(self, pos, event=None):
        if self.preview is None:
            self.hover(pos)
            return
        q = self.preview.mapFromScene(pos)
        self.preview.drag_to((q.x(), q.y()))
        self.preview.rebuild()


class FinishTool(Tool):
    key = "finish"
    hint = "Surface finish: click the surface's edge."

    def press(self, pos, event=None):
        view, p, _kind = self.locate(pos)
        if view is None:
            self.win.status("Click an edge of a view.")
            return
        value = self.win.ask_choice(
            "Surface finish", "Roughness:",
            ["Ra 0.8", "Ra 1.6", "Ra 3.2", "Ra 6.3", "Ra 12.5"], 2)
        if value is None:
            return
        self.win.add_note({"type": "finish", "tip": list(view.to_model(p)),
                           "ra": value}, view, "Add surface finish")


class CentreMarkTool(Tool):
    key = "centre_mark"
    hint = "Centre mark: click a round edge."

    def press(self, pos, event=None):
        view = self.scene.view_at(pos)
        if view is None:
            return
        q = view.mapFromScene(pos)
        c = self.scene.snapper(view).circle(q.x(), q.y(), self.tol())
        if c is None:
            self.win.status("That is not a round edge.")
            return
        self.win.add_note({"type": "centre_mark", "centre": list(c["centre"]),
                           "r": c["r"]}, view, "Add centre mark")


class CentreLineTool(Tool):
    key = "centre_line"
    hint = "Centre line: click two points (the middles of two edges, " \
           "say)."

    def reset(self):
        super().reset()
        self.view = None
        self.first = None

    def press(self, pos, event=None):
        view, p, _kind = self.locate(pos)
        if view is None:
            return
        if self.first is None:
            self.view, self.first = view, view.to_model(p)
            self.show_preview({"type": "centre_line", "a": list(self.first),
                               "b": list(self.first)}, view)
            return
        if view is not self.view:
            self.win.status("Pick the second point in the same view.")
            return
        self.preview.data["b"] = list(view.to_model(p))
        self.finish("Add centre line")
        self.reset()

    def move(self, pos, event=None):
        view, p, _kind = self.hover(pos)
        if self.preview is not None and view is self.view:
            self.preview.data["b"] = list(view.to_model(p))
            self.preview.rebuild()


class TextTool(Tool):
    key = "text"
    hint = "Text: click where it goes."

    def press(self, pos, event=None):
        value = self.win.ask_text("Text", "Text:", "", True)
        if value:
            self.win.add_note({"type": "text", "text": value,
                               "x": pos.x(), "y": pos.y(), "size": 5.0},
                              None, "Add text")


class SketchTool(Tool):
    """Line, rectangle or circle on the paper: click, then click (or
    drag). Snaps onto the views' points."""

    HINTS = {"line": "Line: click the start, then the end.",
             "rect": "Rectangle: click one corner, then the other.",
             "circle": "Circle: click the centre, then the rim."}

    def __init__(self, win, shape):
        self.shape = shape
        self.key = "sketch_" + shape
        self.hint = self.HINTS[shape]
        super().__init__(win)

    def reset(self):
        super().reset()
        self.start = None

    def _sheet_point(self, pos):
        view, p, kind = self.locate(pos)
        if view is not None and kind:
            q = view.mapToScene(QPointF(*p))
            return q.x(), q.y()
        return pos.x(), pos.y()

    def press(self, pos, event=None):
        p = self._sheet_point(pos)
        if self.start is None:
            self.start = p
            self.show_preview({"type": "sketch", "shape": self.shape,
                               "x": p[0], "y": p[1], "p1": [0.0, 0.0],
                               "p2": [0.0, 0.0]}, None)
            return
        self._commit(p)

    def release(self, pos, event=None):
        if self.start is None or self.preview is None:
            return
        p = self._sheet_point(pos)
        if math.hypot(p[0] - self.start[0], p[1] - self.start[1]) > 2.0:
            self._commit(p)                    # a drag, not a click

    def _commit(self, p):
        if math.hypot(p[0] - self.start[0], p[1] - self.start[1]) < 0.1:
            return
        self.preview.data["p2"] = [p[0] - self.start[0], p[1] - self.start[1]]
        self.finish("Add " + self.shape)
        self.reset()

    def move(self, pos, event=None):
        self.hover(pos)
        if self.preview is not None:
            p = self._sheet_point(pos)
            self.preview.data["p2"] = [p[0] - self.start[0],
                                       p[1] - self.start[1]]
            self.preview.rebuild()


class DetailTool(Tool):
    key = "detail"
    hint = "Detail view: click the centre of the area to enlarge, then " \
           "its edge."

    def reset(self):
        super().reset()
        self.view = None
        self.centre = None

    def press(self, pos, event=None):
        view, p, _kind = self.locate(pos)
        if self.centre is None:
            if view is None or view.data.get("kind") not in (
                    "projected", "section"):
                self.win.status("Click inside a projected view.")
                return
            self.view, self.centre = view, p
            at = view.mapToScene(QPointF(*p))
            self.show_preview({"type": "sketch", "shape": "circle",
                               "x": 0.0, "y": 0.0, "p1": [at.x(), at.y()],
                               "p2": [at.x(), at.y()], "line": "thin"},
                              None)
            return
        q = self.view.mapFromScene(pos)
        radius = math.hypot(q.x() - self.centre[0], q.y() - self.centre[1])
        if radius < 1.0:
            return
        centre = self.view.to_model(self.centre)
        self.clear_preview()
        self.win.add_detail(self.view, centre, radius / self.view.scale_)
        self.reset()

    def move(self, pos, event=None):
        self.hover(pos)
        if self.preview is not None:
            self.preview.data["p2"] = [pos.x(), pos.y()]
            self.preview.rebuild()


def make_tools(win):
    """Every tool, by key — the toolbar and tests look them up here."""
    tools = [SelectTool(win), PanTool(win)]
    tools += [DimensionTool(win, k) for k in
              ("smart", "horizontal", "vertical", "aligned", "diameter",
               "radius")]
    tools += [AngleTool(win)]
    tools += [TaggedTool(win, k) for k in ("leader", "balloon", "datum",
                                           "fcf")]
    tools += [FinishTool(win), CentreMarkTool(win), CentreLineTool(win),
              TextTool(win)]
    tools += [SketchTool(win, s) for s in ("line", "rect", "circle")]
    tools += [DetailTool(win)]
    return {t.key: t for t in tools}

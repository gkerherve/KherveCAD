"""The Blueprint's sheet as data and items, without a window: the
model's geometry as the drawing sees it (`Geometry`), and
`BlueprintScene` — frame, title block, views and notes, the state they
are saved as, the third-angle layout, alignment and auto-dimensioning.
The window (blueprint.py) wraps it; the export_drawing MCP tool builds
one offscreen (`blueprint.export_saved`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import datetime
import getpass
import math
import re
from contextlib import contextmanager

from PyQt5.QtCore import QPointF, QRectF, QSettings
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import QGraphicsScene

from . import analysis, drawing
from . import blueprint_items as bi
from . import section as section_mod
from . import shading
from .blueprint_tools import SnapMarker, ViewSnap

_SETTINGS = ("Kherve", "KherveCAD")

#: the projections a sheet can hold
PROJECTIONS = ("Front", "Top", "Right", "Left", "Back", "Bottom",
               "Isometric")
#: which of Front's coordinates a projected view shares (third-angle)
ALIGN = {"Top": "x", "Bottom": "x", "Right": "y", "Left": "y", "Back": "y"}
#: a section's cutting line: the view it is drawn on, and which way
#: its arrows look on that view (sheet direction, y down)
SECTION_PARENT = {"y": "Top", "x": "Front", "z": "Front"}
SECTION_LOOK = {"y": (0.0, -1.0), "x": (-1.0, 0.0), "z": (0.0, 1.0)}
#: the sheet the first layout uses
DEFAULT_SHEET = "A3"
#: room between views for their dimensions (sheet mm)
GAP = 24.0
#: letters a section or detail may take (I, O and Q read as numbers)
LETTERS = [c for c in "ABCDEFGHJKLMNPRSTUVWXYZ"]


# ── the model, as the drawing sees it ──────────────────────────────

class Geometry:
    """The triangles being drawn, analysed once; each view's lines and
    round edges are projected on first use and kept, so an undo or a
    style change never re-projects a thread."""

    def __init__(self, tris):
        self.tris = list(tris or ())
        self.info = shading.analyse(self.tris) if self.tris else None
        self._views, self._sections = {}, {}
        self._volume = None
        if self.tris:
            pts = [p for t in self.tris for p in t]
            self.lo = [min(p[i] for p in pts) for i in range(3)]
            self.hi = [max(p[i] for p in pts) for i in range(3)]
        else:
            self.lo = self.hi = [0.0, 0.0, 0.0]

    def view(self, name, hidden=True):
        key = (name, bool(hidden))
        got = self._views.get(key)
        if got is None:
            raw = drawing.view_lines(self.tris, name, self.info, hidden)
            circles = [] if name == "Isometric" else drawing.find_circles(
                raw["visible"] + raw["hidden"])
            got = self._views[key] = {
                "visible": drawing.merge_collinear(raw["visible"]),
                "hidden": drawing.merge_collinear(raw["hidden"]),
                "bounds": raw["bounds"], "circles": circles}
        return got

    def middle(self, axis):
        k = "xyz".index(axis)
        return (self.lo[k] + self.hi[k]) / 2.0

    def section(self, axis, offset):
        key = (axis, round(float(offset), 6))
        got = self._sections.get(key)
        if got is None:
            cut = section_mod.section(self.tris, axis, float(offset))
            outlines = [o["points"] for o in cut["outlines"]
                        if o["closed"] and len(o["points"]) >= 3]
            segs = [(a, b) for pts in outlines
                    for a, b in zip(pts, pts[1:] + pts[:1])]
            got = self._sections[key] = {
                "outlines": outlines, "bounds": cut["bounds"],
                "circles": drawing.find_circles(segs)}
        return got

    def volume(self):
        if self._volume is None:
            self._volume = abs(analysis.mass_properties(self.tris)
                               ["volume"]) if self.tris else 0.0
        return self._volume


def mass_text(volume, material):
    """The title block's mass, from the volume and the material's
    density — blank for a material the table does not know."""
    if material not in analysis.MATERIALS or volume <= 0:
        return ""
    grams = analysis.mass(volume, material)
    return (f"{grams / 1000.0:.3g} kg" if grams >= 1000.0
            else f"{grams:.3g} g")


def default_fields(title):
    settings = QSettings(*_SETTINGS)
    stem = re.sub(r"[^A-Za-z0-9]+", "-", title or "PART").strip("-")
    return {
        "title": title or "Part",
        "number": (stem.upper()[:16] or "PART") + "-001",
        "material": str(settings.value("blueprint/material",
                                       analysis.DEFAULT_MATERIAL)),
        "finish": "", "mass": "",
        "company": str(settings.value("blueprint/company", "")),
        "drawn": str(settings.value("blueprint/drawn", _user())),
        "date": datetime.date.today().isoformat(),
        "checked": "", "approved": "", "revision": "A",
        "tolerance": "ISO 2768-m", "sheet_no": "1 / 1",
    }


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return ""


# ── the sheet ──────────────────────────────────────────────────────

class BlueprintScene(QGraphicsScene):
    """The sheet: frame, title block, views and notes, and the state
    they are saved as. Usable without a window (the MCP export builds
    one offscreen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.look = bi.Look()
        self.geometry = Geometry(())
        self.sheet = DEFAULT_SHEET
        self.W, self.H = drawing.SHEETS[self.sheet]
        self.scale = 1.0
        self.hidden_lines = True
        self.fields = {}
        self.views = {}
        self.note_items = []
        self.derived = []
        self.frame = self.title = None
        self.marker = SnapMarker()
        self.addItem(self.marker)
        self.on_edit = None           # callback(label) — the window's commit
        self.picture = None           # callback(view data) -> QImage
        self._snaps = {}
        self._moving = False
        self._front_pos = None
        self._setup_paper()

    # -- paper
    def sheet_rect(self):
        return QRectF(0.0, 0.0, self.W, self.H)

    def _setup_paper(self):
        for item in (self.frame, self.title):
            if item is not None and item.scene() is self:
                self.removeItem(item)
        self.W, self.H = drawing.SHEETS.get(self.sheet,
                                            drawing.SHEETS[DEFAULT_SHEET])
        self.frame = bi.FrameItem({"width": self.W, "height": self.H})
        self.addItem(self.frame)
        self.title = bi.TitleBlockItem({})
        m = bi.FrameItem.MARGIN
        self.title.setPos(self.W - m - drawing.TITLE_W,
                          self.H - m - drawing.TITLE_H)
        self.addItem(self.title)
        self.refresh_title()
        self.setSceneRect(-self.W * 0.6, -self.H * 0.6, self.W * 2.2,
                          self.H * 2.2)

    def display_fields(self):
        out = dict(self.fields)
        if not str(out.get("mass") or "").strip():
            out["mass"] = mass_text(self.geometry.volume(),
                                    str(out.get("material", "")))
        return out

    def refresh_title(self):
        self.title.data.update(fields=self.display_fields(),
                               scale_label=drawing.scale_label(self.scale),
                               sheet=self.sheet)
        self.title.rebuild()

    def title_text(self):
        return str(self.fields.get("title") or "Blueprint")

    def usable_rect(self):
        """Where views go: inside the frame, above the title block."""
        m = bi.FrameItem.MARGIN + 6.0
        return QRectF(m, m, self.W - 2 * m,
                      self.H - 2 * m - drawing.TITLE_H - 2.0)

    def drawBackground(self, painter, rect):
        sheet = self.sheet_rect()
        if not self.look.exporting:
            painter.fillRect(rect, QColor("#6b7178"))
            painter.fillRect(sheet.translated(1.5, 2.0), QColor(0, 0, 0, 80))
        painter.fillRect(sheet, self.look.color("ground"))
        grid = bi.STYLES[self.look.style].get("grid")
        if grid:
            painter.setPen(QPen(QColor(grid), 0.15))
            x = 10.0
            while x < self.W:
                painter.drawLine(QPointF(x, 0), QPointF(x, self.H))
                x += 10.0
            y = 10.0
            while y < self.H:
                painter.drawLine(QPointF(0, y), QPointF(self.W, y))
                y += 10.0

    @contextmanager
    def exporting(self):
        """Paint the drawing and nothing else: no selection, no snap
        marker, no half-made preview, no desk around the paper."""
        selected = self.selectedItems()
        for item in selected:
            item.setSelected(False)
        hidden = [i for i in self.items()
                  if getattr(i, "transient", False) and i.isVisible()]
        for item in hidden:
            item.hide()
        cached = [(i, i.cacheMode()) for i in self.views.values()]
        for item, _mode in cached:
            item.setCacheMode(bi.QGraphicsItem.NoCache)
        self.look.exporting = True
        try:
            yield
        finally:
            self.look.exporting = False
            for item, mode in cached:
                item.setCacheMode(mode)
            for item in hidden:
                item.show()
            for item in selected:
                if item.scene() is self:
                    item.setSelected(True)

    # -- state
    def state(self):
        return {"version": 1, "sheet": self.sheet, "style": self.look.style,
                "scale": self.scale, "hidden_lines": self.hidden_lines,
                "fields": dict(self.fields),
                "views": [v.to_dict() for v in self.views.values()],
                "notes": [n.to_dict() for n in self.notes()]}

    def load_state(self, state):
        state = copy.deepcopy(state or {})
        for item in list(self.items()):
            if item is not self.marker and item.parentItem() is None:
                self.removeItem(item)
        self.views, self.note_items, self.derived = {}, [], []
        self._snaps = {}
        self._front_pos = None
        self.frame = self.title = None
        self.sheet = state.get("sheet", DEFAULT_SHEET)
        if self.sheet not in drawing.SHEETS:
            self.sheet = DEFAULT_SHEET
        self.look.style = state.get("style", "paper") \
            if state.get("style") in bi.STYLES else "paper"
        self.scale = float(state.get("scale") or 1.0)
        self.hidden_lines = bool(state.get("hidden_lines", True))
        self.fields = dict(state.get("fields") or {})
        self._setup_paper()
        for data in state.get("views") or []:
            self.add_view(data, marks=False)
        for data in state.get("notes") or []:
            view = self.views.get(data.get("view")) if data.get("view") \
                else None
            if data.get("view") and view is None:
                continue                       # its view is gone
            self.add_note(data, view)
        self.update_marks()
        self.update()

    def notes(self):
        return [n for n in self.note_items if n.scene() is self]

    # -- views
    def next_id(self):
        numbers = [int(k[1:]) for k in self.views if k[1:].isdigit()]
        return f"v{max(numbers, default=0) + 1}"

    def next_letter(self):
        used = {v.data.get("letter") for v in self.views.values()}
        return next((c for c in LETTERS if c not in used), "Z")

    def next_balloon(self):
        numbers = [int(n.data.get("number")) for n in self.notes()
                   if n.KIND == "balloon"
                   and str(n.data.get("number", "")).isdigit()]
        return str(max(numbers, default=0) + 1)

    def next_datum(self):
        used = {n.data.get("letter") for n in self.notes()
                if n.KIND == "datum"}
        return next((c for c in LETTERS if c not in used), "Z")

    def projected(self, name):
        return next((v for v in self.views.values()
                     if v.data.get("kind", "projected") == "projected"
                     and v.data.get("name") == name), None)

    def add_view(self, data, marks=True):
        data = dict(data)
        data.setdefault("id", self.next_id())
        data.setdefault("kind", "projected")
        data.setdefault("show_label", data["kind"] != "projected"
                        or data.get("name") == "Isometric")
        item = bi.ViewItem(data)
        item.setCacheMode(bi.QGraphicsItem.DeviceCoordinateCache)
        self.views[data["id"]] = item
        self.addItem(item)
        self.fill_view(item)
        if data["kind"] == "projected" and data.get("name") == "Front":
            self._front_pos = item.pos()
        if marks:
            self.update_marks()
        return item

    def fill_view(self, item):
        """Give *item* its content for the current geometry and scale."""
        g, d = self.geometry, item.data
        kind = d.get("kind", "projected")
        s = self.scale * float(d.get("factor", 1.0))
        self._snaps.pop(d["id"], None)
        if kind == "shaded":
            image = self.picture(d) if self.picture else None
            w = float(d.get("width", 80.0))
            h = w * (image.height() / image.width() if image is not None
                     and image.width() else 0.75)
            item.set_content(scale=1.0, bounds=(0.0, 0.0, w, h), image=image)
            return
        if not g.tris:
            item.set_content(scale=s, bounds=(0.0, 0.0, 20.0, 20.0))
            return
        if kind == "section":
            axis = d.get("axis", "y")
            if d.get("offset") is None:
                d["offset"] = g.middle(axis)
            got = g.section(axis, d["offset"])
            item.set_content(scale=s, bounds=got["bounds"] or (0, 0, 1, 1),
                             outlines=got["outlines"],
                             circles=got["circles"])
            return
        if kind == "detail":
            base = g.view(d.get("source", "Front"), self.hidden_lines)
            (cu, cv), r = d["centre"], float(d["radius"])
            lines = {key: drawing.clip_to_circle(base[key], (cu, cv), r)
                     for key in ("visible", "hidden")}
            circles = [c for c in base["circles"]
                       if math.hypot(c["centre"][0] - cu,
                                     c["centre"][1] - cv) + c["r"] <= r * 1.02]
            item.set_content(scale=s, bounds=(cu - r, cv - r, cu + r, cv + r),
                             lines=lines, clip=((cu, cv), r), circles=circles)
            return
        name = d.get("name", "Front")
        hidden = self.hidden_lines and name != "Isometric" and \
            d.get("hidden", True)
        got = g.view(name, hidden)
        item.set_content(scale=s, bounds=got["bounds"], lines=got,
                         circles=got["circles"])

    def refill(self):
        for item in self.views.values():
            self.fill_view(item)
        for note in self.notes() + self.derived:
            note.rebuild()
        self.update_marks()
        self.refresh_title()

    def snapper(self, view):
        snap = self._snaps.get(view.data["id"])
        if snap is None:
            snap = self._snaps[view.data["id"]] = ViewSnap(view)
        return snap

    def view_at(self, pos):
        """The view under sheet point *pos* (the smallest, when they
        overlap), or None."""
        best, area = None, None
        for view in self.views.values():
            rect = view.mapRectToScene(view.content_rect().adjusted(
                -3.0, -3.0, 3.0, 3.0))
            if rect.contains(pos):
                a = rect.width() * rect.height()
                if area is None or a < area:
                    best, area = view, a
        return best

    def update_marks(self):
        """Redraw what one view puts on another: a detail's circle and
        letter, a section's cutting line."""
        for item in self.derived:
            if item.scene() is self:
                self.removeItem(item)
        self.derived = []
        for view in self.views.values():
            d = view.data
            if d.get("kind") == "detail":
                parent = self.views.get(d.get("parent"))
                if parent is not None:
                    self.derived.append(bi.DetailMarkItem(
                        {"centre": d["centre"], "radius": d["radius"],
                         "letter": d.get("letter", "A")}, parent))
            elif d.get("kind") == "section":
                axis = d.get("axis", "y")
                parent = self.projected(SECTION_PARENT[axis])
                if parent is None:
                    continue
                u0, v0, u1, v1 = parent.bounds
                off = float(d.get("offset") or 0.0)
                if axis == "x":
                    a, b = (off, v0), (off, v1)
                else:
                    a, b = (u0, off), (u1, off)
                self.derived.append(bi.CuttingLineItem(
                    {"a": list(a), "b": list(b), "look": SECTION_LOOK[axis],
                     "letter": d.get("letter", "A")}, parent))

    # -- keeping projections aligned
    def front(self):
        return self.projected("Front")

    def constrain_view(self, view, value):
        axis = ALIGN.get(view.data.get("name")) \
            if view.data.get("kind", "projected") == "projected" else None
        front = self.front()
        if self._moving or not axis or front is None or front is view \
                or not view.data.get("aligned", True):
            return value
        if axis == "x":
            return QPointF(front.pos().x(), value.y())
        return QPointF(value.x(), front.pos().y())

    def view_moved(self, view):
        """Front carries the views aligned to it."""
        if view is not self.front() or self._moving:
            return
        now = view.pos()
        before = self._front_pos if self._front_pos is not None else now
        delta = now - before
        self._front_pos = now
        if delta.isNull():
            return
        self._moving = True
        try:
            for other in self.views.values():
                if other is view or other.isSelected() or \
                        other.data.get("kind", "projected") != "projected" \
                        or other.data.get("name") not in ALIGN \
                        or not other.data.get("aligned", True):
                    continue
                other.setPos(other.pos() + delta)
        finally:
            self._moving = False

    def edited(self, label="Edit"):
        if self.on_edit is not None:
            self.on_edit(label)

    # -- notes
    def add_note(self, data, view=None):
        item = bi.note_from_dict(data, view)
        if item is None:
            return None
        if view is None:
            self.addItem(item)
        self.note_items.append(item)
        return item

    def remove(self, items):
        """Delete notes and views (a view takes its notes with it)."""
        for item in items:
            if isinstance(item, bi.ViewItem):
                vid = item.data["id"]
                self.views.pop(vid, None)
                self._snaps.pop(vid, None)
                self.note_items = [n for n in self.note_items
                                   if n.view is not item]
                if item.scene() is self:
                    self.removeItem(item)
            elif item in self.note_items:
                self.note_items.remove(item)
                if item.scene() is self:
                    self.removeItem(item)
        self.update_marks()

    # -- layout
    def new_layout(self, names=("Front", "Top", "Right", "Isometric")):
        for view in list(self.views.values()):
            self.remove([view])
        for name in names:
            self.add_view({"kind": "projected", "name": name}, marks=False)
        self.arrange()

    def arrange(self, scale=None):
        """Third-angle placement: Top over Front, Right beside it, Left
        and Back either side, Bottom under it, the isometric top-right —
        at *scale*, or the largest standard scale that fits."""
        area = self.usable_rect()

        def dims(name):
            v = self.projected(name)
            if v is None:
                return 0.0, 0.0
            b = v.bounds
            return b[2] - b[0], b[3] - b[1]
        cols = [n for n in ("Left", "Front", "Right", "Back")
                if self.projected(n)]
        iso = self.projected("Isometric")
        if not cols and iso is None:
            return
        widths = [dims(n)[0] for n in cols] + ([dims("Isometric")[0]]
                                               if iso else [])
        top_h = max(dims("Top")[1], dims("Isometric")[1] if iso and
                    self.projected("Top") else 0.0)
        mid_h = max([dims(n)[1] for n in cols] + (
            [dims("Isometric")[1]] if iso and not self.projected("Top")
            else [0.0]))
        bot_h = dims("Bottom")[1]
        rows = [h for h in (top_h, mid_h, bot_h) if h > 0]
        gaps_w = GAP * (len(widths) - 1)
        gaps_h = GAP * (len(rows) - 1)
        if scale is None:
            scale = drawing.nice_scale(
                sum(widths), sum(rows), max(area.width() - gaps_w, 10.0),
                max(area.height() - gaps_h, 10.0))
        self.scale = float(scale)
        for view in self.views.values():
            view.set_scale(self.scale * float(view.data.get("factor", 1.0)))
        s = self.scale
        total_w = sum(widths) * s + gaps_w
        total_h = sum(rows) * s + gaps_h
        left = area.left() + max(0.0, (area.width() - total_w) / 2.0)
        top = area.top() + max(0.0, (area.height() - total_h) / 2.0)
        x = left
        col_x = {}
        for name, w in zip(cols + (["Isometric"] if iso else []), widths):
            col_x[name] = x
            x += w * s + GAP
        top_bottom = top + top_h * s
        mid_bottom = top_bottom + (GAP if top_h else 0.0) + mid_h * s
        bot_bottom = mid_bottom + GAP + bot_h * s
        self._moving = True
        try:
            for name in cols:
                self.projected(name).setPos(col_x[name], mid_bottom)
            front_x = col_x.get("Front", left)
            if self.projected("Top"):
                self.projected("Top").setPos(front_x, top_bottom)
            if self.projected("Bottom"):
                self.projected("Bottom").setPos(front_x, bot_bottom)
            if iso is not None:
                iso.setPos(col_x["Isometric"],
                           top_bottom if self.projected("Top")
                           else mid_bottom)
        finally:
            self._moving = False
        front = self.front()
        self._front_pos = front.pos() if front is not None else None
        for note in self.notes() + self.derived:
            note.rebuild()
        self.update_marks()
        self.refresh_title()

    def set_scale(self, scale):
        """A new sheet scale: views re-arranged, sections and details
        kept where they are (centred on the same spot)."""
        keep = {}
        for view in self.views.values():
            if view.data.get("kind") != "projected":
                keep[view] = view.mapToScene(view.content_rect().center())
        self.arrange(scale)
        for view, centre in keep.items():
            view.setPos(centre - view.content_rect().center())

    def set_sheet(self, name):
        self.sheet = name if name in drawing.SHEETS else DEFAULT_SHEET
        self._setup_paper()
        self.arrange()

    def free_spot(self, w, h):
        """The first place (scanning the usable area) where a w x h
        view clears everything already on the sheet."""
        area = self.usable_rect()
        taken = [v.mapRectToScene(v.boundingRect()).adjusted(-6, -6, 6, 6)
                 for v in self.views.values()]
        taken += [n.mapRectToScene(n.boundingRect()) for n in self.notes()
                  if n.MOVABLE]
        y = area.top()
        while y + h <= area.bottom():
            x = area.left()
            while x + w <= area.right():
                rect = QRectF(x, y, w, h + 10.0)
                if not any(rect.intersects(t) for t in taken):
                    return x, y + h
                x += 5.0
            y += 5.0
        return area.left(), area.top() + h

    # -- dimensioning by itself
    def auto_dimension(self):
        """Overall sizes on the principal views, every hole's diameter
        (grouped: "4× Ø6") and a centre mark on each. Re-running
        replaces what it added before and leaves the user's own."""
        self.remove([n for n in self.notes() if n.data.get("auto")])
        top = self.projected("Top") is not None
        want = {"Front": ("h", "v"), "Top": ("v",),
                "Right": () if top else ("h",)}
        for view in list(self.views.values()):
            d = view.data
            if d.get("kind", "projected") not in ("projected", "section"):
                continue
            name = d.get("name") if d.get("kind", "projected") == \
                "projected" else "section"
            if name == "Isometric":
                continue
            pts = [p for key in ("visible", "hidden")
                   for seg in view.lines.get(key, ()) for p in seg]
            for o in view.outlines:
                pts += list(o)
            if not pts:
                continue
            w, h = view.size()
            for axis in want.get(name, ("h", "v") if name == "section"
                                 else ()):
                self._auto_linear(view, pts, axis, w, h, name)
            self._auto_circles(view)

    def _auto_linear(self, view, pts, axis, w, h, name):
        if axis == "h":
            a = min(pts, key=lambda p: (round(p[0], 6), p[1]))
            b = max(pts, key=lambda p: (round(p[0], 6), -p[1]))
            if b[0] - a[0] < 1e-6:
                return
            mid = (view.to_local(a)[1] + view.to_local(b)[1]) / 2.0
            offset = 10.0 - mid                   # under the view
            self.add_note({"type": "dim", "kind": "horizontal",
                           "a": list(a), "b": list(b), "offset": offset,
                           "auto": True}, view)
        else:
            if name == "Top":                     # depth, on the left
                a = min(pts, key=lambda p: (round(p[1], 6), p[0]))
                b = max(pts, key=lambda p: (round(p[1], 6), -p[0]))
                line_x = -10.0
            else:                                 # height, on the right
                a = min(pts, key=lambda p: (round(p[1], 6), -p[0]))
                b = max(pts, key=lambda p: (round(p[1], 6), -p[0]))
                line_x = w + 10.0
            if b[1] - a[1] < 1e-6:
                return
            mid = (view.to_local(a)[0] + view.to_local(b)[0]) / 2.0
            self.add_note({"type": "dim", "kind": "vertical",
                           "a": list(a), "b": list(b),
                           "offset": line_x - mid, "auto": True}, view)

    def _auto_circles(self, view, most=8):
        groups = {}
        for c in view.circles:
            if c["r"] * view.scale_ < 0.8:
                continue                           # a speck on paper
            key = (bool(c["closed"]), round(c["r"], 2))
            groups.setdefault(key, []).append(c)
        order = sorted(groups.items(), key=lambda kv: -kv[0][1])[:most]
        w, h = view.size()
        mid = (w / 2.0, -h / 2.0)
        for (closed, _r), circles in order:
            # label the hole nearest the outline, its leader pointing
            # away from the middle so the number lands off the part
            first = max(circles, key=lambda c: math.hypot(
                *[a - b for a, b in zip(view.to_local(c["centre"]), mid)]))
            angle, offset = _leader(view.to_local(first["centre"]),
                                    first["r"] * view.scale_, mid, w, h)
            self.add_note({"type": "dim",
                           "kind": "diameter" if closed else "radius",
                           "centre": list(first["centre"]),
                           "r": first["r"], "angle": angle, "offset": offset,
                           "count": len(circles), "auto": True}, view)
            if closed:
                for c in circles[:40]:
                    self.add_note({"type": "centre_mark",
                                   "centre": list(c["centre"]),
                                   "r": c["r"], "auto": True}, view)


#: leader directions a label may take: never along an axis, where it
#: would read as a dimension line or an edge
_LEADER_ANGLES = (30.0, 60.0, 120.0, 150.0, 210.0, 240.0, 300.0, 330.0)


def _leader(C, R, mid, w, h):
    """(angle°, offset mm) for a Ø/R label on the circle at local *C*:
    pointing away from the view's middle, long enough to clear the
    view's outline by 6 mm."""
    dx, dy = C[0] - mid[0], C[1] - mid[1]
    raw = math.degrees(math.atan2(-dy, dx)) if math.hypot(dx, dy) > 1e-6 \
        else 45.0
    angle = min(_LEADER_ANGLES,
                key=lambda a: abs(((a - raw) + 180.0) % 360.0 - 180.0))
    ux, uy = math.cos(math.radians(angle)), -math.sin(math.radians(angle))
    exits = []
    if ux > 1e-9:
        exits.append((w - C[0]) / ux)
    elif ux < -1e-9:
        exits.append(-C[0] / ux)
    if uy > 1e-9:
        exits.append(-C[1] / uy)
    elif uy < -1e-9:
        exits.append((-h - C[1]) / uy)
    reach = min((t for t in exits if t > 0), default=R)
    return angle, max(6.0, reach - R + 6.0)

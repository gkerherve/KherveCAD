"""More for the Blueprint (2026-10-21, the SolidWorks gap list): a
REVISION TABLE, ORDINATE dimensions, and BASELINE / CHAIN dimension
runs. Split from blueprint_items (at its size) and registered into its
NOTE_CLASSES on import, so the saved state, exports and the MCP
`blueprint` tool know them.

- `RevisionItem` ("revisions"): REV / DESCRIPTION / DATE / BY rows, a
  free table like the parts list; `add_revision` appends a row with the
  next letter and today's date and sets the title block's revision.
- `OrdinateItem` ("ordinate"): a datum and points in a view; every
  point gets a leader and its distance from the datum along u
  ("horizontal") or v ("vertical") — the model's distance, at any scale.
- `baseline` / `chain`: several linear dimensions from one base point
  (stacked `gap` apart) or end to end (in one line), as ordinary `dim`
  notes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import datetime
import string

from . import blueprint_items as bi


class RevisionItem(bi.BomItem):
    """The revision table: REV, DESCRIPTION, DATE, BY."""

    KIND = "revisions"
    TITLE = "Revision table"
    COLS = (("REV", 12.0), ("DESCRIPTION", 78.0), ("DATE", 24.0),
            ("BY", 16.0))
    FULL_COLS = COLS
    DEFAULTS = {"rows": [], "style": "basic"}


class OrdinateItem(bi.SheetItem):
    """Ordinate dimensions: a datum (0) and each point's distance from
    it along one axis, on its own leader."""

    KIND = "ordinate"
    TITLE = "Ordinate dimensions"
    ANCHORED = True
    DEFAULTS = {"axis": "horizontal", "origin": [0.0, 0.0], "points": [],
                "offset": 10.0, "decimals": 1}
    FIELDS = (("axis", "Measures along", "choice",
               (("horizontal", "Horizontal"), ("vertical", "Vertical"))),
              ("offset", "Leader length (mm)", "float", (1.0, 200.0)),
              ("decimals", "Decimals", "int", (0, 4)))

    def values(self):
        d = self.data
        k = 0 if d.get("axis", "horizontal") == "horizontal" else 1
        o = d.get("origin") or [0.0, 0.0]
        return [p[k] - o[k] for p in d.get("points") or []]

    def primitives(self):
        d = self.data
        horiz = d.get("axis", "horizontal") == "horizontal"
        off = float(d.get("offset", 10.0))
        out = []
        pts = [d.get("origin") or [0.0, 0.0]] + list(d.get("points") or [])
        vals = [0.0] + self.values()
        # every leader ends on one line, past the furthest point
        locs = [self.local(p) for p in pts]
        if horiz:
            end = min(q[1] for q in locs) - off      # sheet y is down
        else:
            end = max(q[0] for q in locs) + off
        for q, v in zip(locs, vals):
            tip = (q[0], end) if horiz else (end, q[1])
            out.append(bi.line("thin", (q[0] + (0 if horiz else 1.0),
                                        q[1] - (1.0 if horiz else 0)), tip))
            label = bi.fmt(abs(v), d.get("decimals", 1))
            if horiz:
                out.append(bi.text(label, (tip[0] + 1.0, tip[1] - 1.0),
                                   bi.TEXT, "left", "baseline",
                                   angle=90.0))
            else:
                out.append(bi.text(label, (tip[0] + 1.0, tip[1]),
                                   bi.TEXT, "left", "middle"))
        return out

    def drag_to(self, q):
        """Dragging moves the line the values stand on."""
        d = self.data
        horiz = d.get("axis", "horizontal") == "horizontal"
        locs = [self.local(p) for p in [d.get("origin") or [0, 0]]
                + list(d.get("points") or [])]
        if horiz:
            d["offset"] = max(1.0, min(p[1] for p in locs) - q[1])
        else:
            d["offset"] = max(1.0, q[0] - max(p[0] for p in locs))


bi.NOTE_CLASSES[RevisionItem.KIND] = RevisionItem
bi.NOTE_CLASSES[OrdinateItem.KIND] = OrdinateItem


# ----------------------------------------------------------- helpers
def next_rev(rows):
    letters = [str(r[0]) for r in rows if r]
    if not letters:
        return "A"
    last = letters[-1]
    if last.isdigit():
        return str(int(last) + 1)
    if last and last[-1] in string.ascii_uppercase[:-1]:
        return last[:-1] + chr(ord(last[-1]) + 1)
    return last + "A"


def add_revision(scene, description, by="", date=None):
    """Append a row to the sheet's revision table (made beside the title
    block when there is none) and set the title block's revision."""
    table = next((n for n in scene.notes()
                  if isinstance(n, RevisionItem)), None)
    if table is None:
        x, y = _beside_title(scene)
        table = scene.add_note({"type": "revisions", "x": x, "y": y})
    rows = list(table.data.get("rows") or [])
    rev = next_rev(rows)
    rows.append([rev, str(description),
                 date or datetime.date.today().isoformat(), str(by)])
    table.data["rows"] = rows
    table.rebuild()
    fields = getattr(scene, "fields", None)
    if isinstance(fields, dict):
        fields["revision"] = rev
        if hasattr(scene, "refresh_title"):
            scene.refresh_title()
    return rev


def _beside_title(scene):
    """Top-right of the sheet's usable area, where revision tables go."""
    try:
        r = scene.usable_rect()
        return round(r.right() - 132.0, 3), round(r.top() + 2.0, 3)
    except Exception:
        return 20.0, 20.0


def baseline(base, points, kind="horizontal", offset=10.0, gap=7.0):
    """Dimension dicts from *base* to each point, stacked *gap* apart."""
    k = 0 if kind == "horizontal" else 1
    pts = sorted(points, key=lambda p: abs(p[k] - base[k]))
    return [{"type": "dim", "kind": kind, "a": list(base), "b": list(p),
             "offset": offset + i * gap} for i, p in enumerate(pts)]


def chain(points, kind="horizontal", offset=10.0):
    """Dimension dicts end to end along the points, in one line."""
    k = 0 if kind == "horizontal" else 1
    pts = sorted(points, key=lambda p: p[k])
    return [{"type": "dim", "kind": kind, "a": list(a), "b": list(b),
             "offset": offset} for a, b in zip(pts, pts[1:])]


# ---------------------------------------------------------------- tools
def _tools_module():
    from . import blueprint_tools
    return blueprint_tools


def make_run_tools(win):
    """Baseline / chain / ordinate tools: click the base (datum) point,
    then each point; right-click or a second click on the last point
    finishes. Built on blueprint_tools.Tool (imported late)."""
    bt = _tools_module()

    class _Run(bt.Tool):
        mode = "baseline"

        def reset(self):
            super().reset()
            self.view = None
            self.pts = []

        def press(self, pos, event=None):
            from PyQt5.QtCore import Qt
            if event is not None and event.button() == Qt.RightButton:
                self.done()
                return
            view, p, _k = self.locate(pos)
            if view is None or (self.view is not None
                                and view is not self.view):
                self.win.status("Click points in one view.")
                return
            self.view = view
            m = list(view.to_model(p))
            if self.pts and m == self.pts[-1]:
                self.done()              # the double-click's second press
                return
            self.pts.append(m)
            self._show()
            self.win.status("%s: %d point(s) — right-click to finish."
                            % (self.title, len(self.pts)))

        def _notes(self):
            if len(self.pts) < 2:
                return []
            base, rest = self.pts[0], self.pts[1:]
            kind = self.direction()
            if self.mode == "baseline":
                return baseline(base, rest, kind)
            if self.mode == "chain":
                return chain(self.pts, kind)
            return [{"type": "ordinate", "axis": kind, "origin": base,
                     "points": rest}]

        def direction(self):
            a, b = self.pts[0], self.pts[-1]
            return "horizontal" if abs(b[0] - a[0]) >= abs(b[1] - a[1]) \
                else "vertical"

        def _show(self):
            notes = self._notes()
            if notes:
                self.show_preview(notes[-1], self.view)

        def done(self):
            notes = self._notes()
            view = self.view
            self.clear_preview()
            self.reset()
            if not notes:
                return
            for data in notes:
                self.win.scene.add_note(data, view)
            self.win.commit("Add %s dimensions" % self.mode)

        def cancel(self):
            busy = bool(self.pts)
            self.reset()
            return busy

    out = []
    for key, mode, title, hint in (
            ("baseline", "baseline", "Baseline dimensions",
             "Baseline: click the base point, then each point."),
            ("chain", "chain", "Chain dimensions",
             "Chain: click the points in order along one direction."),
            ("ordinate", "ordinate", "Ordinate dimensions",
             "Ordinate: click the datum (0), then each point.")):
        cls = type("Tool_" + key, (_Run,), dict(key=key, mode=mode,
                                                title=title, hint=hint))
        out.append(cls(win))
    return out


#: rows for blueprint.ANNOTATE
ANNOTATE = (
    ("baseline", "mdi.format-align-left", "Baseline dimensions", "",
     "Several dimensions from ONE base edge, stacked — how a machinist "
     "measures from a datum.",
     "Click the base point, then each point; right-click finishes."),
    ("chain", "mdi.dots-horizontal-circle-outline", "Chain dimensions",
     "", "Dimensions end to end in one line.",
     "Click the points in order; right-click finishes."),
    ("ordinate", "mdi.format-list-numbered", "Ordinate dimensions", "",
     "Each point's distance from a datum, on its own leader, without "
     "dimension lines — for hole patterns.",
     "Click the datum (0), then each point; right-click finishes."),
)

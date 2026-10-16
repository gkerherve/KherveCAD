"""P&ID — piping and instrumentation diagrams (Qt-free model).

A `Diagram` is what File ▸ P&ID edits and the document saves (as
`DocumentModel.pid`, a plain dict): SYMBOLS placed on a sheet (a kind
from `pid_symbols`, a TAG such as P-101 numbered by the kind's prefix, a
label, rotation, mirror, kind-specific data and optionally the name of
the 3D part it stands for), LINES between symbol ports, routed
orthogonally (`route`) with a line number written from size, service and
material ("28-HW-001-CU"), and free NOTES.

Line kinds follow ISO 10628 / ISA: process (main, thick), secondary
(thin), electric signal (dashed), pneumatic signal (slashes), capillary
(crosses), data link (dash-dot). The SERVICE says what flows — heating
flow / return, hot and cold water, refrigerant hot gas / liquid /
suction, glycol, air, drain — and colours the line on screen.

Schedules come straight out of it: equipment list, valve list,
instrument index and line list (`schedules`), and `check` names what is
not connected or tagged twice. `from_model` starts a diagram from a 3D
model by recognising its parts by name.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import copy
import re

from . import pid_symbols as ps

SHEETS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0),
          "A2": (594.0, 420.0), "A1": (841.0, 594.0)}
DEFAULT_SHEET = "A3"
MARGIN = 10.0
TITLE_H = 36.0
GRID = 2.5
#: how far a line runs straight out of a port before it turns
STUB = 5.0

#: kind: (label, pen width mm, style)
LINE_KINDS = {
    "process": ("Process line (main)", 0.6, "solid"),
    "secondary": ("Process line (secondary)", 0.35, "solid"),
    "signal": ("Electric signal", 0.25, "dash"),
    "pneumatic": ("Pneumatic signal", 0.25, "slash"),
    "capillary": ("Capillary", 0.25, "cross"),
    "data": ("Data link", 0.25, "dashdot"),
}
#: service code: (meaning, screen colour)
SERVICES = {
    "HWF": ("Heating water flow", "#c62828"),
    "HWR": ("Heating water return", "#1565c0"),
    "DHW": ("Domestic hot water", "#ad1457"),
    "CW": ("Cold water (mains)", "#0277bd"),
    "RHG": ("Refrigerant hot gas", "#d84315"),
    "RL": ("Refrigerant liquid", "#ef6c00"),
    "RS": ("Refrigerant suction", "#5e92f3"),
    "R2P": ("Refrigerant two-phase", "#8e24aa"),
    "GLY": ("Glycol", "#2e7d32"),
    "AIR": ("Air", "#607d8b"),
    "DR": ("Drain / discharge", "#6d4c41"),
    "EL": ("Electrical", "#424242"),
    "": ("Unspecified", "#202020"),
}
MATERIAL_CODES = {"CU": "Copper", "SS": "Stainless steel",
                  "CS": "Carbon steel", "PEX": "PEX", "MLCP": "Multilayer",
                  "PVC": "PVC", "PP": "Polypropylene", "": ""}

VALVE_KINDS = {k for k, s in ps.SYMBOLS.items()
               if s.group in ("Valves", "Actuated valves", "Safety")}
INSTRUMENT_KINDS = {k for k, s in ps.SYMBOLS.items()
                    if s.group == "Instruments"} | {"pressure_switch"}


class PidError(ValueError):
    pass


def _snap(v, grid=GRID):
    return round(float(v) / grid) * grid


def route(p0, d0, p1, d1, stub=STUB):
    """Orthogonal points from port *p0* (leaving along *d0*) to port
    *p1* (entered against *d1*): straight out of each port, then one or
    two bends."""
    dx = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
    a0, a1 = dx.get(d0, (1, 0)), dx.get(d1, (-1, 0))
    s = (p0[0] + a0[0] * stub, p0[1] + a0[1] * stub)
    e = (p1[0] + a1[0] * stub, p1[1] + a1[1] * stub)
    pts = [tuple(p0), s]
    if abs(s[0] - e[0]) < 1e-6 or abs(s[1] - e[1]) < 1e-6:
        pass
    else:
        horizontal_out = a0[1] == 0
        horizontal_in = a1[1] == 0
        if horizontal_out and horizontal_in:
            mx = (s[0] + e[0]) / 2.0
            pts += [(mx, s[1]), (mx, e[1])]
        elif not horizontal_out and not horizontal_in:
            my = (s[1] + e[1]) / 2.0
            pts += [(s[0], my), (e[0], my)]
        elif horizontal_out:
            pts.append((e[0], s[1]))
        else:
            pts.append((s[0], e[1]))
    pts += [e, tuple(p1)]
    return simplify(pts)


def smart_route(p0, d0, p1, d1, boxes=(), segments=(), stub=STUB,
                stubs=None):
    """The best of several orthogonal routes from port *p0* to *p1*:
    straight, one bend either way, two bends through the middle or
    along either end, or round the outside — scored by length, bends,
    crossing a symbol's box (*boxes*, (x0, y0, x1, y1)), running along
    an existing line (*segments*) and crossing one."""
    dx = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}
    a0, a1 = dx.get(d0, (1, 0)), dx.get(d1, (-1, 0))
    k0, k1 = stubs if stubs else (stub, stub)
    s = (p0[0] + a0[0] * k0, p0[1] + a0[1] * k0)
    e = (p1[0] + a1[0] * k1, p1[1] + a1[1] * k1)
    mids = []
    if abs(s[0] - e[0]) < 1e-6 or abs(s[1] - e[1]) < 1e-6:
        mids.append([])
    mids += [[(e[0], s[1])], [(s[0], e[1])]]
    xs = {(s[0] + e[0]) / 2.0, s[0], e[0]}
    ys = {(s[1] + e[1]) / 2.0, s[1], e[1]}
    lo_x, hi_x = min(s[0], e[0]), max(s[0], e[0])
    lo_y, hi_y = min(s[1], e[1]), max(s[1], e[1])
    for k in (8.0, 16.0, 28.0):
        xs |= {lo_x - k, hi_x + k}
        ys |= {lo_y - k, hi_y + k}
    for x in xs:
        mids.append([(x, s[1]), (x, e[1])])
    for y in ys:
        mids.append([(s[0], y), (e[0], y)])
    # three-bend detours: out along y, across, back
    for x in xs:
        for y in ys:
            mids.append([(s[0], y), (x, y), (x, e[1])])
            mids.append([(x, s[1]), (x, y), (e[0], y)])
    best, score = None, None
    for mid in mids:
        pts = simplify([tuple(p0), s] + mid + [e, tuple(p1)])
        if not _orthogonal(pts):
            continue
        sc = _score(pts, boxes, segments)
        if score is None or sc < score:
            best, score = pts, sc
    return best or route(p0, d0, p1, d1, stub)


def _orthogonal(pts):
    return all(abs(a[0] - b[0]) < 1e-6 or abs(a[1] - b[1]) < 1e-6
               for a, b in zip(pts, pts[1:]))


def _seg_hits_box(a, b, box, pad=0.6):
    x0, y0, x1, y1 = box[0] + pad, box[1] + pad, box[2] - pad, \
        box[3] - pad
    if x0 >= x1 or y0 >= y1:
        return False
    sx0, sx1 = sorted((a[0], b[0]))
    sy0, sy1 = sorted((a[1], b[1]))
    return sx0 < x1 and sx1 > x0 and sy0 < y1 and sy1 > y0


def _score(pts, boxes, segments):
    length_ = sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
                  for a, b in zip(pts, pts[1:]))
    sc = length_ + 25.0 * (len(pts) - 2)
    legs = list(zip(pts, pts[1:]))
    p0, p1 = pts[0], pts[-1]
    for i, (a, b) in enumerate(legs):
        for box in boxes:
            if not _seg_hits_box(a, b, box):
                continue
            # the first and last legs leave and enter their own symbols
            own = (i == 0 and _touches(p0, box)) or \
                (i == len(legs) - 1 and _touches(p1, box))
            if not own:
                sc += 2000.0
        for c, d in segments:
            if _collinear_overlap(a, b, c, d):
                sc += 400.0
            elif _crosses(a, b, c, d):
                sc += 15.0
    # reversing straight back over the previous leg
    for (a, b), (c, d) in zip(legs, legs[1:]):
        if (b[0] - a[0]) * (d[0] - c[0]) < 0 or \
                (b[1] - a[1]) * (d[1] - c[1]) < 0:
            sc += 1000.0
    return sc


def _touches(p, box, tol=0.8):
    return box[0] - tol <= p[0] <= box[2] + tol and \
        box[1] - tol <= p[1] <= box[3] + tol


def _collinear_overlap(a, b, c, d):
    if abs(a[1] - b[1]) < 1e-6 and abs(c[1] - d[1]) < 1e-6 and \
            abs(a[1] - c[1]) < 1.0:
        lo, hi = sorted((a[0], b[0]))
        lo2, hi2 = sorted((c[0], d[0]))
        return min(hi, hi2) - max(lo, lo2) > 1.0
    if abs(a[0] - b[0]) < 1e-6 and abs(c[0] - d[0]) < 1e-6 and \
            abs(a[0] - c[0]) < 1.0:
        lo, hi = sorted((a[1], b[1]))
        lo2, hi2 = sorted((c[1], d[1]))
        return min(hi, hi2) - max(lo, lo2) > 1.0
    return False


def _crosses(a, b, c, d):
    h1 = abs(a[1] - b[1]) < 1e-6
    h2 = abs(c[1] - d[1]) < 1e-6
    if h1 == h2:
        return False
    if not h1:
        a, b, c, d = c, d, a, b
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((c[1], d[1]))
    return x0 < c[0] < x1 and y0 < a[1] < y1


def simplify(pts):
    """Drop repeated and collinear middle points."""
    out = []
    for p in pts:
        p = (round(float(p[0]), 3), round(float(p[1]), 3))
        if out and abs(out[-1][0] - p[0]) < 1e-6 and \
                abs(out[-1][1] - p[1]) < 1e-6:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        same_way = (b[0] - a[0]) * (c[0] - b[0]) + \
            (b[1] - a[1]) * (c[1] - b[1]) > 0
        # a straight run through b — never a turn back over itself,
        # which would draw the line across the symbol it enters
        if same_way and ((abs(a[0] - b[0]) < 1e-6 and
                          abs(b[0] - c[0]) < 1e-6) or
                         (abs(a[1] - b[1]) < 1e-6 and
                          abs(b[1] - c[1]) < 1e-6)):
            out.pop(i)
        else:
            i += 1
    return [list(p) for p in out]


def length(points):
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
               for a, b in zip(points, points[1:]))


class Diagram:
    def __init__(self, data=None):
        data = copy.deepcopy(data or {})
        self.sheet = data.get("sheet") if data.get("sheet") in SHEETS \
            else DEFAULT_SHEET
        self.fields = dict(data.get("fields") or {})
        self.symbols = [dict(s) for s in data.get("symbols") or []
                        if s.get("kind") in ps.SYMBOLS]
        self.lines = [dict(ln) for ln in data.get("lines") or []]
        self.notes = [dict(n) for n in data.get("notes") or []]
        self.colour_lines = bool(data.get("colour_lines", True))
        self.fields.setdefault("title", "Process and instrumentation "
                                        "diagram")
        self.fields.setdefault("number", "PID-001")
        self.fields.setdefault("revision", "A")

    # -- saving
    def to_dict(self):
        return copy.deepcopy({
            "sheet": self.sheet, "fields": self.fields,
            "symbols": self.symbols, "lines": self.lines,
            "notes": self.notes, "colour_lines": self.colour_lines})

    @property
    def size(self):
        return SHEETS[self.sheet]

    # -- ids and tags
    def _next_id(self, prefix, items):
        nums = [int(i["id"][1:]) for i in items
                if str(i.get("id", ""))[1:].isdigit()]
        return f"{prefix}{max(nums, default=0) + 1}"

    def next_tag(self, prefix):
        if not prefix:
            return ""
        nums = []
        for s in self.symbols:
            m = re.fullmatch(re.escape(prefix) + r"-(\d+)",
                             str(s.get("tag", "")))
            if m:
                nums.append(int(m.group(1)))
        return f"{prefix}-{max(nums, default=100) + 1}"

    def symbol(self, sid):
        for s in self.symbols:
            if s["id"] == sid or s.get("tag") == sid:
                return s
        raise PidError(f"no symbol {sid!r}")

    def line(self, lid):
        for ln in self.lines:
            if ln["id"] == lid or ln.get("number") == lid:
                return ln
        raise PidError(f"no line {lid!r}")

    # -- symbols
    def add_symbol(self, kind, x, y, tag=None, label="", rot=0,
                   mirror=False, data=None, node=""):
        if kind not in ps.SYMBOLS:
            raise PidError(f"unknown symbol {kind!r}; see the symbol list")
        sym = ps.SYMBOLS[kind]
        s = {"id": self._next_id("s", self.symbols), "kind": kind,
             "x": _snap(x), "y": _snap(y), "rot": int(rot) % 360,
             "mirror": bool(mirror),
             "tag": sym.prefix and self.next_tag(sym.prefix)
             if tag is None else str(tag),
             "label": str(label or ""), "data": dict(data or {}),
             "node": str(node or "")}
        if kind == "boundary":
            s["data"].setdefault("w", 60.0)
            s["data"].setdefault("h", 40.0)
        self.symbols.append(s)
        return s

    def set_symbol(self, sid, **changes):
        s = self.symbol(sid)
        for key, value in changes.items():
            if key in ("x", "y"):
                s[key] = _snap(value)
            elif key == "rot":
                s["rot"] = int(value) % 360
            elif key in ("mirror",):
                s[key] = bool(value)
            elif key in ("tag", "label", "node"):
                s[key] = str(value)
            elif key == "data":
                s["data"].update(dict(value))
            elif key == "kind":
                if value not in ps.SYMBOLS:
                    raise PidError(f"unknown symbol {value!r}")
                s["kind"] = value
            else:
                raise PidError(f"a symbol has no {key!r}")
        self.reroute(s["id"])
        return s

    def remove(self, ids):
        """Symbols (and the lines on them), lines or notes by id."""
        ids = set(ids)
        gone = {s["id"] for s in self.symbols if s["id"] in ids or
                s.get("tag") in ids}
        self.symbols = [s for s in self.symbols if s["id"] not in gone]
        self.lines = [ln for ln in self.lines
                      if ln["id"] not in ids and
                      ln.get("number") not in ids and
                      ln.get("from", {}).get("symbol") not in gone and
                      ln.get("to", {}).get("symbol") not in gone]
        self.notes = [n for n in self.notes if n["id"] not in ids]

    def ports(self, s):
        return ps.port_points(s["kind"], s["x"], s["y"], s.get("rot", 0),
                              s.get("mirror", False))

    def port(self, end):
        """((x, y), direction) of a line end {symbol, port} or {x, y}."""
        if end.get("symbol"):
            s = self.symbol(end["symbol"])
            got = self.ports(s).get(end.get("port"))
            if got is None:
                raise PidError(f"{s.get('tag') or s['id']} has no port "
                               f"{end.get('port')!r}; it has "
                               f"{sorted(ps.SYMBOLS[s['kind']].ports)}")
            return got
        return (float(end.get("x", 0)), float(end.get("y", 0))), \
            end.get("dir", "r")

    def nearest_port(self, x, y, reach=4.0, exclude=None):
        best, dist = None, reach
        for s in self.symbols:
            if exclude and s["id"] in exclude:
                continue
            for name, ((px, py), _d) in self.ports(s).items():
                d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                if d <= dist:
                    best, dist = {"symbol": s["id"], "port": name}, d
        return best

    # -- lines
    def connect(self, a, b, kind="process", service="", size="",
                material="", number=None, label="", arrow=True,
                insulated=False, points=None):
        """A line from end *a* to end *b* — each {"symbol": id or tag,
        "port": name} or a free {"x", "y"}."""
        if kind not in LINE_KINDS:
            raise PidError(f"line kind is one of {sorted(LINE_KINDS)}")
        for end in (a, b):
            if end.get("symbol"):
                end["symbol"] = self.symbol(end["symbol"])["id"]
                self.port(end)
        ln = {"id": self._next_id("l", self.lines), "kind": kind,
              "from": dict(a), "to": dict(b), "service": str(service),
              "size": str(size), "material": str(material),
              "label": str(label), "arrow": bool(arrow),
              "insulated": bool(insulated), "auto": points is None}
        if kind == "process" or number:
            # a process line is numbered; a tap to an instrument is not
            ln["number"] = str(number) if number else self.next_line_number(
                service, size, material)
        ln["points"] = simplify(points) if points else self._route(ln)
        self.lines.append(ln)
        return ln

    def next_line_number(self, service="", size="", material=""):
        n = 1 + sum(1 for ln in self.lines if ln.get("number"))
        parts = [str(size) if size else "", str(service) or "P",
                 f"{n:03d}", str(material) if material else ""]
        return "-".join(p for p in parts if p)

    def set_line(self, lid, **changes):
        ln = self.line(lid)
        for key, value in changes.items():
            if key in ("service", "size", "material", "label", "number"):
                ln[key] = str(value)
            elif key in ("arrow", "insulated"):
                ln[key] = bool(value)
            elif key == "kind":
                if value not in LINE_KINDS:
                    raise PidError(f"line kind is one of {sorted(LINE_KINDS)}")
                ln["kind"] = value
            elif key == "points":
                ln["points"] = simplify(value)
                ln["auto"] = False
            else:
                raise PidError(f"a line has no {key!r}")
        return ln

    def _route(self, ln):
        (p0, d0), (p1, d1) = self.port(ln["from"]), self.port(ln["to"])
        boxes = [self.box(s) for s in self.symbols
                 if s["kind"] not in ("boundary",)]
        segments = [(tuple(a), tuple(b)) for other in self.lines
                    if other is not ln and other.get("id") != ln.get("id")
                    for a, b in zip(other.get("points") or [],
                                    (other.get("points") or [])[1:])]
        free0 = not ln["from"].get("symbol")
        free1 = not ln["to"].get("symbol")
        if free0:
            d0 = _toward(p0, p1)
        if free1:
            d1 = _toward(p1, p0)
        # a free end (a tee on another line) needs no stub of its own
        return smart_route(p0, d0, p1, d1, boxes, segments,
                           stubs=(0.0 if free0 else STUB,
                                  0.0 if free1 else STUB))

    def box(self, s):
        if s["kind"] == "boundary":
            w = float((s.get("data") or {}).get("w", 60))
            h = float((s.get("data") or {}).get("h", 40))
            return (s["x"] - w / 2, s["y"] - h / 2, s["x"] + w / 2,
                    s["y"] + h / 2)
        return ps.bounds(s["kind"], s["x"], s["y"], s.get("rot", 0),
                         s.get("mirror", False))

    def reroute(self, sid=None):
        """Re-route the automatic lines on symbol *sid* (all when None);
        a hand-shaped line keeps its middle and has its ends moved."""
        for ln in self.lines:
            ends = (ln.get("from", {}).get("symbol"),
                    ln.get("to", {}).get("symbol"))
            if sid is not None and sid not in ends:
                continue
            if ln.get("auto", True) or len(ln.get("points") or []) < 2:
                ln["points"] = self._route(ln)
            else:
                pts = ln["points"]
                (p0, _d0), (p1, _d1) = self.port(ln["from"]), \
                    self.port(ln["to"])
                pts[0], pts[-1] = list(p0), list(p1)
                # keep the first and last legs straight
                if len(pts) > 2:
                    a, b = pts[0], pts[1]
                    if abs(b[0] - a[0]) < abs(b[1] - a[1]):
                        b[0] = a[0]
                    else:
                        b[1] = a[1]
                    a, b = pts[-1], pts[-2]
                    if abs(b[0] - a[0]) < abs(b[1] - a[1]):
                        b[0] = a[0]
                    else:
                        b[1] = a[1]
                ln["points"] = simplify(pts)

    def move(self, sid, x, y):
        s = self.symbol(sid)
        s["x"], s["y"] = _snap(x), _snap(y)
        self.reroute(s["id"])

    # -- notes
    def add_note(self, text, x, y, size=3.0):
        n = {"id": self._next_id("n", self.notes), "text": str(text),
             "x": float(x), "y": float(y), "size": float(size)}
        self.notes.append(n)
        return n

    # -- what it says
    def junctions(self):
        """Points where a line ENDS on the middle of another line — a
        tee, drawn as a dot."""
        out = []
        for ln in self.lines:
            for end in (ln["points"][0], ln["points"][-1]) if \
                    ln.get("points") else ():
                for other in self.lines:
                    if other is ln:
                        continue
                    pts = other.get("points") or []
                    for a, b in zip(pts, pts[1:]):
                        if _on_segment(end, a, b) and end not in (
                                list(a), list(b)):
                            out.append(tuple(end))
        return sorted(set(out))

    def check(self):
        """Problems: an unconnected port of a process symbol, a tag used
        twice, a line whose end symbol has gone."""
        problems = []
        used = {}
        for ln in self.lines:
            for end in (ln.get("from", {}), ln.get("to", {})):
                if end.get("symbol"):
                    used.setdefault(end["symbol"], set()).add(
                        end.get("port"))
        tags = {}
        for s in self.symbols:
            if s.get("tag"):
                tags.setdefault(s["tag"], []).append(s["id"])
            sym = ps.SYMBOLS[s["kind"]]
            if s["kind"] in ("boundary", "off_page", "fan", "motor"):
                continue        # air side or no process port
            free = [p for p in sym.ports if p not in used.get(s["id"],
                                                              set())]
            if len(sym.ports) and len(free) == len(sym.ports):
                problems.append(f"{s.get('tag') or sym.label}: not "
                                "connected")
            elif free and sym.group not in ("Vessels & tanks",
                                            "Equipment") \
                    and len(sym.ports) <= 3:
                problems.append(f"{s.get('tag') or sym.label}: port(s) "
                                f"{', '.join(free)} open")
        for tag, ids in tags.items():
            if len(ids) > 1:
                problems.append(f"tag {tag} used {len(ids)} times")
        return problems

    def schedules(self):
        """Equipment list, valve list, instrument index, line list."""
        by_id = {s["id"]: s for s in self.symbols}

        def name(end):
            s = by_id.get(end.get("symbol"))
            if s is None:
                return "—"
            return f"{s.get('tag') or ps.SYMBOLS[s['kind']].label} " \
                   f"({end.get('port')})"
        equipment, valves, instruments = [], [], []
        for s in sorted(self.symbols, key=lambda s: str(s.get("tag"))):
            sym = ps.SYMBOLS[s["kind"]]
            row = {"tag": s.get("tag", ""), "type": sym.label,
                   "description": s.get("label", ""),
                   "data": "; ".join(f"{k} {v}" for k, v in
                                     (s.get("data") or {}).items() if v),
                   "part": s.get("node", "")}
            if s["kind"] in ("boundary", "off_page"):
                continue
            if s["kind"] in INSTRUMENT_KINDS:
                letters = re.match(r"[A-Z]+", str(s.get("tag", "")))
                row["function"] = _isa_meaning(letters.group(0)
                                               if letters else "")
                instruments.append(row)
            elif s["kind"] in VALVE_KINDS:
                valves.append(row)
            else:
                equipment.append(row)
        lines = []
        for ln in self.lines:
            if ln.get("kind") not in ("process", "secondary"):
                continue
            lines.append({
                "number": ln.get("number", ""), "service":
                    SERVICES.get(ln.get("service", ""), (ln.get("service"),
                                                         ""))[0],
                "size": ln.get("size", ""),
                "material": MATERIAL_CODES.get(ln.get("material", ""),
                                               ln.get("material", "")),
                "from": name(ln.get("from", {})),
                "to": name(ln.get("to", {})),
                "insulated": "yes" if ln.get("insulated") else "",
                "label": ln.get("label", "")})
        return {"equipment": equipment, "valves": valves,
                "instruments": instruments, "lines": lines}


def _toward(p, q):
    """The direction a free line end leaves in: towards the other end
    along the longer axis."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    if abs(dx) >= abs(dy):
        return "r" if dx >= 0 else "l"
    return "d" if dy >= 0 else "u"


def _on_segment(p, a, b, tol=0.05):
    x, y = p
    if abs(a[0] - b[0]) < 1e-6:
        return abs(x - a[0]) < tol and min(a[1], b[1]) - tol <= y <= \
            max(a[1], b[1]) + tol
    if abs(a[1] - b[1]) < 1e-6:
        return abs(y - a[1]) < tol and min(a[0], b[0]) - tol <= x <= \
            max(a[0], b[0]) + tol
    return False


#: ISA-5.1 first and succeeding letters
_FIRST = {"A": "Analysis", "F": "Flow", "L": "Level", "P": "Pressure",
          "T": "Temperature", "H": "Hand", "S": "Speed", "J": "Power",
          "E": "Voltage", "I": "Current", "Z": "Position", "Q": "Quantity",
          "D": "Density", "M": "Moisture", "V": "Vibration", "W": "Weight",
          "U": "Multivariable", "K": "Time"}
_NEXT = {"I": "indicator", "T": "transmitter", "E": "element",
         "C": "controller", "S": "switch", "A": "alarm", "V": "valve",
         "R": "recorder", "Q": "totaliser", "G": "gauge / glass",
         "Y": "relay", "D": "differential", "H": "high", "L": "low",
         "Z": "safety"}


def _isa_meaning(letters):
    if not letters:
        return ""
    first = _FIRST.get(letters[0], letters[0])
    rest = [_NEXT.get(c, c) for c in letters[1:]]
    return " ".join([first] + rest)


# ── a start from the 3D model ──────────────────────────────────────

#: words in a part's name -> symbol kind (first match)
_KEYWORDS = (
    ("expansion valve", "expansion_valve"), ("eev", "expansion_valve"),
    ("reversing", "four_way_valve"), ("4-way", "four_way_valve"),
    ("4 way", "four_way_valve"), ("diverter", "diverter_valve"),
    ("relief", "relief_valve"), ("safety valve", "relief_valve"),
    ("isolation", "ball_valve"), ("check valve", "check_valve"),
    ("solenoid", "solenoid_valve"), ("compressor", "compressor"),
    ("accumulator", "accumulator"), ("plate heat", "plate_hx"),
    ("heat exchanger", "plate_hx"), ("condenser", "plate_hx"),
    ("evaporator", "coil"), ("coil", "coil"), ("fan", "fan"),
    ("pump", "pump_inline"), ("expansion vessel", "expansion_vessel"),
    ("vessel", "expansion_vessel"), ("buffer", "tank"),
    ("cylinder", "cylinder"), ("tank", "tank"), ("radiator", "radiator"),
    ("underfloor", "ufh"), ("filter drier", "filter_drier"),
    ("drier", "filter_drier"), ("magnetic filter", "magnetic_filter"),
    ("strainer", "strainer"), ("filter", "filter"),
    ("gauge", "pressure_gauge"), ("flow switch", "flow_switch"),
    ("air vent", "air_vent"), ("controller", "controller"),
    ("control box", "controller"), ("heater", "heater"),
    ("pressure switch", "pressure_switch"), ("sensor", "instrument"),
)


def kind_for(name):
    low = (name or "").lower()
    for word, kind in _KEYWORDS:
        if word in low:
            return kind
    return None


def from_model(model, diagram=None):
    """A new diagram holding a symbol for every part of the 3D model
    whose name (or a labelled piece's name) says what it is — laid out
    in rows to be connected. Returns (diagram, [(name, kind)])."""
    from .bom import build, piece_tag
    d = diagram or Diagram()
    b = build(model, "components")
    found, seen = [], set()
    for ln in b.flat():
        names = [ln.name]
        if ln.kind == "component" and ln.nodes:
            names = [piece_tag(ln.nodes[0]) or ln.name]
        for nm in names:
            kind = kind_for(nm)
            if kind is None or (nm.lower(), kind) in seen:
                continue
            seen.add((nm.lower(), kind))
            found.append((nm, kind))
    W, H = d.size
    x0, y0 = MARGIN + 30.0, MARGIN + 30.0
    x, y, row_h = x0, y0, 0.0
    for nm, kind in found:
        sym = ps.SYMBOLS[kind]
        if x + sym.w > W - MARGIN - 20.0:
            x, y = x0, y + row_h + 25.0
            row_h = 0.0
        d.add_symbol(kind, x + sym.w / 2.0, y + sym.h / 2.0,
                     label=nm, node=nm)
        x += sym.w + 25.0
        row_h = max(row_h, sym.h)
    return d, found

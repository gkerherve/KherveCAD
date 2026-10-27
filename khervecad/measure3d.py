"""Measure in 3D (2026-10-27) — SolidWorks' Measure: click one thing to
read its size, a second to read how far apart they are.

- one face: its area, a round face's radius / diameter;
- one edge: its length;
- two picks: the straight distance between the points, dX / dY / dZ, and
  — for two faces — the angle between them and, when they are parallel,
  the face-to-face distance; for two edges the angle between them.

The tool keeps picking (a third click starts again) until Esc. The
answer is shown on a card in the 3D view and in the status bar, and the
two points are joined by a line (the view's overlay painter). `describe`
and `between` are the arithmetic, Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language


def _fmt(v):
    return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:g}"


def _area(tris):
    total = 0.0
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        cr = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
              u[0] * v[1] - u[1] * v[0]]
        total += math.sqrt(sum(x * x for x in cr)) / 2
    return total


def describe(pick, unit="mm"):
    """What one pick measures: a dict with ``text`` (lines)."""
    from . import refgeom, refgeom_ui
    lines = []
    out = dict(kind=pick["kind"], point=list(pick["pos"]))
    if pick["kind"] == "edge":
        seg = pick.get("seg") or [pick["pos"], pick["pos"]]
        out["length"] = math.dist(seg[0], seg[1])
        lines.append(f"Edge length: {_fmt(out['length'])} {unit}")
    else:
        flat = pick.get("tris") or []
        if flat:
            out["area"] = _area(flat)
        part = pick.get("part_tris") or []
        round_ = None
        if part:
            region = refgeom_ui.smooth_region(part, pick["pos"])
            if len(region) > len(flat) + 2:
                try:
                    p, d = refgeom.axis_of_cylinder(region)
                    rs = [_dist_line(v, p, d) for t in region for v in t]
                    round_ = sum(rs) / len(rs)
                    out["area"] = _area(region)
                except ValueError:
                    round_ = None
        if round_:
            out["radius"] = round_
            lines.append(f"Radius: {_fmt(round_)} {unit}  ·  Ø "
                         f"{_fmt(2 * round_)} {unit}")
        if "area" in out:
            lines.append(f"Face area: {_fmt(out['area'])} {unit}²")
        out["normal"] = list(pick.get("dir") or [0, 0, 1])
    out["text"] = lines
    return out


def _dist_line(v, p, d):
    w = [v[i] - p[i] for i in range(3)]
    t = sum(w[i] * d[i] for i in range(3))
    return math.sqrt(max(sum(x * x for x in w) - t * t, 0.0))


def _angle(a, b):
    la = math.sqrt(sum(x * x for x in a)) or 1.0
    lb = math.sqrt(sum(x * x for x in b)) or 1.0
    c = sum(a[i] * b[i] for i in range(3)) / (la * lb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def between(first, second, unit="mm"):
    """What two picks measure (each from `describe`)."""
    a, b = first["point"], second["point"]
    d = [b[i] - a[i] for i in range(3)]
    out = dict(distance=math.dist(a, b), delta=d)
    lines = [f"Distance: {_fmt(out['distance'])} {unit}",
             f"dX {_fmt(d[0])}  dY {_fmt(d[1])}  dZ {_fmt(d[2])}"]
    if first["kind"] == "face" and second["kind"] == "face":
        ang = _angle(first["normal"], second["normal"])
        out["angle"] = min(ang, 180.0 - ang)
        if out["angle"] < 0.01:
            n = first["normal"]
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            out["normal_distance"] = abs(sum(d[i] * n[i] for i in range(3))
                                         / ln)
            lines.insert(0, f"Face to face: "
                         f"{_fmt(out['normal_distance'])} {unit} "
                         "(parallel)")
        else:
            lines.append(f"Angle between faces: {_fmt(out['angle'])}°")
    elif first["kind"] == "edge" and second["kind"] == "edge":
        sa = first.get("seg_dir")
        sb = second.get("seg_dir")
        if sa and sb:
            ang = _angle(sa, sb)
            out["angle"] = min(ang, 180.0 - ang)
            lines.append(f"Angle between edges: {_fmt(out['angle'])}°")
    out["text"] = lines
    return out


# =================================================================== Qt

def start(window):
    from . import refgeom_ui
    state = window._measure = dict(picks=[], line=None, card=None)
    if not getattr(window, "_measure_painter", False):
        window.view3d.overlay_painters.append(
            lambda painter, project: paint(window, painter, project))
        window._measure_painter = True
    unit = getattr(window.model, "unit", "mm")

    def got(desc, node, tris):
        if getattr(window, "_measure", None) is not state:
            return
        pick = dict(desc)
        pick["part_tris"] = tris
        seg = desc.get("seg")
        if seg:
            pick["seg_dir"] = [seg[1][i] - seg[0][i] for i in range(3)]
        info = describe(pick, unit)
        info.update(kind=pick["kind"], seg_dir=pick.get("seg_dir"))
        if len(state["picks"]) >= 2:
            state["picks"] = []
        state["picks"].append(info)
        lines = list(info["text"])
        if len(state["picks"]) == 2:
            both = between(state["picks"][0], info, unit)
            lines = both["text"] + [""] + state["picks"][0]["text"] + \
                lines
            state["line"] = (state["picks"][0]["point"], info["point"])
            state["result"] = both
        else:
            state["line"] = None
            state["result"] = info
        show(window, lines)
        refgeom_ui._pick(window, "Measure: click another face or edge "
                         "(Esc ends)", got)

    ok = refgeom_ui._pick(window, "Measure: click a face or an edge",
                          got)
    if not ok:
        window._measure = None
    return ok


def show(window, lines):
    from PyQt5.QtWidgets import QLabel
    state = getattr(window, "_measure", None)
    if state is None:
        return
    card = state.get("card")
    if card is None:
        card = QLabel(window.view3d)
        card.setObjectName("measure_card")
        card.setStyleSheet(
            "#measure_card { background: rgba(255,255,255,240); color: "
            "#202020; border: 1px solid #3c78dc; border-radius: 5px; "
            "padding: 6px 9px; font-size: 12px; }")
        state["card"] = card
    card.setText("<b>" + language.tr("Measure") + "</b><br>"
                 + "<br>".join(lines))
    card.adjustSize()
    card.move(max(8, window.view3d.width() - card.width() - 12), 52)
    card.show()
    window.statusBar().showMessage("  ·  ".join(x for x in lines if x),
                                   15000)
    window.view3d.update()


def stop(window):
    state = getattr(window, "_measure", None)
    window._measure = None
    if state and state.get("card") is not None:
        state["card"].deleteLater()
    window.view3d.update()


def paint(window, painter, project):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPen
    state = getattr(window, "_measure", None)
    if not state:
        return
    if window.view3d._pick_cb is None and state.get("card") is not None:
        stop(window)                           # Esc ended the picking
        return
    painter.save()
    try:
        painter.setPen(QPen(QColor(60, 120, 220), 2))
        for info in state["picks"]:
            p = project(info["point"])
            if p is not None and p[2] > 0:
                painter.drawEllipse(QPointF(p[0], p[1]), 4.0, 4.0)
        if state.get("line"):
            a, b = (project(q) for q in state["line"])
            if a is not None and b is not None and a[2] > 0 \
                    and b[2] > 0:
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
                res = state.get("result") or {}
                if "distance" in res:
                    painter.drawText(QPointF((a[0] + b[0]) / 2 + 6,
                                             (a[1] + b[1]) / 2 - 6),
                                     _fmt(res["distance"]))
    finally:
        painter.restore()

"""Library ▸ Vacuum & UHV ▸ Chamber Designer… — draw a UHV chamber.

A non-modal window over `chamber_design`:

- **Chamber** — sphere, cylinder or cube, its size and wall, a mu-metal
  liner (gap, thickness), how it is TURNED (rx, ry, rz), the height of
  its focal point above the floor and which bench it stands on; or start
  from a preset (preparation, XPS analysis, two-level, load lock, cube).
- **Port map** — every port drawn where it points: an unfolded map of
  the sphere of directions (azimuth φ across, polar angle θ down, the
  flange drawn as the patch it covers, clashes in red) beside a top and
  a side view of the chamber with its ports. Click a port to select it,
  drag it on the map to aim it, double-click empty map to add one there.
- **Ports** — a table: name, CF or KF flange, θ, φ, the focal point it
  aims at (mm up the manipulator axis, so a tall chamber can have a
  preparation level and an analysis level), length (focal point to
  sealing face), the accessory, which size row of it (variant) and the
  spin of that accessory about the port axis.

Build adds the chamber to the document as one assembly; Update replaces
the last one built. Specs save to and load from JSON.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import math

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                             QDialog, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QGroupBox, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QSplitter, QTableWidget,
                             QVBoxLayout, QWidget)

from . import chamber_design as cd

#: accessory -> map colour
COLOURS = {"open": "#9aa0a6", "blank": "#b9bfc7", "viewport": "#6fc3df",
           "ion_gauge": "#e0a040", "gauge_head": "#e0a040",
           "sputter_gun": "#d96c3f", "leed": "#7fe07a",
           "analyser": "#8c6bd6", "xray": "#d6c24b", "evaporator": "#c47a4a",
           "manipulator": "#3f8fd9", "manipulator_cryo": "#3f8fd9",
           "manipulator_transax": "#3f8fd9", "manipulator_hpt": "#3f8fd9",
           "manipulator_uhvd": "#3f8fd9", "mono": "#d6c24b",
           "transfer_flag": "#2fb3a0", "transfer_pts": "#2fb3a0",
           "carousel": "#2fb3a0", "wobble": "#5fa35f", "rga": "#b35f9a",
           "door": "#9aa0a6", "kf_blank": "#b9bfc7", "pirani": "#e0a040"}

COLUMNS = ("Name", "Flange", "θ (°)", "φ (°)", "Focus", "Length",
           "Accessory", "Variant", "Spin (°)")
SPINS = {"theta": 2, "phi": 3, "focus": 4, "length": 5, "spin": 8}


class PortMap(QWidget):
    """The drawing: an unfolded direction map plus top and side views."""

    selected = pyqtSignal(int)
    moved = pyqtSignal(int, float, float)          # index, theta, phi
    add_at = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spec = cd.new_spec()
        self.current = -1
        self.bad = set()
        self._drag = -1
        self.setMinimumSize(560, 300)
        self.setMouseTracking(True)

    # ------------------------------------------------------------ layout
    def _map_rect(self):
        w, h = self.width(), self.height()
        return QRectF(40, 24, w * 0.58 - 50, h - 50)

    def _view_rects(self):
        w, h = self.width(), self.height()
        x0 = w * 0.58 + 10
        side = min(w - x0 - 10, (h - 40) / 2.0)
        return (QRectF(x0, 20, side, side),
                QRectF(x0, 30 + side, side, side))

    def _to_map(self, theta, phi):
        r = self._map_rect()
        return QPointF(r.left() + r.width() * (phi % 360.0) / 360.0,
                       r.top() + r.height() * theta / 180.0)

    def _from_map(self, pt):
        r = self._map_rect()
        phi = (pt.x() - r.left()) / r.width() * 360.0
        theta = (pt.y() - r.top()) / r.height() * 180.0
        return (min(max(theta, 0.0), 180.0), phi % 360.0)

    def _extent(self):
        s = self.spec
        far = max([p["length"] + 40.0 for p in s["ports"]]
                  + [s["radius"] * 1.3,
                     s["height"] * 0.65 if s["body"] == "cylinder" else 0])
        return far

    # ------------------------------------------------------------- paint
    def paintEvent(self, _event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        qp.fillRect(self.rect(), pal.base())
        text = pal.text().color()
        self._paint_map(qp, text)
        top, side = self._view_rects()
        self._paint_view(qp, top, "Top view (looking down)", text,
                         lambda d: (d[0], -d[1]))
        self._paint_view(qp, side, "Side view (chamber axis up)", text,
                         lambda d: (d[0], -d[2]))
        qp.end()

    def _paint_map(self, qp, text):
        r = self._map_rect()
        qp.setPen(QPen(text, 1))
        qp.setFont(QFont(qp.font().family(), 8))
        qp.drawText(QPointF(r.left(), r.top() - 8),
                    "Port directions — φ across, θ down (drag to aim, "
                    "double-click to add)")
        grid = QColor(text)
        grid.setAlpha(50)
        for k in range(0, 361, 45):
            p = self._to_map(0, k)
            qp.setPen(QPen(grid, 1))
            qp.drawLine(p, self._to_map(180, k))
            qp.setPen(QPen(text, 1))
            qp.drawText(QPointF(p.x() - 8, r.bottom() + 14), f"{k}")
        for k in range(0, 181, 30):
            p = self._to_map(k, 0)
            qp.setPen(QPen(grid, 1))
            qp.drawLine(p, self._to_map(k, 360))
            qp.setPen(QPen(text, 1))
            qp.drawText(QPointF(r.left() - 30, p.y() + 4), f"{k}°")
        for i, port in enumerate(self.spec["ports"]):
            self._paint_patch(qp, i, port)

    def _paint_patch(self, qp, i, port):
        """A port's flange as the patch of directions it covers: a circle
        of its half-angle, drawn with the azimuth stretched by 1/sin θ."""
        r = self._map_rect()
        ha = cd.half_angle(port)
        c = self._to_map(port["theta"], port["phi"])
        ry = r.height() * ha / 180.0
        s = max(math.sin(math.radians(port["theta"])), 0.05)
        rx = min(r.width() * ha / 360.0 / s, r.width() / 2.0)
        colour = QColor(COLOURS.get(port["accessory"], "#b9bfc7"))
        fill = QColor(colour)
        fill.setAlpha(110)
        pen = QPen(QColor("#d0342c") if i in self.bad else colour.darker(140),
                   3 if i == self.current else 1.5)
        qp.setPen(pen)
        qp.setBrush(QBrush(fill))
        for dx in (-r.width(), 0.0, r.width()):          # wrap round φ
            cx = c.x() + dx
            if cx + rx < r.left() or cx - rx > r.right():
                continue
            qp.save()
            qp.setClipRect(r)
            qp.drawEllipse(QPointF(cx, c.y()), rx, ry)
            qp.restore()
        qp.setPen(QPen(self.palette().text().color(), 1))
        qp.drawText(QPointF(c.x() + 4, c.y() + 4), port["name"])

    def _paint_view(self, qp, rect, title, text, project):
        qp.setPen(QPen(text, 1))
        qp.drawText(QPointF(rect.left(), rect.top() + 2), title)
        scale = rect.width() / 2.0 / self._extent()
        cx, cy = rect.center().x(), rect.center().y() + 6
        s = self.spec

        def at(point):
            """A chamber-frame point on the view."""
            u, v = project(point)
            return QPointF(cx + u * scale, cy + v * scale)
        R = s["radius"] * scale
        top_view = "Top" in title
        qp.setBrush(QBrush(QColor(185, 191, 199, 90)))
        qp.setPen(QPen(text, 1.5))
        if s["body"] == "sphere" or (s["body"] == "cylinder" and top_view):
            qp.drawEllipse(QPointF(cx, cy), R, R)
        elif s["body"] == "cylinder":
            H = s["height"] / 2.0 * scale
            qp.drawRect(QRectF(cx - R, cy - H, 2 * R, 2 * H))
        else:
            qp.drawRect(QRectF(cx - R, cy - R, 2 * R, 2 * R))
        if s["liner"]:
            qp.setBrush(Qt.NoBrush)
            qp.setPen(QPen(QColor("#6f7a73"), 1, Qt.DashLine))
            L = (s["radius"] - s["wall"] - s["liner_gap"]) * scale
            qp.drawEllipse(QPointF(cx, cy), L, L)
        order = sorted(range(len(s["ports"])),
                       key=lambda i: i == self.current)
        for i in order:
            p = s["ports"][i]
            d = cd.direction(p["theta"], p["phi"])
            o = (0.0, 0.0, p["focus"])
            row = cd.flange_row(p["flange"])
            colour = QColor(COLOURS.get(p["accessory"], "#b9bfc7"))
            width = 3 if i == self.current else 1.5
            start = cd.wall_distance(s, p) * 0.7
            a0 = at(tuple(o[k] + d[k] * start for k in range(3)))
            end = at(tuple(o[k] + d[k] * p["length"] for k in range(3)))
            qp.setPen(QPen(colour.darker(130),
                           max(row["tube_od"] * scale, 2.0)))
            qp.drawLine(a0, end)
            u, v = project(d)
            n = math.hypot(u, v)
            if n > 0.05:                       # the flange as a bar
                fx, fy = -v / n, u / n
                fw = row["flange_od"] / 2.0 * scale * n
                qp.setPen(QPen(QColor("#d0342c") if i in self.bad
                               else colour.darker(160), width + 2))
                qp.drawLine(QPointF(end.x() + fx * fw, end.y() + fy * fw),
                            QPointF(end.x() - fx * fw, end.y() - fy * fw))
            else:                              # end-on: a circle
                qp.setPen(QPen(colour.darker(160), width))
                qp.setBrush(Qt.NoBrush)
                fr = row["flange_od"] / 2.0 * scale
                qp.drawEllipse(end, fr, fr)
        qp.setPen(QPen(QColor("#d0342c"), 1.5))
        for f in sorted({p["focus"] for p in s["ports"]} or {0.0}):
            c = at((0.0, 0.0, f))
            qp.drawLine(QPointF(c.x() - 5, c.y()), QPointF(c.x() + 5, c.y()))
            qp.drawLine(QPointF(c.x(), c.y() - 5), QPointF(c.x(), c.y() + 5))
            if f and not top_view:
                qp.drawText(QPointF(c.x() + 8, c.y() + 4), f"{f:g}")
        if not top_view and (s["rx"] or s["ry"] or s["rz"]):
            qp.setPen(QPen(text, 1))
            qp.drawText(QPointF(rect.left(), rect.bottom()),
                        f"turned {s['rx']:g}°, {s['ry']:g}°, {s['rz']:g}° "
                        "(chamber frame shown)")

    # ------------------------------------------------------------- mouse
    def _hit(self, pos):
        best, dist = -1, 1e9
        for i, p in enumerate(self.spec["ports"]):
            c = self._to_map(p["theta"], p["phi"])
            d = math.hypot(c.x() - pos.x(), c.y() - pos.y())
            if d < dist:
                best, dist = i, d
        return best if dist < 22 else -1

    def mousePressEvent(self, event):
        if not self._map_rect().contains(QPointF(event.pos())):
            return
        i = self._hit(event.pos())
        if i >= 0:
            self._drag = i
            self.selected.emit(i)

    def mouseMoveEvent(self, event):
        if self._drag >= 0 and event.buttons() & Qt.LeftButton:
            theta, phi = self._from_map(QPointF(event.pos()))
            step = 1.0 if event.modifiers() & Qt.ShiftModifier else 5.0
            theta = round(theta / step) * step
            phi = round(phi / step) * step % 360.0
            self.moved.emit(self._drag, theta, phi)

    def mouseReleaseEvent(self, _event):
        self._drag = -1

    def mouseDoubleClickEvent(self, event):
        pt = QPointF(event.pos())
        if self._map_rect().contains(pt) and self._hit(event.pos()) < 0:
            theta, phi = self._from_map(pt)
            self.add_at.emit(round(theta / 5.0) * 5.0,
                             round(phi / 5.0) * 5.0 % 360.0)


class ChamberDesigner(QDialog):
    """The non-modal Chamber Designer window."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Chamber Designer")
        self.setModal(False)
        self.resize(1180, 760)
        self.spec = cd.preset(next(iter(cd.PRESETS)))
        self.built = None
        self._loading = False
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        layout.addLayout(top)
        top.addWidget(self._body_box())
        self.map = PortMap()
        self.map.selected.connect(self._select_row)
        self.map.moved.connect(self._drag_port)
        self.map.add_at.connect(lambda th, ph: self._add_port(th, ph))
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.map)
        split.addWidget(self._ports_box())
        split.setSizes([400, 300])
        top.addWidget(split, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.info)
        buttons = QHBoxLayout()
        for label, slot in (("Load…", self.load), ("Save…", self.save)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        buttons.addStretch(1)
        self.update_btn = QPushButton("Update last build")
        self.update_btn.clicked.connect(lambda: self.build_now(True))
        self.update_btn.setEnabled(False)
        self.go = QPushButton("Build")
        self.go.setDefault(True)
        self.go.clicked.connect(lambda: self.build_now(False))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        for b in (self.update_btn, self.go, close):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self._load_spec(self.spec)

    # ------------------------------------------------------------ panels
    def _body_box(self):
        box = QGroupBox("Chamber")
        form = QFormLayout(box)
        self.preset = QComboBox()
        self.preset.addItem("Start from a preset…", "")
        for name in cd.PRESETS:
            self.preset.addItem(name, name)
        self.preset.activated.connect(self._use_preset)
        form.addRow(self.preset)
        self.name = QLineEdit()
        form.addRow("Name:", self.name)
        self.body = QComboBox()
        for b in cd.BODIES:
            self.body.addItem(b.capitalize(), b)
        form.addRow("Body:", self.body)

        def spin(lo, hi, step=1.0, suffix=" mm"):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(1)
            s.setSuffix(suffix)
            return s
        self.radius = spin(20.0, 1000.0, 5.0)
        form.addRow("Radius (half-width):", self.radius)
        self.height = spin(20.0, 3000.0, 10.0)
        form.addRow("Height (cylinder):", self.height)
        self.wall = spin(0.5, 50.0, 0.5)
        form.addRow("Wall:", self.wall)
        self.liner = QCheckBox("Mu-metal liner inside")
        form.addRow(self.liner)
        self.liner_gap = spin(1.0, 100.0, 1.0)
        form.addRow("Liner gap:", self.liner_gap)
        self.liner_t = spin(0.2, 10.0, 0.1)
        form.addRow("Liner thickness:", self.liner_t)
        self.bench = QComboBox()
        for key, label in cd.BENCHES.items():
            self.bench.addItem(label, key)
        form.addRow("Bench:", self.bench)
        self.beam = spin(0.0, 3000.0, 10.0)
        form.addRow("Focal point height:", self.beam)
        self.bench_w = spin(0.0, 4000.0, 50.0)
        self.bench_w.setSpecialValueText("automatic")
        form.addRow("Bench width:", self.bench_w)
        self.bench_d = spin(0.0, 4000.0, 50.0)
        self.bench_d.setSpecialValueText("automatic")
        form.addRow("Bench depth:", self.bench_d)
        turn = QHBoxLayout()
        self.rx, self.ry, self.rz = (spin(-180.0, 180.0, 5.0, " °")
                                     for _k in range(3))
        for label, w in (("rx", self.rx), ("ry", self.ry), ("rz", self.rz)):
            w.setMinimumWidth(76)
            w.setDecimals(0)
            turn.addWidget(QLabel(label))
            turn.addWidget(w)
        form.addRow("Turn the chamber:", turn)
        hint = QLabel("θ is measured from the chamber's own axis (0° up "
                      "it, 90° equator, 180° down), φ from +X. A port aims "
                      "at its focal point — a height on the manipulator "
                      "axis — and its length is measured from there to the "
                      "sealing face; a tool on it reaches that point. The "
                      "chamber and everything on it turn together; the "
                      "bench stays level.")
        hint.setWordWrap(True)
        form.addRow(hint)
        for w in (self.radius, self.height, self.wall, self.liner_gap,
                  self.liner_t, self.beam, self.bench_w, self.bench_d,
                  self.rx, self.ry, self.rz):
            w.valueChanged.connect(self._body_changed)
        for w in (self.body, self.bench):
            w.currentIndexChanged.connect(self._body_changed)
        self.name.textChanged.connect(self._body_changed)
        self.liner.toggled.connect(self._body_changed)
        box.setMaximumWidth(320)
        return box

    def _ports_box(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._row_changed)
        v.addWidget(self.table)
        row = QHBoxLayout()
        for label, slot in (("Add port", lambda: self._add_port(90.0, 0.0)),
                            ("Duplicate", self._duplicate),
                            ("Remove", self._remove),
                            ("Shortest length", self._shortest)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        return box

    # -------------------------------------------------------------- spec
    def _load_spec(self, spec):
        self._loading = True
        self.spec = cd.normalise(spec)
        s = self.spec
        self.name.setText(s["name"])
        self.body.setCurrentIndex(max(self.body.findData(s["body"]), 0))
        self.radius.setValue(s["radius"])
        self.height.setValue(s["height"])
        self.wall.setValue(s["wall"])
        self.liner.setChecked(bool(s["liner"]))
        self.liner_gap.setValue(s["liner_gap"])
        self.liner_t.setValue(s["liner_thickness"])
        self.bench.setCurrentIndex(max(self.bench.findData(s["bench"]), 0))
        self.beam.setValue(s["beam_height"])
        self.bench_w.setValue(s["bench_width"])
        self.bench_d.setValue(s["bench_depth"])
        for key, w in (("rx", self.rx), ("ry", self.ry), ("rz", self.rz)):
            w.setValue(s[key])
        self._fill_table()
        self._loading = False
        self._refresh()

    def _fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, p in enumerate(self.spec["ports"]):
            self.table.insertRow(i)
            self._fill_row(i, p)
        self.table.blockSignals(False)

    def _fill_row(self, i, p):
        name = QLineEdit(p["name"])
        name.textChanged.connect(lambda t, r=i: self._set(r, "name", t))
        self.table.setCellWidget(i, 0, name)
        flange = QComboBox()
        for f in cd.FLANGES:
            flange.addItem(f, f)
        flange.setCurrentIndex(flange.findData(p["flange"]))
        flange.currentIndexChanged.connect(
            lambda _i, r=i, w=flange: self._set(r, "flange", w.currentData()))
        self.table.setCellWidget(i, 1, flange)
        for key, (lo, hi, step) in (("theta", (0.0, 180.0, 5.0)),
                                    ("phi", (0.0, 359.9, 5.0)),
                                    ("focus", (-2000.0, 2000.0, 10.0)),
                                    ("length", (10.0, 4000.0, 5.0)),
                                    ("spin", (0.0, 359.9, 15.0))):
            box = QDoubleSpinBox()
            box.setRange(lo, hi)
            box.setDecimals(1)
            box.setSingleStep(step)
            box.setWrapping(key in ("phi", "spin"))
            box.setValue(p[key])
            box.valueChanged.connect(
                lambda val, r=i, k=key: self._set(r, k, val))
            self.table.setCellWidget(i, SPINS[key], box)
        acc = QComboBox()
        for key, (label, _pid, fam) in cd.ACCESSORIES.items():
            acc.addItem(label if fam == "any" else f"{label} ({fam})", key)
        acc.setCurrentIndex(acc.findData(p["accessory"]))
        acc.currentIndexChanged.connect(
            lambda _i, r=i, w=acc: self._set_accessory(r, w.currentData()))
        self.table.setCellWidget(i, 6, acc)
        self.table.setCellWidget(i, 7, self._variant_box(i, p))

    def _variant_box(self, i, p):
        box = QComboBox()
        rows = cd.variants(p["accessory"])
        box.addItem("default", "")
        for row in rows:
            box.addItem(row, row)
        box.setCurrentIndex(max(box.findData(p.get("variant") or ""), 0))
        box.setEnabled(bool(rows))
        box.currentIndexChanged.connect(
            lambda _i, r=i, w=box: self._set(r, "variant", w.currentData()))
        return box

    def _set_accessory(self, row, key):
        """An accessory change resets the variant to that part's rows."""
        if self._loading or row >= len(self.spec["ports"]):
            return
        self.spec["ports"][row]["accessory"] = key
        self.spec["ports"][row]["variant"] = ""
        self._loading = True
        self.table.setCellWidget(row, 7,
                                 self._variant_box(row,
                                                   self.spec["ports"][row]))
        self._loading = False
        self._refresh()

    def _set(self, row, key, value):
        if self._loading or row >= len(self.spec["ports"]):
            return
        self.spec["ports"][row][key] = value
        self._refresh()

    def _body_changed(self, *_args):
        if self._loading:
            return
        s = self.spec
        s.update(name=self.name.text().strip() or "UHV chamber",
                 body=self.body.currentData(), radius=self.radius.value(),
                 height=self.height.value(), wall=self.wall.value(),
                 liner=self.liner.isChecked(),
                 liner_gap=self.liner_gap.value(),
                 liner_thickness=self.liner_t.value(),
                 bench=self.bench.currentData(), beam_height=self.beam.value(),
                 bench_width=self.bench_w.value(),
                 bench_depth=self.bench_d.value(), rx=self.rx.value(),
                 ry=self.ry.value(), rz=self.rz.value())
        self._refresh()

    def _refresh(self):
        self.height.setEnabled(self.spec["body"] == "cylinder")
        self.liner_gap.setEnabled(self.spec["liner"])
        self.liner_t.setEnabled(self.spec["liner"])
        on_bench = self.spec["bench"] != "none"
        for w in (self.bench_w, self.bench_d):
            w.setEnabled(on_bench and self.spec["bench"] != "tripod")
        found = cd.problems(self.spec)
        problems = [msg for msg, _ports in found]
        bad = set().union(*[ports for _msg, ports in found])
        self.map.spec = self.spec
        self.map.bad = bad
        self.map.current = self._current()
        self.map.update()
        n = len(self.spec["ports"])
        if problems:
            self.info.setText(f"{n} ports. <span style='color:#c0392b'>"
                              + "; ".join(problems) + "</span>")
        else:
            self.info.setText(f"{n} ports, no clashes.")

    def _current(self):
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    # ------------------------------------------------------------ editing
    def _select_row(self, i):
        self.table.selectRow(i)

    def _row_changed(self):
        self.map.current = self._current()
        self.map.update()

    def _drag_port(self, i, theta, phi):
        p = self.spec["ports"][i]
        p["theta"], p["phi"] = theta, phi
        self._loading = True
        self.table.cellWidget(i, SPINS["theta"]).setValue(theta)
        self.table.cellWidget(i, SPINS["phi"]).setValue(phi)
        self._loading = False
        self._refresh()

    def _add_port(self, theta, phi):
        n = len(self.spec["ports"]) + 1
        focus = self.spec["ports"][-1]["focus"] if self.spec["ports"] else 0.0
        p = cd.port(f"Port {n}", "CF40 (DN40)", theta, phi, 0.0,
                    focus=focus)
        p["length"] = cd.min_length(self.spec, p) + 40.0
        self.spec["ports"].append(p)
        self._fill_table()
        self.table.selectRow(n - 1)
        self._refresh()

    def _duplicate(self):
        i = self._current()
        if i < 0:
            return
        p = dict(self.spec["ports"][i])
        p["name"] += " copy"
        p["phi"] = (p["phi"] + 30.0) % 360.0
        self.spec["ports"].insert(i + 1, p)
        self._fill_table()
        self.table.selectRow(i + 1)
        self._refresh()

    def _remove(self):
        i = self._current()
        if i < 0:
            return
        del self.spec["ports"][i]
        self._fill_table()
        self._refresh()

    def _shortest(self):
        """Pull the selected port (or every port) in to the shortest
        length that clears the body."""
        i = self._current()
        rows = [i] if i >= 0 else range(len(self.spec["ports"]))
        for r in rows:
            p = self.spec["ports"][r]
            p["length"] = cd.min_length(self.spec, p)
        self._fill_table()
        if i >= 0:
            self.table.selectRow(i)
        self._refresh()

    def _use_preset(self, index):
        name = self.preset.itemData(index)
        if name:
            self._load_spec(cd.preset(name))
        self.preset.setCurrentIndex(0)

    # ------------------------------------------------------------ files
    def save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save chamber", f"{self.spec['name']}.json",
            "Chamber (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.spec, fh, indent=2, ensure_ascii=False)

    def load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load chamber", "",
                                              "Chamber (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                self._load_spec(json.load(fh))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Chamber Designer",
                                f"Could not read the chamber:\n{exc}")

    # ------------------------------------------------------------ build
    def build_now(self, replace=False):
        model = self.window_.model
        try:
            node = cd.build(self.spec)
        except Exception as exc:                 # noqa: BLE001
            QMessageBox.warning(self, "Chamber Designer",
                                f"Could not build the chamber:\n{exc}")
            return
        old = self.built
        if replace and old is not None and old.parent is not None:
            parent = old.parent
            index = parent.children.index(old)
            parent.remove(old)
            parent.add(node, index)
        else:
            model.root.add(node)
        self.built = node
        self.update_btn.setEnabled(True)
        model.structure_changed.emit()
        try:
            self.window_.builder.tree.select_nodes([node])
            self.window_.view3d.fit()
        except AttributeError:
            pass
        self.window_.statusBar().showMessage(
            f"Built {node.name}: {len(self.spec['ports'])} ports.", 8000)


def open_designer(window):
    """Show the (one) Chamber Designer window."""
    panel = getattr(window, "_chamber_designer", None)
    if panel is None:
        panel = window._chamber_designer = ChamberDesigner(window)
    panel.show()
    panel.raise_()
    return panel

"""Section Properties (2026-11-12, the user, from SolidWorks' Evaluate
tab): the area properties of the model cut by a plane — area, perimeter,
centroid, second moments of area about the centroid, the principal axes,
the polar moment, radii of gyration and section moduli. What a beam's
stiffness and strength are worked out from.

`properties` is Qt-free: the outlines come from `section.section` (solid
outlines counter-clockwise, holes clockwise), so every sum below is the
signed polygon formula and a hole subtracts by itself. `SectionDialog`
is Analyse ▸ Section Properties; the MCP `section` tool returns the same
numbers as `properties`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import section


def properties(sec: dict) -> dict:
    """Area properties of a `section.section` result, in its (u, v)
    plane and its unit. {} when nothing closed is cut (the plane misses
    the model, or the mesh leaks all round).

    area, perimeter, centroid [u, v]; about the CENTROID: iu (resisting
    bending about the u axis, the integral of v²), iv, iuv, the principal
    i1 >= i2 with `angle` (degrees from u to the i1 axis), polar j,
    radii of gyration ru, rv, and the elastic section moduli zu, zv
    (I over the farthest fibre). `open` counts outlines left open."""
    loops = [o["points"] for o in sec["outlines"]
             if o["closed"] and len(o["points"]) >= 3]
    a = sx = sy = ixx = iyy = ixy = per = 0.0
    for pts in loops:
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            c = x0 * y1 - x1 * y0
            a += c
            sx += (x0 + x1) * c
            sy += (y0 + y1) * c
            ixx += (y0 * y0 + y0 * y1 + y1 * y1) * c
            iyy += (x0 * x0 + x0 * x1 + x1 * x1) * c
            ixy += (x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * c
            per += math.hypot(x1 - x0, y1 - y0)
    a /= 2.0
    opened = sum(1 for o in sec["outlines"] if not o["closed"])
    if abs(a) < 1e-12:
        return {}
    cu, cv = sx / (6.0 * a), sy / (6.0 * a)
    iu = ixx / 12.0 - a * cv * cv
    iv = iyy / 12.0 - a * cu * cu
    iuv = ixy / 24.0 - a * cu * cv
    if a < 0:                      # every loop wound the other way
        a, iu, iv, iuv = -a, -iu, -iv, -iuv
    # rounding noise is not a number to show: 4.6e-16 mm, -2.5e-10 mm⁴
    every = [p for pts in loops for p in pts]
    size = max(max(abs(p[0]), abs(p[1])) for p in every)
    cu = 0.0 if abs(cu) < 1e-9 * size else cu
    cv = 0.0 if abs(cv) < 1e-9 * size else cv
    if abs(iuv) < 1e-9 * max(abs(iu), abs(iv)):
        iuv = 0.0
    mean, half = (iu + iv) / 2.0, (iu - iv) / 2.0
    r = math.hypot(half, iuv)
    # the axis of i1 (the stiffest): Mohr's circle
    angle = 0.0 if r < 1e-9 * max(mean, 1e-30) else \
        math.degrees(0.5 * math.atan2(-2.0 * iuv, iu - iv))
    if angle <= -90.0 + 1e-9:      # one axis, one name: (-90, 90]
        angle += 180.0
    far_v = max(abs(p[1] - cv) for p in every)
    far_u = max(abs(p[0] - cu) for p in every)
    return {
        "area": a, "perimeter": per, "centroid": [cu, cv],
        "iu": iu, "iv": iv, "iuv": iuv,
        "i1": mean + r, "i2": mean - r, "angle": angle,
        "j": iu + iv,
        "ru": math.sqrt(max(iu, 0.0) / a), "rv": math.sqrt(max(iv, 0.0) / a),
        "zu": iu / far_v if far_v > 1e-12 else 0.0,
        "zv": iv / far_u if far_u > 1e-12 else 0.0,
        "loops": len(loops), "open": opened,
    }


def of_mesh(tris, axis: str, offset: float = None):
    """(section, properties) of *tris* cut by ``axis = offset``."""
    sec = section.section(tris, axis, offset)
    return sec, properties(sec)


def _n(v, digits=4):
    """A number at *digits* significant figures, thousands grouped."""
    if v == 0:
        return "0"
    mag = math.floor(math.log10(abs(v)))
    if mag >= 9 or mag < -4:
        return f"{v:.{digits - 1}e}"
    places = max(0, digits - 1 - mag)
    return f"{v:,.{places}f}"


def rows(sec: dict, props: dict, unit: str = "mm") -> list:
    """[(label, value)] of the report, in the document's unit symbol."""
    from . import language, units
    u = units.symbol(unit)
    un, vn = sec["plane"]
    tr = language.tr
    if not props:
        return [(tr("Section"), tr(
            "The plane cuts no closed outline here — move it into the "
            "part."))]
    cu, cv = props["centroid"]
    out = [
        (tr("Area"), f"{_n(props['area'])} {u}²"),
        (tr("Perimeter"), f"{_n(props['perimeter'])} {u}"),
        (tr("Centroid"), f"{un} = {_n(cu)}, {vn} = {_n(cv)} {u}"),
        (tr("I about {axis} (through the centroid)").format(axis=un),
         f"{_n(props['iu'])} {u}⁴"),
        (tr("I about {axis} (through the centroid)").format(axis=vn),
         f"{_n(props['iv'])} {u}⁴"),
        (tr("Product of inertia"), f"{_n(props['iuv'])} {u}⁴"),
        (tr("Principal moments"),
         f"I₁ = {_n(props['i1'])}, I₂ = {_n(props['i2'])} {u}⁴"),
        (tr("Principal axis"), tr("{angle}° from {axis}").format(
            angle=_n(props["angle"], 3), axis=un)),
        (tr("Polar moment (about the centroid)"),
         f"{_n(props['j'])} {u}⁴"),
        (tr("Radii of gyration"),
         f"{un}: {_n(props['ru'])}, {vn}: {_n(props['rv'])} {u}"),
        (tr("Section moduli"),
         f"{un}: {_n(props['zu'])}, {vn}: {_n(props['zv'])} {u}³"),
    ]
    if props["open"]:
        out.append((tr("Warning"), tr(
            "{n} outline(s) do not close — the mesh leaks on this "
            "plane and is left out of the figures.").format(
                n=props["open"])))
    return out


def html(sec, props, unit="mm") -> str:
    body = "".join(f"<tr><td><b>{k}</b>&nbsp;&nbsp;</td><td>{v}</td></tr>"
                   for k, v in rows(sec, props, unit))
    return f"<table cellpadding='3'>{body}</table>"


def picture(sec, props, width, height):
    """The hatched section with its centroid and principal axes."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen

    def marks(painter, xy):
        if not props or not sec["bounds"]:
            return
        cu, cv = props["centroid"]
        u0, v0, u1, v1 = sec["bounds"]
        reach = 0.6 * math.hypot(u1 - u0, v1 - v0)
        for k, colour in ((0, "#c0392b"), (1, "#2e8b57")):
            t = math.radians(props["angle"] + 90 * k)
            du, dv = math.cos(t) * reach, math.sin(t) * reach
            painter.setPen(QPen(QColor(colour), 1.3, Qt.DashDotLine))
            painter.drawLine(xy((cu - du, cv - dv)), xy((cu + du, cv + dv)))
            painter.drawText(xy((cu + du, cv + dv)) + QPointF(4, -4),
                             "1" if k == 0 else "2")
        c = xy((cu, cv))
        painter.setPen(QPen(QColor("#101010"), 1.6))
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(c, 5, 5)
        painter.drawLine(c + QPointF(-9, 0), c + QPointF(9, 0))
        painter.drawLine(c + QPointF(0, -9), c + QPointF(0, 9))

    return section.draw(sec, width, height, overlay=marks)


# =================================================================== Qt

def _dialog_class():
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPixmap
    from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                                 QDoubleSpinBox, QHBoxLayout, QLabel,
                                 QPushButton, QSlider, QTextBrowser,
                                 QVBoxLayout)

    from . import language, units

    class SectionDialog(QDialog):
        """Analyse ▸ Section Properties: choose the plane, read the
        figures; the 3D view is cut at the same plane while it is open
        (Cut Through), and put back when it closes."""

        def __init__(self, window, nodes, parent=None):
            super().__init__(parent or window)
            self.window_ = window
            self.nodes = list(nodes)
            self.setModal(False)
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setWindowTitle(language.tr("Section properties"))
            self.resize(640, 860)
            from .analysis_dialog import part_tris
            self.tris, approx = part_tris(window, self.nodes)
            self._cut_before = window.view3d.cut_state()
            self._showing = False
            tr = language.tr
            layout = QVBoxLayout(self)
            row = QHBoxLayout()
            row.addWidget(QLabel(tr("Cut plane")))
            self.axis = QComboBox()
            for key, text in (("z", tr("Top (across Z)")),
                              ("y", tr("Front (across Y)")),
                              ("x", tr("Right (across X)"))):
                self.axis.addItem(text, key)
            row.addWidget(self.axis)
            row.addWidget(QLabel(tr("at")))
            self.offset = QDoubleSpinBox()
            self.offset.setDecimals(3)
            self.offset.setKeyboardTracking(False)
            self.offset.setSuffix(" " + units.symbol(window.model.unit))
            row.addWidget(self.offset)
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, 1000)
            row.addWidget(self.slider, 1)
            layout.addLayout(row)
            row = QHBoxLayout()
            self.show_cut = QPushButton(tr("Show the cut in the 3D view"))
            self.show_cut.setCheckable(True)
            row.addWidget(self.show_cut)
            copy = QPushButton(tr("Copy the figures"))
            row.addWidget(copy)
            row.addStretch(1)
            layout.addLayout(row)
            self.image = QLabel()
            self.image.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.image)
            self.browser = QTextBrowser()
            layout.addWidget(self.browser, 1)
            self.note = QLabel(tr(
                "The mesh comes from the built-in preview, which only "
                "approximates booleans (holes uncut) — figures are "
                "approximate until the exact render lands.") if approx
                else "")
            self.note.setWordWrap(True)
            layout.addWidget(self.note)
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(self.close)
            layout.addWidget(buttons)
            self.sec, self.props = None, {}
            cut = self._cut_before
            if cut and cut.get("axis") in section.PLANES:
                self.axis.setCurrentIndex(self.axis.findData(cut["axis"]))
            self._span()
            if cut and cut.get("offset") is not None \
                    and cut.get("axis") == self.axis.currentData():
                self.offset.setValue(float(cut["offset"]))
            self.axis.currentIndexChanged.connect(self._axis_changed)
            self.offset.valueChanged.connect(self._offset_changed)
            self.slider.valueChanged.connect(self._slid)
            self.show_cut.toggled.connect(self._show)
            copy.clicked.connect(self._copy)
            self.refresh()

        # ---------------------------------------------------- plane
        def _span(self):
            """The spin box and slider cover the part along the axis;
            the plane starts in the middle."""
            k = section.PLANES[self.axis.currentData()][0]
            vals = [v[k] for tri in self.tris for v in tri] or [0.0, 0.0]
            self.lo, self.hi = min(vals), max(vals)
            for w in (self.offset, self.slider):
                w.blockSignals(True)
            self.offset.setRange(self.lo, self.hi)
            self.offset.setSingleStep(max((self.hi - self.lo) / 100, 1e-3))
            self.offset.setValue((self.lo + self.hi) / 2.0)
            self.slider.setValue(500)
            for w in (self.offset, self.slider):
                w.blockSignals(False)

        def _axis_changed(self, _index):
            self._span()
            self.refresh()

        def _offset_changed(self, value):
            span = max(self.hi - self.lo, 1e-12)
            self.slider.blockSignals(True)
            self.slider.setValue(int(round(1000 * (value - self.lo) / span)))
            self.slider.blockSignals(False)
            self.refresh()

        def _slid(self, value):
            self.offset.setValue(self.lo + (self.hi - self.lo) * value / 1000)

        # ----------------------------------------------------- data
        def refresh(self):
            self.sec, self.props = of_mesh(
                self.tris, self.axis.currentData(), self.offset.value())
            self.browser.setHtml(html(self.sec, self.props,
                                      self.window_.model.unit))
            self.image.setPixmap(QPixmap.fromImage(
                picture(self.sec, self.props, 600, 280)))
            if self._showing:
                self._show(True)

        def _show(self, on):
            win = self.window_
            if on:
                # Cut Through counts along the WHOLE model on show
                axis = self.axis.currentData()
                k = section.PLANES[axis][0]
                vals = [v[k] for tri in win.view3d.model_mesh
                        for v in tri] or [self.lo, self.hi]
                span = max(max(vals) - min(vals), 1e-12)
                win.set_cut(True, axis=axis, position=(
                    self.offset.value() - min(vals)) / span)
                self._showing = True
            elif self._showing:
                self._showing = False
                before = self._cut_before
                if before:
                    win.set_cut(True, axis=before.get("axis"),
                                position=before.get("position"),
                                flip=before.get("flip"))
                else:
                    win.set_cut(False)

        def _copy(self):
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(
                f"{k}\t{v}" for k, v in rows(
                    self.sec, self.props, self.window_.model.unit)))
            self.window_.statusBar().showMessage(language.tr(
                "Section properties copied."), 4000)

        def closeEvent(self, event):
            self._show(False)
            super().closeEvent(event)

    return SectionDialog


def open_window(window, nodes=None):
    """The Section Properties window for the selection, else every
    visible part; None (and a message) when there is nothing to cut."""
    from . import language
    if nodes is None:
        nodes = window.builder.active_tree().selected_nodes()
    if not nodes:
        nodes = [n for n in window.model.root.children
                 if n.visible and n.type not in ("variables", "masters",
                                                 "assign")]
    if not nodes:
        message = language.tr(
            "Nothing to analyse — select a part, or build one.")
        window.statusBar().showMessage(message, 4000)
        window.view3d.flash(message)
        return None
    dialog = _dialog_class()(window, nodes)
    if not dialog.tris:
        dialog.deleteLater()
        message = language.tr("Section properties: there is no solid to "
                              "cut here.")
        window.statusBar().showMessage(message, 4000)
        window.view3d.flash(message)
        return None
    dialog.show()
    return dialog

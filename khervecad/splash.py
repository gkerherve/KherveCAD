"""The start-up picture: shown while the window's modules load and the
window is built, with what is loading and a progress bar.

Painted, not a shipped image, so it always carries the running version
and needs nothing in the installer's data files.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap)
from PyQt5.QtWidgets import QApplication, QSplashScreen

WIDTH, HEIGHT = 560, 320
ACCENT = QColor("#f28c28")
TEXT = QColor("#eef1f5")
MUTED = QColor("#9aa6b4")

#: the steps main() reports, in order — the bar fills one step at a time
STEPS = ("Starting", "Loading the modelling engine", "Building the window",
         "Opening the workspace", "Ready")


def _font(size, bold=False):
    font = QFont()
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def background(ratio=1.0) -> QPixmap:
    """The picture without the progress: slate gradient, the app icon, the
    name, a line of what it is and the version."""
    from . import APP_NAME, __version__
    from .icons import _paint_kcad
    pm = QPixmap(int(WIDTH * ratio), int(HEIGHT * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    frame = QPainterPath()
    frame.addRoundedRect(QRectF(0, 0, WIDTH, HEIGHT), 14, 14)
    grad = QLinearGradient(0, 0, WIDTH, HEIGHT)
    grad.setColorAt(0.0, QColor("#2b3440"))
    grad.setColorAt(1.0, QColor("#151a21"))
    p.fillPath(frame, grad)
    # a faint isometric grid behind, like the 3D view's floor
    p.setClipPath(frame)
    p.setPen(QPen(QColor(255, 255, 255, 14), 1))
    for k in range(-HEIGHT, WIDTH + HEIGHT, 28):
        p.drawLine(QPointF(k, HEIGHT), QPointF(k + HEIGHT * 1.7, 0))
        p.drawLine(QPointF(k, 0), QPointF(k + HEIGHT * 1.7, HEIGHT))
    p.setClipping(False)
    icon = _paint_kcad(int(132 * ratio))
    icon.setDevicePixelRatio(ratio)
    p.drawPixmap(QPointF(44, 58), icon)
    p.setPen(TEXT)
    p.setFont(_font(40, bold=True))
    p.drawText(QRectF(204, 62, WIDTH - 220, 50), Qt.AlignLeft | Qt.AlignVCenter,
               APP_NAME)
    p.setPen(MUTED)
    p.setFont(_font(15))
    p.drawText(QRectF(206, 112, WIDTH - 220, 24),
               Qt.AlignLeft | Qt.AlignVCenter,
               "Parametric CAD with OpenSCAD as the engine")
    p.setPen(ACCENT)
    p.setFont(_font(13, bold=True))
    p.drawText(QRectF(206, 142, WIDTH - 220, 20),
               Qt.AlignLeft | Qt.AlignVCenter, f"v{__version__}")
    p.setPen(QColor(255, 255, 255, 40))
    p.setFont(_font(11))
    p.drawText(QRectF(24, HEIGHT - 30, WIDTH - 48, 18),
               Qt.AlignRight | Qt.AlignVCenter,
               "khervetools.com  ·  GPL-3.0")
    p.end()
    return pm


class Splash(QSplashScreen):
    """The start-up picture plus a status line and a progress bar."""

    def __init__(self):
        screen = QApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen is not None else 1.0
        super().__init__(background(ratio), Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.step_text = STEPS[0]
        self.fraction = 0.0

    def step(self, text: str):
        """Show *text* (one of STEPS, or anything) and advance the bar to
        its place in STEPS; the event loop gets a turn so it paints."""
        self.step_text = text
        if text in STEPS:
            self.fraction = STEPS.index(text) / (len(STEPS) - 1)
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, p: QPainter):
        p.setRenderHint(QPainter.Antialiasing)
        bar = QRectF(44, HEIGHT - 74, WIDTH - 88, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(bar, 3, 3)
        if self.fraction > 0:
            done = QRectF(bar.x(), bar.y(), bar.width() * self.fraction,
                          bar.height())
            p.setBrush(ACCENT)
            p.drawRoundedRect(done, 3, 3)
        p.setPen(TEXT)
        p.setFont(_font(13))
        dots = "" if self.step_text == STEPS[-1] else "…"
        p.drawText(QRectF(44, HEIGHT - 100, WIDTH - 88, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, self.step_text + dots)

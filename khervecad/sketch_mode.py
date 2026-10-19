"""Fusion's sketch mode: one canvas, 2D only while sketching.

Fusion and SolidWorks have no 2D view beside the 3D one: Create Sketch
turns the canvas to the sketch plane, a SKETCH tab of tools appears,
Finish Sketch goes back to the model. KherveCAD's classic window keeps
both views stacked; in the Fusion Interface Style (2026-10-19, the
user chose the simple version) the right column shows ONE of them in
the same place: the 3D view, and the 2D sketch view while sketching —
entered by Create Sketch or by picking a drawing tool, left by the
Finish Sketch button floating on the sketch.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QAction, QLabel, QPushButton

from . import icons, language, tooltips

tooltips.TIPS.setdefault("create_sketch", (
    "Create sketch",
    "Draw in 2D: the canvas turns into the sketch on the current plane "
    "(Top XY, Front XZ or Side YZ). Finish Sketch brings the 3D model "
    "back.",
    ["Click Create sketch (or any drawing tool).",
     "Pick the plane in the sketch's own bar, draw.",
     "Click Finish Sketch."], None))


def active(win) -> bool:
    """True when the window works Fusion's way (one canvas)."""
    return getattr(win, "_interface_style", "") == "Fusion"


def sketching(win) -> bool:
    return bool(getattr(win, "_sketching", False))


def create_action(win):
    """The SKETCH tab's Create Sketch action, made once per window."""
    act = getattr(win, "_create_sketch_act", None)
    if act is None:
        act = QAction(icons.icon("mdi.pencil-box-outline", "#0696d7"),
                      language.tr("Create Sketch"), win)
        act.setData("create_sketch")
        from . import toolbars
        toolbars.remember_glyph(act, "mdi.pencil-box-outline", "draw")
        tooltips.apply(act, "create_sketch")
        act.triggered.connect(lambda: enter(win))
        win._create_sketch_act = act
    return act


class _FinishButton(QPushButton):
    """Fusion's green FINISH SKETCH, top-right of the sketch."""

    def __init__(self, win):
        super().__init__("✓  " + language.tr("FINISH SKETCH"), win.view2d)
        self.setObjectName("finishSketch")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "#finishSketch { background: #2e9a46; color: white; border: "
            "none; border-radius: 3px; padding: 6px 14px; font-weight: "
            "bold; } #finishSketch:hover { background: #38b153; }")
        self.clicked.connect(lambda: finish(win))
        self._view = win.view2d
        self._view.installEventFilter(self)
        self.place()

    def place(self):
        self.adjustSize()
        area = self._view.viewport().geometry()
        # left of the floating nav bar, which holds the top-right corner
        nav = getattr(self._view, "nav_bar", None)
        right = nav.x() - 10 if nav is not None and nav.isVisible() \
            else area.right() - 10
        self.move(right - self.width(), area.top() + 10)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            self.place()
        return False


def _button(win):
    b = getattr(win, "_finish_sketch", None)
    if b is None:
        b = win._finish_sketch = _FinishButton(win)
    return b


def _show(win, sketch: bool):
    vibe = bool(getattr(win, "_vibe_act", None)
                and win._vibe_act.isChecked())
    win.view2d.setVisible(sketch and not vibe)
    win.view3d.setVisible(not sketch or vibe)
    b = _button(win)
    b.setVisible(sketch)
    inset = _inset(win)
    inset.setVisible(sketch and not vibe)
    if sketch:
        b.place()
        inset.place()
        inset.redraw()
        # the splitter sizes a view it just showed on the next turn
        QTimer.singleShot(0, inset.place)
        QTimer.singleShot(0, b.place)


def enter(win):
    """Create Sketch: the canvas becomes the 2D sketch."""
    if not active(win):
        return
    win._sketching = True
    _show(win, True)
    if getattr(win, "ribbon", None) is not None:
        win.ribbon.show_tab("sketch")
    win.view2d.setFocus()


def finish(win):
    """Finish Sketch: back to the 3D model, Select tool."""
    win._sketching = False
    from .view2d import SELECT
    for act in win._tool_group.actions():
        if act.data() == SELECT:
            act.setChecked(True)
    win.view2d.set_tool(SELECT)
    if active(win):
        _show(win, False)
        if getattr(win, "ribbon", None) is not None:
            win.ribbon.show_tab("features")


def tool_chosen(win, tool):
    """A drawing tool picked while the 3D model shows: start sketching."""
    from .view2d import MEASURE, SELECT
    if active(win) and not sketching(win) and tool not in (SELECT,
                                                           MEASURE):
        enter(win)


def apply(win, style):
    """The Interface Style changed: one canvas (Fusion) or both."""
    if style == "Fusion":
        _show(win, sketching(win))
        return
    win._sketching = False
    for name in ("_finish_sketch", "_sketch_inset"):
        b = getattr(win, name, None)
        if b is not None:
            b.hide()
    vibe = bool(getattr(win, "_vibe_act", None)
                and win._vibe_act.isChecked())
    win.view2d.setVisible(not vibe)
    win.view3d.setVisible(True)


def after_vibe(win):
    """Vibe Model switched: in Fusion the canvas follows the sketch."""
    if active(win):
        _show(win, sketching(win))


class Inset(QLabel):
    """The model in 3D, small, in the sketch's bottom-right corner while
    sketching (2026-10-19, the user: "in the right bottom corner of the
    2D, see the 3D still"). A picture from the 3D view's own camera
    (`View3D.snapshot`), redrawn when the model changes; a click on it
    finishes the sketch."""

    W, H = 280, 200

    def __init__(self, win):
        super().__init__(win.view2d)
        self.win = win
        self.setObjectName("sketchInset")
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(language.tr("The model in 3D — click to finish "
                                    "the sketch"))
        self.setStyleSheet("#sketchInset { border: 1px solid #9aa4ad; "
                           "border-radius: 3px; background: #e9edf1; }")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.redraw)
        win.model.structure_changed.connect(self.later)
        win.model.node_changed.connect(self.later)
        win.view2d.installEventFilter(self)

    def later(self, *args):
        if self.isVisible():
            self._timer.start()

    def redraw(self):
        try:                  # the 3D view's own angle, the whole model
            img, _state = self.win.view3d.snapshot(
                self.W - 2, self.H - 2, frame=True, zoom=0.8, clean=True)
        except Exception:                   # never break the sketch
            return
        if img is not None:
            self.setPixmap(QPixmap.fromImage(img))

    def place(self):
        area = self.win.view2d.viewport().geometry()
        self.move(area.right() - self.W - 12, area.bottom() - self.H - 12)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show,
                            QEvent.LayoutRequest):
            QTimer.singleShot(0, self.place)
        return False

    def mousePressEvent(self, event):
        finish(self.win)


def _inset(win):
    got = getattr(win, "_sketch_inset", None)
    if got is None:
        got = win._sketch_inset = Inset(win)
    return got

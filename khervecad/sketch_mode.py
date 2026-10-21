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


#: styles with one canvas and the other view small in its corner
ONE_CANVAS = ("Fusion", "SolidWorks")


def active(win) -> bool:
    """True when the window works Fusion's way (one canvas)."""
    # SolidWorks sketches the same way (2026-10-20, the user)
    return getattr(win, "_interface_style", "") in ONE_CANVAS


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
        # a 2D shape selected: Edit Sketch — turn to it first (normal_to)
        act.triggered.connect(lambda: _create_or_edit(win))
        win._create_sketch_act = act
    return act


def _create_or_edit(win):
    """Create Sketch / Exit Sketch, one button (the user): sketching, it
    leaves; else the 3D view turns onto the plane and the sketch opens."""
    if sketching(win):
        finish(win)
        return
    from . import normal_to
    if active(win):
        normal_to.create(win)
    else:
        enter(win)


def sync_create(win):
    """The button reads Exit Sketch while sketching."""
    act = getattr(win, "_create_sketch_act", None)
    if act is not None:
        act.setText(language.tr("Exit Sketch") if sketching(win)
                    else language.tr("Create Sketch"))


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
    # the green FINISH SKETCH is not drawn (2026-10-21, the user: remove
    # it from the 2D view); picking a 3D tab or tool leaves the sketch
    b.setVisible(False)
    inset = _inset(win)
    inset.setVisible(sketch and not vibe)
    mini = _mini2d(win)
    mini.setVisible(not sketch and not vibe)
    if not sketch:
        mini.place()
        mini.redraw()
        QTimer.singleShot(0, mini.place)
    if sketch:
        inset.place()
        inset.redraw()
        # the splitter sizes a view it just showed on the next turn
        QTimer.singleShot(0, inset.place)



def enter(win):
    """Create Sketch: the canvas becomes the 2D sketch."""
    if not active(win):
        return
    win._sketching = True
    sync_create(win)
    _show(win, True)
    QTimer.singleShot(0, lambda: _frame_2d(win))
    if getattr(win, "ribbon", None) is not None:
        win.ribbon.show_tab("sketch")
    win.view2d.setFocus()


def finish(win):
    """Finish Sketch: back to the 3D model, Select tool."""
    win._sketching = False
    sync_create(win)
    from .view2d import SELECT
    for act in win._tool_group.actions():
        if act.data() == SELECT:
            act.setChecked(True)
    win.view2d.set_tool(SELECT)
    if active(win):
        _show(win, False)
        # the ribbon stays on the Sketch tab (the user: Exit Sketch should
        # not take the tools away)
        # the 3D view comes back framed on what was picked (else the
        # whole model): it kept the camera it had before the sketch and
        # the picked part could be nowhere on it (2026-10-20, the user)
        # the 3D view turns back at the sketch's size — no zoom (the user)
        from . import normal_to
        QTimer.singleShot(0, lambda: normal_to.back(win))


#: how much further back than a tight fit the 3D view comes back
FRAME_MARGIN = 1.8


def _picked_rect(win):
    """The scene rectangle of what is picked — the part shown alone, the
    selected shapes — else of the whole drawing; None when empty."""
    scene = win.view2d.scene()
    rect = win.scene.isolated_bounds()
    if rect is None:
        for item in scene.selectedItems():
            box = item.sceneBoundingRect()
            rect = box if rect is None else rect.united(box)
    if rect is None or rect.isEmpty():
        rect = scene.itemsBoundingRect()
    return None if rect.isEmpty() else rect


def _frame_2d(win):
    """Opening the sketch shows what is picked, as leaving it shows it
    in 3D (the sketch could open zoomed out on empty paper)."""
    rect = _picked_rect(win)
    if rect is not None and win.view2d.isVisible():
        win.view2d.frame_rect(rect)


def _frame_3d(win):
    from . import viewnav
    view = win.view3d
    if view.isVisible() and (view.highlight_mesh or view.mesh):
        viewnav.focus_3d(view)
        view.distance *= FRAME_MARGIN        # room round it, like Fusion
        view.update()


def tool_chosen(win, tool):
    """A drawing tool picked while the 3D model shows: start sketching."""
    from .view2d import MEASURE, SELECT
    if active(win) and not sketching(win) and tool not in (SELECT,
                                                           MEASURE):
        enter(win)


def apply(win, style):
    """The Interface Style changed: one canvas (Fusion) or both."""
    if style in ONE_CANVAS:
        _show(win, sketching(win))
        return
    win._sketching = False
    for name in ("_finish_sketch", "_sketch_inset", "_sketch_mini2d"):
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


class _Resizable:
    """A corner view the user can make smaller or larger (2026-10-21,
    the user: "that small view needs to be resizable to make it even
    smaller"): a grip in its TOP-LEFT corner — it sits in the
    bottom-right of its view, so that corner is the free one — drags
    the size, remembered per view in QSettings `<KEY>`."""

    GRIP = 14
    MIN_W, MIN_H, MAX_W, MAX_H = 90, 64, 640, 460

    def _init_size(self):
        from PyQt5.QtCore import QSettings
        value = QSettings("Kherve", "KherveCAD").value(self.KEY)
        try:
            w, h = (int(v) for v in str(value).split("x"))
        except (TypeError, ValueError):
            w, h = type(self).W, type(self).H
        self.W = max(self.MIN_W, min(self.MAX_W, w))
        self.H = max(self.MIN_H, min(self.MAX_H, h))
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self._grab = None

    def _on_grip(self, pos):
        return pos.x() < self.GRIP and pos.y() < self.GRIP

    def set_size(self, w, h, save=True):
        self.W = int(max(self.MIN_W, min(self.MAX_W, w)))
        self.H = int(max(self.MIN_H, min(self.MAX_H, h)))
        self.setFixedSize(self.W, self.H)
        if getattr(self, "_twin_view", None) is not None:
            self._twin_view.resize((self.W - 2) * 3, (self.H - 2) * 3)
        self.place()
        self.redraw()
        if save:
            from PyQt5.QtCore import QSettings
            QSettings("Kherve", "KherveCAD").setValue(
                self.KEY, "%dx%d" % (self.W, self.H))

    def _grip_press(self, event):
        if event is not None and event.button() == Qt.LeftButton and \
                self._on_grip(event.pos()):
            # the bottom-right corner stays put, the top-left follows
            self._grab = (event.globalPos(), self.W, self.H)
            return True
        return False

    def mouseMoveEvent(self, event):
        if self._grab is not None:
            start, w, h = self._grab
            d = event.globalPos() - start
            self.set_size(w - d.x(), h - d.y(), save=False)
            return
        self.setCursor(Qt.SizeFDiagCursor if self._on_grip(event.pos())
                       else Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if self._grab is not None:
            self._grab = None
            self.set_size(self.W, self.H)            # remember it

    def paintEvent(self, event):
        super().paintEvent(event)
        from PyQt5.QtGui import QPainter, QPen, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#7d8892"), 1.2))
        for k in (4, 8, 12):                     # three diagonal ridges
            p.drawLine(2, k, k, 2)
        p.end()


class Inset(_Resizable, QLabel):
    """The model in 3D, small, in the sketch's bottom-right corner while
    sketching (2026-10-19, the user: "in the right bottom corner of the
    2D, see the 3D still"). A picture from the 3D view's own camera
    (`View3D.snapshot`), redrawn when the model changes; a click on it
    finishes the sketch."""

    W, H = 280, 200
    KEY = "sketch/inset_size"

    def __init__(self, win):
        super().__init__(win.view2d)
        self.win = win
        self.setObjectName("sketchInset")
        self._init_size()
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
        # the tree's selection reaches the sketch scene: the part picked
        # is tinted in the corner as in the full 3D view
        win.view2d.scene().selectionChanged.connect(self.later)
        win.view2d.installEventFilter(self)

    def later(self, *args):
        if self.isVisible():
            self._timer.start()

    def redraw(self):
        try:                  # the 3D view's own angle, the whole model
            img, _state = self.win.view3d.snapshot(
                self.W - 2, self.H - 2, frame=True, zoom=0.8, clean=True,
                highlight=True)
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
        if not self._grip_press(event):
            finish(self.win)


def _inset(win):
    got = getattr(win, "_sketch_inset", None)
    if got is None:
        got = win._sketch_inset = Inset(win)
    return got


class Mini2D(_Resizable, QLabel):
    """The sketch, small, in the 3D view's corner (the user, same day:
    "in the 3D view, the same thing, a 2D view on the side"): the 2D
    scene drawn Y-up round what it holds, the selection showing as the
    sketch shows it; a click starts sketching."""

    W, H = 240, 170
    KEY = "sketch/mini2d_size"

    def __init__(self, win):
        super().__init__(win.view3d)
        self.win = win
        self.setObjectName("sketchMini")
        self._init_size()
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(language.tr("The sketch in 2D — click to sketch"))
        self.setStyleSheet("#sketchMini { border: 1px solid #9aa4ad; "
                           "border-radius: 3px; background: #ffffff; }")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.redraw)
        win.model.structure_changed.connect(self.later)
        win.model.node_changed.connect(self.later)
        win.view2d.scene().selectionChanged.connect(self.later)
        win.view3d.installEventFilter(self)

    def later(self, *args):
        if self.isVisible():
            self._timer.start()

    def redraw(self):
        """The sketch, drawn by a twin sketch view of the SAME scene
        (grid when on, axes, colours, selection) framed on what is
        picked, else the whole drawing, and shrunk into the corner.

        A twin, never the user's own 2D view: borrowing that one showed
        a cropped, empty patch — hidden in its splitter it is squashed
        to no height, and its own zoom was whatever the sketch last had
        (the user's door handle: the cylinder seen in 2D was gone from
        the corner after going back to 3D)."""
        from PyQt5.QtCore import QSize
        from PyQt5.QtWidgets import QWidget
        try:
            twin = self._twin()
            rect = _picked_rect(self.win)
            if rect is not None:
                twin.frame_rect(rect)
            port = twin.viewport()
            pix = QPixmap(port.size())
            pix.fill(Qt.white)
            port.render(pix, flags=QWidget.RenderFlags(
                QWidget.DrawWindowBackground))
            pix = pix.scaled(QSize(self.W - 2, self.H - 2),
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception:                   # never break the 3D view
            return
        self.setPixmap(pix)

    def _twin(self):
        """An off-screen SketchView on the document's scene, the corner's
        own camera (3x the corner's size, so lines stay fine)."""
        twin = getattr(self, "_twin_view", None)
        if twin is None:
            from PyQt5.QtWidgets import QWidget
            from .view2d import SketchView
            twin = SketchView(self.win.view2d.scene())
            twin.no_dims = True          # the corner picture: shapes only
            twin.setAttribute(Qt.WA_DontShowOnScreen, True)
            # never a window the app waits for: a "shown" twin kept
            # KherveCAD running after its window closed, and it could
            # not be opened again (the user, 2026-10-20)
            twin.setAttribute(Qt.WA_QuitOnClose, False)
            twin.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            twin.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            twin.resize((self.W - 2) * 3, (self.H - 2) * 3)
            twin.show()                       # lays it out, off screen
            for w in twin.findChildren(QWidget):
                if w.parent() is twin and w is not twin.viewport():
                    w.hide()                  # its polygon bar & co
            self._twin_view = twin
            self.destroyed.connect(twin.deleteLater)
            self.win.destroyed.connect(twin.deleteLater)
        return twin

    def place(self):
        r = self.win.view3d.rect()
        nav = getattr(self.win.view3d, "nav_bar", None)
        lift = nav.height() + 18 if nav is not None and \
            nav.isVisible() and getattr(nav, "anchor", "") == \
            "bottom-centre" else 12
        self.move(r.right() - self.W - 12, r.bottom() - self.H - lift)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show):
            QTimer.singleShot(0, self.place)
        return False

    def mousePressEvent(self, event):
        if not self._grip_press(event):
            enter(self.win)


def _mini2d(win):
    got = getattr(win, "_sketch_mini2d", None)
    if got is None:
        got = win._sketch_mini2d = Mini2D(win)
    return got


def selection_changed(win):
    """The selection moved (tree or sketch): both corner views follow."""
    for name in ("_sketch_mini2d", "_sketch_inset"):
        got = getattr(win, name, None)
        if got is not None:
            got.later()

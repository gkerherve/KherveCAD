"""Where a Boss / Cut is sketched — asked, not guessed (2026-11-11, the
user: "extrude, boss or cut do a sketch in 3D … could we have the option
between doing a sketch in 3D or 2D so that I make a final decision? A
pop-up when you come to extrude cut, if you haven't selected anything,
also if you have selected something: select this model or create a new
sketch").

`ask(window, label, selection)` shows one small window:

- **What to use** — the selection (named, when there is one), a FACE
  clicked on the model, or one of the main planes (Front / Top / Right);
- **Sketch in** — the 3D view (drawn on the model where you look) or the
  2D sketch view (the flat drawing, square on);
- "Don't ask again" keeps the answer (QSettings `sketch/feature_ask`,
  `sketch/feature_where`); Edit ▸ Options ▸ Sketch turns the question
  back on.

Returns ``{"source": "selection" | "face" | "plane", "where": "3d" |
"2d"}``, ``False`` when cancelled, or ``None`` when `ask_hook` says not
to ask (the tests: the old behaviour, untouched).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

#: tests set it: called with (label, selection text) -> an answer dict,
#: False (cancel) or None (do not ask: the old behaviour)
ask_hook = None

SOURCES = ("selection", "face", "plane")
WHERE = ("3d", "2d")


def _settings():
    from PyQt5.QtCore import QSettings
    return QSettings("Kherve", "KherveCAD")


def asks() -> bool:
    v = _settings().value("sketch/feature_ask", True)
    return v not in (False, "false", "0", 0)


def set_asks(on: bool):
    _settings().setValue("sketch/feature_ask", bool(on))


def where() -> str:
    # the 2D sketch view is the default (2026-11-13, the user)
    v = str(_settings().value("sketch/feature_where", "2d"))
    return v if v in WHERE else "2d"


def _remember(choice, again):
    s = _settings()
    s.setValue("sketch/feature_where", choice["where"])
    if again:
        s.setValue("sketch/feature_ask", False)


def ask(window, label, selection=None):
    """The question for the Boss / Cut called *label*. *selection* is
    a short description of what is selected and usable (None: nothing)."""
    if ask_hook is not None:
        return ask_hook(label, selection)
    if not asks():
        return {"source": "selection" if selection else "face",
                "where": where()}
    from . import choice_preview
    preview = None
    if window is not None and getattr(window, "view3d", None) is not None:
        preview = choice_preview.start(window)
    dlg = ChoiceDialog(window, label, selection,
                       faces=(preview or {}).get("faces") or [])
    try:
        ok = dlg.exec_()
    finally:
        dlg.restore_view()
        if preview is not None:
            choice_preview.stop(window)
    if not ok:
        return False
    choice = dlg.choice()
    _remember(choice, dlg.again.isChecked())
    return choice


def describe(nodes, limit=3):
    """'Sketch on Block, Circle' — the selection in a few names."""
    names = [getattr(n, "name", "") or n.type for n in nodes]
    text = ", ".join(names[:limit])
    if len(names) > limit:
        text += " and %d more" % (len(names) - limit)
    return text


try:
    from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                                 QDialogButtonBox, QGroupBox, QLabel,
                                 QRadioButton, QVBoxLayout)

    class ChoiceDialog(QDialog):
        def __init__(self, window, label, selection, faces=()):
            super().__init__(window)
            self._window = window
            self._faces = list(faces)
            self._was_2d = None
            from . import language
            tr = language.tr
            self.setWindowTitle(tr(label))
            lay = QVBoxLayout(self)
            head = QLabel("<b>%s</b>" % tr(label))
            lay.addWidget(head)

            box = QGroupBox(tr("What to use"))
            col = QVBoxLayout(box)
            self.sources = QButtonGroup(self)
            self._source_buttons = {}
            items = []
            # a selected PART is sketched on (a face of it, clicked): the
            # 3D / 2D choice stays; a selected sketch is used as it is
            self._new_sketch = bool(selection) and \
                selection.startswith("a face of")
            if self._new_sketch:
                items.append(("selection", tr(
                    "The selection — click %s to sketch on") % selection))
            elif selection:
                items.append(("selection", tr("Use the selection: %s")
                              % selection))
            items += [
                ("face", tr("New sketch on a face of the model — "
                            "click the face")),
                ("plane", tr("New sketch on a plane — Front, Top or "
                             "Right"))]
            for key, text in items:
                b = QRadioButton(text)
                self.sources.addButton(b)
                self._source_buttons[key] = b
                col.addWidget(b)
                if key == "face":
                    # or one by its number, as painted on the model
                    self.face_combo = QComboBox()
                    self.face_combo.addItem(tr("Click it on the model"))
                    from .choice_preview import face_name
                    for i, f in enumerate(self._faces):
                        self.face_combo.addItem(face_name(f, i + 1))
                    self.face_combo.setEnabled(bool(self._faces))
                    self.face_combo.currentIndexChanged.connect(
                        lambda i: i > 0 and self.set_source("face"))
                    col.addWidget(self.face_combo)
            self._source_buttons[items[0][0]].setChecked(True)
            lay.addWidget(box)

            show = QGroupBox(tr("Show on the model"))
            row = QVBoxLayout(show)
            self.show_faces = QCheckBox(tr("Faces, numbered (F1, F2...)"))
            self.show_regions = QCheckBox(tr(
                "Sketch regions, numbered"))
            self.show_planes = QCheckBox(tr("Planes — Front, Top, Right"))
            self.show_faces.setChecked(True)
            self.show_regions.setChecked(True)
            self.show_planes.setChecked(False)
            for c in (self.show_faces, self.show_regions,
                      self.show_planes):
                row.addWidget(c)
                c.toggled.connect(lambda _on: self._shown())
            lay.addWidget(show)

            self.where_box = QGroupBox(tr("Sketch in"))
            col = QVBoxLayout(self.where_box)
            self.in3d = QRadioButton(tr(
                "3D view — draw on the model, where you are looking"))
            self.in2d = QRadioButton(tr(
                "2D sketch view — the flat drawing, square on"))
            col.addWidget(self.in3d)
            col.addWidget(self.in2d)
            # the 2D sketch view is always offered first (2026-11-13, the
            # user); "Don't ask again" keeps whatever was chosen
            self.in2d.setChecked(True)
            lay.addWidget(self.where_box)
            # the window shows the view chosen, back and forth (the user)
            self.in2d.toggled.connect(lambda _on: self._switch_view())

            self.again = QCheckBox(tr(
                "Don't ask again (Edit ▸ Options ▸ Sketch asks again)"))
            lay.addWidget(self.again)
            btns = QDialogButtonBox(QDialogButtonBox.Ok |
                                    QDialogButtonBox.Cancel)
            btns.accepted.connect(self.accept)
            btns.rejected.connect(self.reject)
            lay.addWidget(btns)
            # using the selection draws nothing new: no 3D / 2D to choose
            for b in self._source_buttons.values():
                b.toggled.connect(lambda _on: self._sync())
            self._sync()

        def _shown(self):
            if self._window is None:
                return
            from . import choice_preview
            choice_preview.show(self._window,
                                faces=self.show_faces.isChecked(),
                                regions=self.show_regions.isChecked(),
                                planes=self.show_planes.isChecked())

        def _switch_view(self):
            """The one canvas shows the 2D sketch or the 3D view as the
            Sketch in choice says (classic: both are on show)."""
            win = self._window
            if win is None:
                return
            try:
                from . import sketch_mode
                if not sketch_mode.active(win) or \
                        sketch_mode.sketching(win):
                    return
                if self._was_2d is None:
                    self._was_2d = win.view2d.isVisible() and \
                        not win.view3d.isVisible()
                sketch_mode._show(win, self.in2d.isChecked())
            except Exception:
                pass

        def restore_view(self):
            win = self._window
            if win is None or self._was_2d is None:
                return
            try:
                from . import sketch_mode
                sketch_mode._show(win, self._was_2d)
            except Exception:
                pass

        def _sync(self):
            self.where_box.setEnabled(self.source() != "selection" or
                                      self._new_sketch)

        def source(self):
            for key, b in self._source_buttons.items():
                if b.isChecked():
                    return key
            return "face"

        def set_source(self, key):
            self._source_buttons[key].setChecked(True)

        def choice(self):
            out = {"source": self.source(),
                   "where": "3d" if self.in3d.isChecked() else "2d"}
            i = self.face_combo.currentIndex() \
                if hasattr(self, "face_combo") else 0
            if out["source"] == "face" and 0 < i <= len(self._faces):
                out["face"] = self._faces[i - 1]
            return out
except ImportError:                       # Qt-free use (no dialog)
    ChoiceDialog = None

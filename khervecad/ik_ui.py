"""Reach (IK) by clicking — right-click a human figure or a part inside
joints ▸ Reach…, then click where the hand / foot / tip should go.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import ik, language

LABELS = {"Left hand": "left_hand", "Right hand": "right_hand",
          "Left foot": "left_foot", "Right foot": "right_foot",
          "Head": "head"}


def can_reach(node) -> bool:
    return ik.human_in(node) is not None or ik.in_joint(node)


def start(window, node):
    """Ask for the effector (a figure) and arm the 3D view: each click
    on the model moves it there, Esc finishes."""
    effector = None
    what = node.name
    if ik.human_in(node) is not None and not ik.in_joint(node):
        from PyQt5.QtWidgets import QInputDialog
        translated = [language.tr(k) for k in LABELS]
        label, ok = QInputDialog.getItem(
            window, language.tr("Reach"), language.tr("What should reach?"),
            translated, 0, False)
        if not ok:
            return
        english = list(LABELS)[translated.index(label)]
        effector = LABELS[english]
        what = label
    view = window.view3d

    def on_pick(desc):
        if desc is None:
            window.statusBar().showMessage(
                language.tr("Reach: {what} posed.").format(what=what), 5000)
            return
        from . import anchors
        try:
            out = ik.reach(window.model, node, desc["point"], effector,
                           env=anchors.doc_env(window.model))
        except ValueError as exc:
            window.statusBar().showMessage(
                language.tr("Reach: {error}").format(error=exc), 8000)
            return
        msg = (language.tr("Reach: {what} there (±{miss:.1f})").format(
                   what=what, miss=out["miss"])
               if out["reached"] else
               language.tr("Reach: {note}").format(note=out["note"]))
        window.statusBar().showMessage(msg, 8000)
        arm()

    def arm():
        view.start_pick(on_pick, banner=language.tr(
            "Reach: click where the {what} should go · Esc when "
            "done").format(what=what))
    arm()

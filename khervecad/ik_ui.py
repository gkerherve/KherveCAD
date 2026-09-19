"""Reach (IK) by clicking — right-click a human figure or a part inside
joints ▸ Reach…, then click where the hand / foot / tip should go.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import ik

LABELS = {"Left hand": "left_hand", "Right hand": "right_hand",
          "Left foot": "left_foot", "Right foot": "right_foot",
          "Head": "head"}


def can_reach(node) -> bool:
    return ik.human_in(node) is not None or ik.in_joint(node)


def start(window, node):
    """Ask for the effector (a figure) and arm the 3D view: each click
    on the model moves it there, Esc finishes."""
    effector = None
    if ik.human_in(node) is not None and not ik.in_joint(node):
        from PyQt5.QtWidgets import QInputDialog
        label, ok = QInputDialog.getItem(window, "Reach",
                                         "What should reach?",
                                         list(LABELS), 0, False)
        if not ok:
            return
        effector = LABELS[label]
    what = effector.replace("_", " ") if effector else node.name
    view = window.view3d

    def on_pick(desc):
        if desc is None:
            window.statusBar().showMessage(f"Reach: {what} posed.", 5000)
            return
        from . import anchors
        try:
            out = ik.reach(window.model, node, desc["point"], effector,
                           env=anchors.doc_env(window.model))
        except ValueError as exc:
            window.statusBar().showMessage(f"Reach: {exc}", 8000)
            return
        msg = (f"Reach: {what} there (±{out['miss']:.1f})"
               if out["reached"] else f"Reach: {out['note']}")
        window.statusBar().showMessage(msg, 8000)
        arm()

    def arm():
        view.start_pick(on_pick, banner=f"Reach: click where the {what} "
                        "should go · Esc when done")
    arm()

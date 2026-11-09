"""Writes docs/RIBBON_TOOLS.md: every tool of the ribbon's Features,
Sketch, Surfaces and Sheet Metal tabs, panel by panel, with what it does
and how to use it step by step — the same words the hover cards show
(tooltips.TIPS), so the page and the program cannot disagree.

    python -m khervecad.tools.ribbon_guide [OUT.md]

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys

TABS = ("features", "sketch", "surface", "sheetmetal")
INTRO = """# The ribbon, tool by tool

Every tool of the **Features**, **Sketch**, **Surfaces** and **Sheet
Metal** tabs (SolidWorks interface style: View ▸ Interface Style), in
the order the ribbon shows them. Each was pressed in the real window and
followed to the end before its steps were written. Hovering a button in
KherveCAD shows the same card.

Three habits hold everywhere:

- **Nothing selected?** Most tools then ask for a click in the 3D view —
  the face to sketch on, the edge to round, the part to move. The banner
  across the top of the view says what to click; **Esc** stops.
- **Something selected?** The tool works on it at once.
- **Ctrl+Z** takes any step back, and the numbers a tool used stay
  editable afterwards in **Properties** (bottom left).
"""


def build():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from khervecad import ribbon, toolbar_style, tooltips
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    toolbar_style.apply(win, "SolidWorks", remember=False)
    out = [INTRO]
    count = 0
    for key, _fusion, title, panels in ribbon.tab_order(False):
        if key not in TABS:
            continue
        out.append("\n## %s tab\n" % title)
        for panel in panels:
            ptitle, acts = ribbon.panel_actions(win, panel)
            acts = [a for a in acts if not a.isSeparator()
                    and a.menu() is None]
            if not acts:
                continue
            out.append("\n### %s ▸ %s\n" % (title, ptitle))
            for act in acts:
                k = act.property("kc_paint") or act.data()
                tip = tooltips.TIPS.get(k) if isinstance(k, str) else None
                name = act.text().replace("&", "").split("\t")[0]
                if not tip:
                    continue
                _t, what, steps, hint = (list(tip) + [None] * 4)[:4]
                out.append("\n**%s**  \n%s\n" % (name, what))
                for i, step in enumerate(steps or [], 1):
                    out.append("%d. %s" % (i, step))
                if hint:
                    out.append("\n*Tip:* %s" % hint)
                count += 1
    toolbar_style.apply(win, "KherveCAD", remember=False)
    win._dirty = False
    win.close()
    del app
    return "\n".join(out) + "\n", count


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    here = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    path = argv[0] if argv else os.path.join(here, "docs",
                                             "RIBBON_TOOLS.md")
    text, count = build()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("%d tools written to %s" % (count, path))


if __name__ == "__main__":
    main()

# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""The Extrude window while the regions of a sketch are picked
(SolidWorks' Selected Contours): a tool window beside the view with the
Profiles box counting the picks, OK and Cancel — never a green Done
button over the drawing (2026-11-10, the user: "we don't want to see
Done ... it's the window with all the extrude").

OK makes the feature from the picked regions; its Extrude window then
opens at the same place (ToolPanel remembers where it stood), where the
direction and depth are set."""


def _panel(window):
    return getattr(window, "_region_panel", None)


def open(window, cut, ok, cancel):
    """Show the window for a region pick; *ok* / *cancel* end it."""
    from .tool_panel import ToolPanel
    close(window)
    panel = ToolPanel(window.view3d, "Extruded Cut" if cut else "Extrude",
                      on_ok=ok, on_cancel=cancel)
    panel.hint("Click the regions in the 3D view (click one again to "
               "drop it). OK makes the %s; then set its depth."
               % ("cut" if cut else "extrude"))
    panel.selection("profiles", "Profiles", "")
    panel.set_active("profiles")
    panel.finish()
    window._region_panel = panel
    update(window, 0)
    panel.open()
    return panel


def update(window, count, text=None):
    panel = _panel(window)
    if panel is None:
        return
    panel.boxes["profiles"].set_text(
        text or ("%d region(s) picked" % count if count else
                 "Click the regions to use"))
    panel.set_ok_enabled(count > 0)


def close(window):
    panel = _panel(window)
    window._region_panel = None
    if panel is not None:
        panel.hide()
        panel.deleteLater()


def ok_button(window):
    """The window's OK (tests, MCP), or None."""
    panel = _panel(window)
    return panel.ok if panel is not None else None

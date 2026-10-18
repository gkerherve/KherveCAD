"""Detailed hover help for the Blueprint window's buttons: what each does,
numbered how-to steps and a tip — the same layout as the 3D view's
(`tooltips.rich`), keyed by the button's label.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

WIDTH = 360
#: replaced by the shortcut span once the action knows its key
KEY_MARK = "<!--KEY-->"

#: label -> (steps, tip)
HELP = {
    "Export PDF": (
        ["Click Export PDF (Ctrl+E) and choose a file name.",
         "Open it anywhere: lines stay sharp at any zoom."],
        "The paper size and style you picked are used as they are."),
    "Export DXF": (
        ["Click Export DXF and choose a file name.",
         "Open it in any CAD or CAM program; each kind of line is on "
         "its own layer (VISIBLE, HIDDEN, CENTER, DIM, TEXT)."],
        "Units are sheet millimetres, at the drawing's scale."),
    "Export SVG": (
        ["Click Export SVG and choose a file name.",
         "Edit it in Inkscape or drop it into a web page."], None),
    "Export PNG": (
        ["Click Export PNG and choose a file name."],
        "8 pixels per millimetre: an A4 sheet is about 2400 × 1700."),
    "Print": (
        ["Click Print (Ctrl+P) and pick the printer.",
         "The sheet is fitted to the page."],
        "Choose the paper size first so the scale stays true."),
    "Delete": (
        ["Select a view or an annotation.",
         "Click Delete, or press the Delete key."],
        "Deleting a view also removes its dimensions. Ctrl+Z brings "
        "them back."),
    "Update from model": (
        ["Edit the 3D model as you like.",
         "When the ⚠ warning appears, click Update (F5)."],
        "Your dimensions, notes and view positions are kept; only the "
        "projected lines are redrawn."),
    "Auto-dimension": (
        ["Click Auto-dimension.",
         "The overall width, depth and height and every hole's "
         "diameter appear, with centre marks.",
         "Drag any label to move it; delete the ones you do not want."],
        "Running it again replaces only what it added before — your "
        "own dimensions stay."),
    "Auto-arrange": (
        ["Click Auto-arrange.",
         "The views go back to the standard third-angle layout at the "
         "largest scale that fits."],
        "Handy after you have dragged views about or changed the "
        "paper size."),
    "Hidden lines": (
        ["Click to switch the dashed hidden edges on or off."],
        "Turn them off for threaded or very detailed parts: it makes "
        "the sheet much faster to draw."),
    "Make all part drawings": (
        ["Click once.",
         "Every Object without a drawing gets its own sheet, with its "
         "own title block, parts list and balloons."],
        "Pick any of them in the Drawing list afterwards."),
    "Export drawing set": (
        ["Click Export drawing set….",
         "Choose one multi-page PDF, or a folder of PDF / DXF / SVG / "
         "PNG files — one per drawing."], None),
    "Undo": (
        ["Click Undo (Ctrl+Z) to take back the last change to the "
         "sheet — a dimension, a moved view, a deleted note."],
        "Every step is kept for the whole session of this window."),
    "Redo": (
        ["Click Redo (Ctrl+Y) to bring back what Undo took away."],
        None),
    "Zoom in": (
        ["Click, or press Ctrl++.",
         "Or turn the mouse wheel to zoom about the cursor."], None),
    "Zoom out": (
        ["Click, or press Ctrl+-.",
         "Or turn the mouse wheel."], None),
    "Fit sheet": (
        ["Click Fit sheet (F) to show the whole sheet."], None),
    "Projected view": (
        ["Click the button and pick Front, Top, Right, Left, Back, "
         "Bottom or Isometric.",
         "The view lands on the sheet; drag it where you want it."],
        "Top and Right stay aligned with Front when you drag them, as "
        "a drawing standard requires."),
    "Section view": (
        ["Click the button and pick the axis the part is cut across.",
         "A hatched cut through the middle appears, with its cutting "
         "line drawn on the view it cuts."],
        "A section is the best way to show a bore, a wall thickness or "
        "a thread."),
    "Shaded picture": (
        ["Click Shaded picture.",
         "A coloured isometric picture of the model is added; drag it "
         "to a free corner of the sheet."],
        "It is painted the way the 3D view paints it, so colours and "
        "materials match."),
    "Parts list": (
        ["Click Parts list.",
         "The bill of materials appears above the title block: item, "
         "part number, name, material, quantity and mass."],
        "Balloons on the views refer to its item numbers."),
    "Title block": (
        ["Click Title block.",
         "Fill in the title, drawing number, material, finish, and who "
         "drew and checked it."],
        "Material, company and author are remembered for the next "
        "drawing."),
    "Select / Move": (
        ["Click a view or an annotation to select it; its settings open "
         "in Properties.",
         "Drag a view to move it; drag a dimension or note by its label.",
         "Arrow keys nudge it, Shift+arrow moves 10 mm, Delete removes "
         "it."],
        "Press Esc from any other tool to come back here."),
    "Pan": (
        ["Click Pan, then drag to slide the sheet around."],
        "The middle mouse button pans with any tool, and the wheel "
        "zooms."),
    "Smart dimension": (
        ["Click a round edge for Ø (or R), a straight edge for its "
         "length, or two points for their distance.",
         "Move the mouse: above or below gives a horizontal dimension, "
         "left or right a vertical one, anywhere else an aligned one.",
         "Click again to place the number."],
        "Points snap to corners, midpoints, centres and quadrants — a "
        "marker shows what you will hit."),
    "Horizontal dimension": (
        ["Click the first point, then the second.",
         "Move up or down to set the dimension line, and click to "
         "place it."],
        "The number is the model's real distance at any drawing scale."),
    "Vertical dimension": (
        ["Click the first point, then the second.",
         "Move left or right to set the dimension line, and click to "
         "place it."], None),
    "Aligned dimension": (
        ["Click the first point, then the second.",
         "Move away from the line to set the offset, and click to "
         "place it."],
        "Use it for sloped edges, where horizontal or vertical would "
        "give the wrong length."),
    "Diameter": (
        ["Click the rim of a hole or boss.",
         "Click where the Ø number should go."],
        "Several identical holes are grouped by Auto-dimension as "
        "'4× Ø6'."),
    "Radius": (
        ["Click the arc or fillet.",
         "Click where the R number should go."], None),
    "Angle": (
        ["Click the first straight edge, then the second.",
         "Click where the angle arc should go."], None),
    "Note with leader": (
        ["Click the feature the note points at.",
         "Click where the text goes, then type it — for example '4 "
         "HOLES THROUGH' or 'BREAK EDGES'."],
        "Double-click a note later to edit its text."),
    "Text": (
        ["Click where the text goes, then type."],
        "Good for general notes and revision remarks. Set size and "
        "style in Properties."),
    "Balloon": (
        ["Click the part, then where the balloon goes.",
         "Type or confirm its item number."],
        "The number matches the parts list; the ring placement avoids "
        "your views."),
    "Centre mark": (
        ["Click a round edge — the chain-line cross appears at its "
         "centre."], None),
    "Centre line": (
        ["Click one end of the axis, then the other."],
        "Use it for axes of symmetry and bolt-circle centres."),
    "Surface finish": (
        ["Click the surface's edge.",
         "Pick the roughness (Ra) in the box that opens."],
        "Drawn as the ISO 1302 symbol."),
    "Datum feature": (
        ["Click the datum edge, then where the letter goes."],
        "Geometric tolerances refer to datums by their letter."),
    "Geometric tolerance": (
        ["Click the feature, then where the frame goes.",
         "Choose the symbol (position, flatness…), the tolerance value "
         "and the datums."],
        "Drawn as an ISO 1101 feature control frame."),
    "Line": (
        ["Click the start, then the end.",
         "Set thick, thin, dashed or chain in Properties."], None),
    "Rectangle": (
        ["Click one corner, then the opposite one."],
        "A frame round a note or a table."),
    "Circle": (
        ["Click the centre, then a point on the rim."], None),
    "Detail view": (
        ["Click the centre of the small area to enlarge, then drag out "
         "to its edge.",
         "The enlarged view (2:1) appears; drag it where it fits.",
         "A lettered circle marks the area on the parent view."],
        "Use it for small features that are unreadable at the sheet's "
        "scale."),
    # -- the toolbar's drop-downs and pickers
    "Sheet": (
        ["Pick a paper size: A4, A3, Letter…"],
        "Landscape. Views are re-arranged to fit the new paper."),
    "Scale": (
        ["Pick Best fit, or a standard scale such as 1:2 or 5:1.",
         "Or type any ratio — 1:7, 1:333, 3:1."],
        "The title block's SCALE follows."),
    "Style": (
        ["Pick White paper or the classic Blueprint blue."],
        "Exports follow the style you choose."),
    "Drawing": (
        ["Pick the assembly drawing, or one Object's own part drawing.",
         "A part drawing is made the first time you pick it."],
        "● marks drawings already made, ○ those not yet."),
}


def html(title, what, how="", shortcut=""):
    """The tooltip: title, what it does, numbered steps, a tip."""
    steps, tip = HELP.get(title, ([how] if how else [], None))
    keys = (f" &nbsp;<span style='color:#8a8a8a'>{shortcut}</span>"
            if shortcut else KEY_MARK)
    parts = [f"<b>{title}</b>{keys}",
             f"<p style='margin:4px 0 0 0'>{what}</p>"]
    if steps:
        items = "".join(f"<li>{s}</li>" for s in steps)
        parts.append("<p style='margin:6px 0 0 0'><b>How to use</b></p>"
                     f"<ol style='margin:2px 0 0 0'>{items}</ol>")
    if tip:
        parts.append("<p style='margin:4px 0 0 0; color:#8a8a8a'>"
                     f"<i>Tip:</i> {tip}</p>")
    return (f"<table width='{WIDTH}' cellspacing='0' cellpadding='0'>"
            f"<tr><td>{''.join(parts)}</td></tr></table>")

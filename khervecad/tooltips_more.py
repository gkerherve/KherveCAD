"""Step-by-step help for the ribbon tools that had only a one-line card
(2026-11-09, the user: "go through every tool in the ribbon ... explain
in detail how to use it" — Features, Sketch, Surfaces, Sheet Metal).

Each entry was written after pressing the tool in the real window and
following it to the end: the later sketch shapes, the six surfaces from
curves, every sheet metal command, the Gumball and the simple sheet
metal part. Same shape as tooltips.TIPS — key -> (title, what it does,
steps, tip) — and merged into it from the bottom of tooltips.py, so the
hover cards, the status line and the User Guide's tool reference all
read them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

_IN_SKETCH = ("Open a sketch first: Sketch Mode, then click a plane or a "
              "flat face.")

TIPS = {
    # ------------------------------------------------------------ sketch
    "construction_line": (
        "Centerline",
        "A dashed reference line. Relations and dimensions use it — a "
        "mirror line, a centre to dimension from, an axis to revolve "
        "about — but it is never part of the solid.",
        [_IN_SKETCH,
         "Click where the centerline starts.",
         "Click where it ends. It snaps level, upright and onto points "
         "like the Line.",
         "Use it: Mirror Entities about it, Symmetric, or Smart "
         "Dimension from it."],
        "Any line can be switched to a centerline afterwards with "
        "Construction (Modify panel)."),
    "point": (
        "Point",
        "A sketch point: a small construction mark to dimension to, to "
        "make other shapes Coincident with, or to mark a hole's centre.",
        [_IN_SKETCH,
         "Click where the point goes — it snaps to ends, middles, "
         "centres and the origin.",
         "Smart Dimension it from an edge or the origin to place it "
         "exactly."],
        "It is construction geometry: an extrude ignores it."),
    "polyline": (
        "Polyline",
        "Straight lines joined end to end in one go, kept together as "
        "one Polyline group with their ends Coincident.",
        [_IN_SKETCH,
         "Click the first point, then every corner in turn.",
         "Backspace takes the last point back.",
         "Enter, right-click or double-click ends it; click the first "
         "point again to close the outline."],
        "For lines that also turn into arcs on the way, use Line."),
    "rect_3pt": (
        "3 Point Corner Rectangle",
        "A rectangle at any angle: two clicks give one side, the third "
        "its depth.",
        [_IN_SKETCH,
         "Click one corner.",
         "Click the next corner — this first side may lean at any "
         "angle.",
         "Move away from that side and click to set the depth."],
        "Square to the axes? Corner Rectangle is one click fewer."),
    "circle_2pt": (
        "2-point circle",
        "A circle from the two ends of its diameter — when you know "
        "what it must pass through, not where its centre is.",
        [_IN_SKETCH,
         "Click one end of the diameter.",
         "Click the opposite end: the circle passes through both."],
        "Give it a size afterwards with Smart Dimension (click the "
        "circle, then empty space)."),
    "circle_3pt": (
        "Perimeter Circle",
        "A circle through three points on its rim. Clicked on three "
        "lines or sides instead, it becomes the circle touching all "
        "three and stays Tangent to them.",
        [_IN_SKETCH,
         "Click a first point on the rim (or a first line).",
         "Click a second.",
         "Click a third: the circle through the three is drawn."],
        "Three sides of a triangle give its inscribed circle."),
    "circle_tangent": (
        "Tangent circle",
        "The circle that touches three lines — the round that fits "
        "exactly into a corner or a triangle.",
        [_IN_SKETCH,
         "Click the first line.",
         "Click the second line.",
         "Click the third: the circle touching all three appears."],
        "The lines may be sides of a polygon or rectangle."),
    "arc_tangent": (
        "Tangent arc",
        "An arc that carries on smoothly from the end of a line, with "
        "no kink where they meet.",
        [_IN_SKETCH,
         "Click near the END of the line to go on from.",
         "Move: the arc follows the cursor, leaving the line in its own "
         "direction.",
         "Click where the arc ends. Straight across from the end gives "
         "a half circle."],
        "While drawing with Line, bring the mouse back onto the last "
        "point and out again (or press A) for the same arc without "
        "changing tool."),
    "poly_reg": (
        "Polygon",
        "A regular polygon — triangle, square, hexagon… — from its "
        "centre and one corner.",
        [_IN_SKETCH,
         "Click the centre.",
         "Click where one corner goes: that sets the size and the "
         "turn.",
         "Type the number of sides when asked (6 = a hexagon)."],
        "Polygon (free) draws any outline corner by corner instead."),
    "bspline": (
        "Style Spline",
        "A smooth curve PULLED towards the points you click without "
        "passing through them — gentler than Spline, good for styled "
        "outlines.",
        [_IN_SKETCH,
         "Click the control points in order; the curve starts at the "
         "first and ends at the last.",
         "Backspace takes a point back.",
         "Enter, right-click or double-click ends it."],
        "Spline is the one that goes THROUGH every clicked point."),
    "conic": (
        "Conic",
        "One smooth bow between two points — a piece of an ellipse — "
        "shaped by where its two end directions would meet.",
        [_IN_SKETCH,
         "Click where the curve starts.",
         "Click where it ends.",
         "Click the shoulder: the point both ends aim at. Further out "
         "gives a fuller bow."],
        "Handy for a blend between two straight lines that is softer "
        "than a round."),
    # ---------------------------------------------------------- surfaces
    "srf_loft": (
        "Loft (surface from curves)",
        "A skin stretched through two or more 3D curves, in the order "
        "you selected them — a hull, a duct, a blade.",
        ["Draw the curves with 3D Sketch (Curves panel), one per "
         "section.",
         "Select them in the tree in order: click the first, Ctrl+click "
         "the next ones.",
         "Click Loft. The skin is made with a wall thickness, so it is "
         "a real solid.",
         "In Properties change the Wall thickness, tick Ruled for "
         "straight sides, or Capped to close a loft of closed curves "
         "into a solid."],
        "The curves stay inside the surface: edit a curve's points and "
        "the surface follows."),
    "srf_sweep": (
        "Sweep (surface from curves)",
        "Drives a profile curve along a rail curve — a pipe, a moulding, "
        "a handle.",
        ["Draw the rail (the path) and the profile with 3D Sketch.",
         "Select the RAIL first, then Ctrl+click the profile.",
         "Click Sweep.",
         "Set the Wall thickness in Properties; a closed profile "
         "sweeps a solid bar."],
        "For a round pipe, Swept Boss/Base on the Features tab needs "
        "only the path and a circle."),
    "srf_sweep2": (
        "Sweep along two rails",
        "Like Sweep, but the profile is stretched between TWO rails as "
        "it travels, so the surface widens and narrows with them.",
        ["Draw the two rails and one profile that reaches from one "
         "rail to the other.",
         "Select rail 1, Ctrl+click rail 2, then Ctrl+click the "
         "profile.",
         "Click Sweep along two rails.",
         "Adjust the Wall thickness in Properties."],
        "Start both rails at the profile's two ends."),
    "srf_patch": (
        "Patch (surface from curves)",
        "Fills the inside of a closed curve with a smooth surface — a "
        "lid, a filled hole, a panel between edges.",
        ["Draw one CLOSED 3D curve (press C to close it while "
         "drawing); it need not be flat.",
         "Select it. Ctrl+click other curves the surface must pass "
         "through, if any.",
         "Click Patch.",
         "Set the Wall thickness in Properties."],
        "An open curve cannot be patched — close it first."),
    "srf_revolve": (
        "Revolve (surface from curves)",
        "Turns a curve about the Z axis: a bowl, a vase, a bell.",
        ["Draw the curve as the profile seen from the side, away from "
         "the Z axis (it must not cross it).",
         "Select it and click Revolve.",
         "In Properties set the Angle (360 = all the way round) and "
         "the Wall thickness."],
        "Revolved Boss/Base on the Features tab revolves a flat sketch "
        "shape into a solid instead."),
    "srf_extrude": (
        "Extrude (surface from curves)",
        "Pushes a curve straight up into a wall; a closed curve "
        "becomes a solid block.",
        ["Draw the curve with 3D Sketch.",
         "Select it and click Extrude.",
         "Set the Height and the Wall thickness in Properties."],
        "A curved fence, a rib, a shaped wall from one stroke."),
    # ------------------------------------------------------- sheet metal
    "sm_base": (
        "Base Flange/Tab",
        "The flat sheet every sheet metal part starts from. With a "
        "sketch shape selected (rectangle, polygon, circle) the sheet "
        "takes that outline; with nothing selected it is 100 × 60 mm.",
        ["Optional: draw the outline in a sketch and select it.",
         "Click Base Flange/Tab — a 2 mm sheet appears and stays "
         "selected.",
         "In Properties set the Thickness, Bend radius and K-factor "
         "(or apply a rule with Sheet Metal Rules).",
         "Go on with Edge Flange, Hem or Fold."],
        "Unfold shows the flat blank at any time."),
    "sm_convert": (
        "Convert to Sheet Metal",
        "Turns a plate you already have — a thin cube or a sketch shape "
        "extruded to the sheet's thickness — into a sheet metal body, "
        "in the same place, so it can take flanges and unfold.",
        ["Select the plate in the tree.",
         "Click Convert to Sheet Metal.",
         "Its thinnest side becomes the thickness; the status bar says "
         "what it found."],
        "A cube standing on edge is converted standing on edge."),
    "sm_flange": (
        "Edge Flange",
        "Bends a wall up (or down) from an edge of the sheet, with the "
        "bend radius and allowance worked out for you.",
        ["Select the sheet metal body (the only one in view is taken "
         "by itself).",
         "Click Edge Flange, then click the edge in the 3D view — Esc "
         "lets you choose it from a list instead.",
         "In the window set the Height (to the outside), the Angle "
         "(90 = square; negative bends down), the Bend radius and, to "
         "stop short of the corners, the two Insets.",
         "OK: the wall is added and the status bar gives the new flat "
         "blank size."],
        "A flange's own outer edge can take another flange — that is "
        "how a box lip is made."),
    "sm_fold": (
        "Fold",
        "Bends the flat sheet along a line across it (SolidWorks' "
        "Sketched Bend). The outline stays the flat blank; the bend "
        "allowance is centred on the line.",
        ["Select the sheet metal body while it is still flat.",
         "Click Fold.",
         "Give the bend line by its two ends (X, Y on the sheet — it "
         "starts as a line across the middle), the Angle and the Bend "
         "radius.",
         "OK."],
        "Fold BEFORE adding flanges or hems: a fold changes the edges "
        "they sit on, and is refused afterwards."),
    "sm_hem": (
        "Hem",
        "Folds an edge right back over itself — a safe, stiff, rounded "
        "edge — leaving the rule's hem gap inside.",
        ["Select the sheet metal body.",
         "Click Hem, then click the edge in the 3D view.",
         "Set the Length of the folded-back strip; tick Fold under to "
         "turn it down instead of over.",
         "OK."],
        "The hem gap comes from the body's rule (Sheet Metal Rules)."),
    "sm_path": (
        "Path Flange",
        "Several flanges in a row off one edge, a bend at every corner "
        "— a Z, a return lip, a channel — typed as length, angle "
        "pairs.",
        ["Select the sheet metal body.",
         "Click Path Flange, then click the edge.",
         "Type the segments as “length, angle; length, angle”: "
         "20, 90; 10, 90 goes up 20 then turns in 10.",
         "OK."],
        "A negative angle bends the other way: 20, 90; 10, -90 is a Z."),
    "sm_contour": (
        "Contour Flange",
        "A NEW sheet metal body from an open profile seen from the "
        "side — a channel, a Z or a hat section — with one bend at "
        "every corner, stretched to a width.",
        ["Click Contour Flange (nothing needs selecting).",
         "Type the profile's points as “X, Z; X, Z; …” in order: "
         "0, 30; 0, 0; 50, 0; 50, 30 is a U channel 50 wide, 30 high.",
         "Set the Width (how long the section runs).",
         "OK: the body is made and can take edge flanges and hems."],
        "Keep the corners square to start; the bend radius rounds "
        "them."),
    "sm_perforate": (
        "Perforate",
        "A field of round holes over the flat sheet, kept clear of the "
        "edges and the bends — in the part, the flat pattern and the "
        "DXF.",
        ["Select the sheet metal body.",
         "Click Perforate.",
         "Set the Hole diameter, the Pitch (centre to centre — more "
         "than the diameter), the Margin and Staggered or Square.",
         "OK: the status bar counts the holes; Unfold shows them on "
         "the blank."],
        "Run it again to change the field: it replaces the last one."),
    "sm_flat": (
        "Create Flat Pattern",
        "Puts a flat copy of the body beside it: the blank to cut, "
        "with its bend lines, while the folded part stays as it is.",
        ["Select the sheet metal body.",
         "Click Create Flat Pattern.",
         "The status bar gives the blank's size and the number of "
         "bends."],
        "For the cutting file use Export Flat Pattern as DXF."),
    "sm_unfold": (
        "Unfold",
        "Shows the selected body flat — every bend opened out — to "
        "check the blank and its holes.",
        ["Select the sheet metal body.",
         "Click Unfold.",
         "Click Refold to fold it back up."],
        "Nothing is lost: it is the same body, shown flat."),
    "sm_refold": (
        "Refold",
        "Folds an unfolded body back up to its bent shape.",
        ["Select the unfolded sheet metal body.",
         "Click Refold."],
        None),
    "sm_rules": (
        "Sheet Metal Rules",
        "Named sets of thickness, bend radius, K-factor and hem gap — "
        "“Steel 2 mm”, “Aluminium 1.5 mm”. A body given a rule follows "
        "it: change the rule and every such body changes.",
        ["Click Sheet Metal Rules.",
         "New… adds a rule; select one to edit its four values.",
         "With a sheet metal body selected, apply the rule to it.",
         "Close."],
        "The rules are document variables, so they are saved with the "
        "file and written into the OpenSCAD program."),
    "sm_dxf": (
        "Export Flat Pattern as DXF",
        "Writes the flat blank for a laser or punch: CUT outlines and "
        "holes, BEND_UP and BEND_DOWN lines and ETCH notes on their own "
        "layers, in millimetres.",
        ["Select the sheet metal body.",
         "Click Export Flat Pattern as DXF.",
         "Choose where to save the file."],
        "Send the bend table with it so the folder knows each angle."),
    "sm_bend_table": (
        "Export Bend Table",
        "Every bend as a CSV table: direction, angle, radius, length, "
        "allowance and where its centre line lies on the flat blank.",
        ["Select the sheet metal body.",
         "Click Export Bend Table.",
         "Choose where to save the file; open it in any spreadsheet."],
        None),
    # ------------------------------------------------------------ others
    "sheet_metal": (
        "Sheet metal part (simple)",
        "A plate with one flange on each of its four edges, set by "
        "numbers — the quick way to a tray or a bracket. The Sheet "
        "Metal tab makes anything more.",
        ["Click it: a plate with flanges appears as a new part.",
         "In Properties set the plate size, Thickness, Bend radius and "
         "each edge's flange length and angle (0 = no flange, negative "
         "= bent down).",
         "Right-click it in the tree ▸ Unfold for the flat blank, or "
         "Export flat pattern DXF."],
        "Convert to Sheet Metal (Sheet Metal tab) turns it into a full "
        "sheet metal body."),
    "gumball": (
        "Gumball",
        "Arrows and rings on the selected part, to move and turn it by "
        "hand in the 3D view.",
        ["Select a part, then switch the Gumball on.",
         "Drag an arrow to move along that axis, a ring to turn about "
         "it. Hold Ctrl to snap to the grid and to 15°.",
         "Esc while dragging puts the part back. Drag anywhere else to "
         "orbit as usual.",
         "Switch it off with the same button."],
        "Exact values go in Properties (Position / Rotation)."),
}

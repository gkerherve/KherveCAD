"""Help for the buttons floating on the 2D sketch and the 3D preview.

Same shape as `tooltips.TIPS` (title, what, steps, tip); `tooltips`
merges these in, so `tooltips.apply(button, key)` works for them too.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

_PAN_2D = ("Scrolls the sketch by a step. Hold the button to keep going.",
           ["Click once for one step, or hold for a steady glide.",
            "Middle-mouse drag pans freely without the buttons."],
           "The mouse wheel zooms about the cursor.")
_PAN_3D = ("Slides the camera sideways or up/down without turning the "
           "model. Hold the button to keep going.",
           ["Click once for one step, or hold for a steady glide.",
            "Right-drag or middle-drag in the view pans freely."],
           "Orbit with a left-drag; the wheel zooms.")

NAV_TIPS = {
    # ------------------------------------------------------------ 2D bar
    "nav2d_hand": (
        "Pan (hand)",
        "Moves the VIEW of the sketch, never the drawing: while the hand "
        "is on, drag anywhere to slide the sketch.",
        ["Click the hand.", "Drag in the sketch.",
         "Click the hand again to draw or select."],
        "Middle-mouse drag pans at any time."),
    "nav3d_hand": (
        "Pan (hand)",
        "Slides the camera, never the model: while the hand is on, drag "
        "anywhere to move the view without turning it.",
        ["Click the hand.", "Drag in the 3D view.",
         "Click the hand again to orbit with a left drag."],
        "Right- or middle-drag pans at any time."),
    "nav2d_left": ("Scroll left",) + _PAN_2D,
    "nav2d_right": ("Scroll right",) + _PAN_2D,
    "nav2d_up": ("Scroll up",) + _PAN_2D,
    "nav2d_down": ("Scroll down",) + _PAN_2D,
    "nav2d_zoom_in": (
        "Zoom in",
        "Magnifies the sketch about the centre of the view, down to "
        "sub-millimetre detail.",
        ["Click (or hold) to zoom in step by step.",
         "Or turn the mouse wheel to zoom about the cursor, or press "
         "Ctrl++."],
        "The scale bar and the grid follow the zoom."),
    "nav2d_zoom_out": (
        "Zoom out",
        "Pulls back so you see more of the sketch — up to a whole "
        "house or site plan.",
        ["Click (or hold) to zoom out step by step.",
         "Or turn the mouse wheel, or press Ctrl+-."],
        None),
    "nav2d_focus": (
        "Focus",
        "Frames the selected part wherever it is, or the whole sketch "
        "when nothing is selected.",
        ["Select a part in the tree or the sketch.",
         "Click Focus — the view zooms to it."],
        "Handy after a long pan, when you have lost the part."),
    "nav2d_fit": (
        "Fit all",
        "Zooms so everything in the sketch is in sight.",
        ["Click Fit all (Ctrl+Shift+F)."],
        None),
    "plane_top": (
        "Top view (XY)",
        "Shows the model from above. Shapes you draw land on the X–Y "
        "plane, and 3D parts appear as outlines you can drag.",
        ["Click Top.",
         "Draw, or drag a part's outline to move it along X and Y."],
        "The X axis is red, Y green, Z blue — in the corner gizmo too."),
    "plane_front": (
        "Front view (XZ)",
        "Shows the model from the front. Shapes land on the X–Z plane "
        "— the plane for elevations and profiles.",
        ["Click Front.",
         "Draw, or drag a part's outline to move it along X and Z."],
        "Selecting a bore or a revolve profile jumps here by itself."),
    "plane_side": (
        "Side view (YZ)",
        "Shows the model from the side. Shapes land on the Y–Z plane.",
        ["Click Side.",
         "Draw, or drag a part's outline to move it along Y and Z."],
        None),
    "grid_bar": (
        "Grid",
        "Shows or hides the grid in the sketch. The arrow beside it "
        "sets the spacing.",
        ["Click the icon to switch the grid on or off (Ctrl+').",
         "Click the arrow to choose 0.1, 0.2, 0.5, 1 … 100 mm, or "
         "Custom… for any value."],
        "Turn Snap on to make drawn points land on grid lines."),
    "snap_bar": (
        "Snap to grid",
        "Makes the points you draw and drag land on the grid, so sizes "
        "come out as round numbers.",
        ["Click Snap (Ctrl+Shift+') to switch it on or off.",
         "Pick a finer or coarser grid with the Grid arrow."],
        "Hold the grid at 0.1 mm for fine work, 10 mm for layouts."),
    # ------------------------------------------------------------ 3D bar
    "nav3d_top": (
        "Top view",
        "Looks straight down on the model, as in a plan.",
        ["Click the cube with the top face lit."],
        "The 2D sketch's Top button shows the same plane."),
    "nav3d_front": (
        "Front view",
        "Looks at the model from the front (the -Y side), as in an "
        "elevation.",
        ["Click the cube with the front face lit."],
        None),
    "nav3d_side": (
        "Side view",
        "Looks at the model from its right-hand side (the +X side).",
        ["Click the cube with the right face lit."],
        "View ▸ 3D View also has Back, Left, Bottom and Isometric."),
    "nav3d_orbit_left": (
        "Turn left",
        "Turns the model to the left about the vertical axis.",
        ["Click (or hold) to keep turning.",
         "Or left-drag in the view for free orbiting."],
        "The View menu has the standard Front, Top, Isometric… views."),
    "nav3d_orbit_right": (
        "Turn right",
        "Turns the model to the right about the vertical axis.",
        ["Click (or hold) to keep turning.",
         "Or left-drag in the view for free orbiting."],
        None),
    "nav3d_left": ("Pan left",) + _PAN_3D,
    "nav3d_right": ("Pan right",) + _PAN_3D,
    "nav3d_up": ("Pan up",) + _PAN_3D,
    "nav3d_down": ("Pan down",) + _PAN_3D,
    "nav3d_zoom_in": (
        "Zoom in",
        "Moves the camera closer to the model.",
        ["Click (or hold) to zoom in, or turn the mouse wheel."],
        None),
    "nav3d_zoom_out": (
        "Zoom out",
        "Moves the camera back to see more.",
        ["Click (or hold) to zoom out, or turn the mouse wheel."],
        None),
    "nav3d_focus": (
        "Focus",
        "Frames the selected part, or the whole model when nothing is "
        "selected.",
        ["Select a part in the tree.",
         "Click Focus — the camera moves to it."],
        "Good for inspecting a small part inside a big assembly."),
    "nav3d_fit": (
        "Fit all",
        "Frames the whole model (platform and shadow included when "
        "they are on).",
        ["Click Fit all, press Ctrl+F, or double-click the view."],
        None),
    "nav3d_stage": (
        "Platform & shadow",
        "Stands the model on a round platform with a soft shadow, lit "
        "from the far top left — a presentation look. Only the picture "
        "changes.",
        ["Click to switch it on or off (also View ▸ 3D Platform & "
         "Shadow)."],
        "Pictures exported to PNG and Printables use it too."),
    "nav3d_explode": (
        "Exploded view",
        "Pulls the parts of an assembly apart to show how they go "
        "together. Only the picture changes — the model is untouched.",
        ["Click the icon (Ctrl+Shift+X) to explode or collapse.",
         "Select a part first to explode just the assembly it belongs "
         "to.",
         "Click the arrow for the distance and the direction: radial, "
         "or along X, Y or Z."],
        "Export PNG and the Printables bundle can include exploded "
        "stills."),
    "nav3d_cut": (
        "Cut through",
        "Slices the 3D view with a plane, hides one half and fills the "
        "cut face in red, so you can see how the part is made inside — "
        "holes, walls, bores, threads, how parts sit in each other. "
        "Only the picture is cut: the model, exports and drawings stay "
        "whole.",
        ["Click the icon (Ctrl+Alt+X).",
         "Pick X, Y or Z on the bar along the bottom of the 3D view — "
         "or in the arrow's menu.",
         "Drag the slider to move the cut through the model.",
         "⇄ keeps the other half; ✕ (or the icon again) shows the whole "
         "model."],
        "Orbit while it is cut: the red face is the section, the rest "
        "is the inside of the part."),
    "nav3d_display": (
        "Display options",
        "How the 3D picture is drawn — the same switches as the View "
        "menu. None of them changes the model.",
        ["Click to open the list and tick what you want:",
         "Platform & shadow, cavity shading (dark creases), edge lines, "
         "scale bar, smooth shading, reference-image overlay and "
         "hardware (OpenGL) rendering."],
        "Turn hardware rendering off if the view ever looks wrong on "
        "an old graphics card."),
}

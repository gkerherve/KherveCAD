"""What every toolbar icon does, and how to use it.

Each entry is (title, what it does, [how-to steps], tip). `rich()` turns
one into the HTML tooltip the icon shows on hover — wide enough to read,
with the steps numbered — and `summary()` gives the one-line status-bar
text. The Help ▸ User Guide covers the same tools at length; these are
the version you get without leaving the canvas.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: tooltip width in pixels — QToolTip otherwise lays a long paragraph
#: out on a single line as wide as the screen
WIDTH = 360

_SELECTION = ("Select the object(s) in the tree (Ctrl-click to add "
              "more), or click one in the 2D view.")

TIPS = {
    # ------------------------------------------------------ drawing tools
    "select": (
        "Select / move",
        "Pick, move and resize things in the 2D view. Whatever you pick "
        "is selected everywhere at once — tree, Properties, 2D and 3D.",
        ["Click a shape to select it; its settings open in Properties.",
         "Drag it to move it; drag a square handle to resize it.",
         "In the assembly plane, drag a part's outline to place it.",
         "Middle-mouse drag pans the view, the wheel zooms."],
        "Press V to come back to this tool from any other."),
    "line": (
        "Line",
        "Draws a straight bar between two points. It is a real 2D solid "
        "(a hull of two circles), so it can be extruded like any shape.",
        ["Press where the line starts.",
         "Drag to the end point — the length shows in the status bar.",
         "Release. Set its thickness (Width) in Properties.",
         "Use Extrude to turn it into a 3D rod or wall."],
        "Turn Snap on to land the ends on round grid values."),
    "rect": (
        "Rectangle",
        "Draws a rectangle on the sketch plane — the usual start of a "
        "plate, a box or a bracket.",
        ["Press at one corner.",
         "Drag to the opposite corner; the size reads live in mm.",
         "Release, then type exact Width/Height in Properties.",
         "Extrude it to give it thickness."],
        None),
    "circle": (
        "Circle",
        "Draws a circle, or a part of one (a quarter, a semicircle) — "
        "rods, discs, holes and arcs.",
        ["Press at the centre.",
         "Drag outwards to the radius (r and Ø show live).",
         "Release. In Properties, Angle 180 makes a semicircle, 90 a "
         "quarter; Segments sets how smooth it is."],
        "A circle inside a Difference cuts a round hole."),
    "polygon": (
        "Polygon",
        "Draws any straight-sided outline, one corner at a time — "
        "gussets, profiles, custom brackets.",
        ["Click each corner in turn.",
         "Double-click (or press Enter) to close the shape — at least "
         "three corners.",
         "Esc abandons it.",
         "Edit any corner exactly in the points table in Properties."],
        None),
    "text": (
        "Text",
        "Places a line of lettering on the sketch — labels, name "
        "plates, stamps.",
        ["Click where the text should start.",
         "Type the words and the Size in Properties.",
         "Extrude it to make raised or engraved lettering."],
        "Put extruded text in a Difference to engrave it into a part."),
    "measure": (
        "Measure distance",
        "Measures between two points without changing the model. It "
        "snaps to corners and edges of the shapes.",
        ["Click the first point.",
         "Move the mouse — the distance updates live in the status bar.",
         "Click the second point to freeze the reading.",
         "Click again to start a new measurement."],
        None),
    "dimension": (
        "Add dimension",
        "Like Measure, but leaves a dimension line with its length on "
        "the sketch, so the size stays visible.",
        ["Click the first point (it snaps to corners and edges).",
         "Click the second point — the dimension is placed.",
         "View ▸ Clear Dimensions removes them all."],
        None),

    # ---------------------------------------------------------- 3D solids
    "cube": (
        "Cube (box)",
        "Adds a box — the most common starting block.",
        ["Click. In the Main tab it becomes a new Object and the Object "
         "tab opens on it; in the Object tab it is added to the part you "
         "are editing.",
         "Set Width (X), Depth (Y) and Height (Z) in Properties.",
         "X/Y/Z move it; Center puts its middle on that point instead "
         "of its corner."],
        None),
    "sphere": (
        "Sphere",
        "Adds a ball — eyes, knobs, joints, domes.",
        ["Click to add it at the origin (see Cube for where it lands).",
         "Set the Radius; X/Y/Z move its centre.",
         "Segments sets smoothness (more = rounder, slower)."],
        None),
    "cylinder": (
        "Cylinder / cone",
        "Adds a cylinder — shafts, legs, pins, holes. A different top "
        "radius makes a cone (0 comes to a point).",
        ["Click to add it (see Cube for where it lands).",
         "Set Height and the bottom and top radius.",
         "Center stands it on its middle instead of its base."],
        "Inside a Difference, a cylinder drills a hole."),
    "capsule": (
        "Capsule",
        "A rod with rounded ends between two points — arms, legs, "
        "fingers, handles.",
        ["Click to add it.",
         "Set the Start and End points and the Radius.",
         "Wrap it in a Joint to pose it, or a Blend to melt it into a "
         "body."],
        None),
    "ellipsoid": (
        "Ellipsoid",
        "A sphere stretched differently along X, Y and Z — heads, "
        "bodies, eggs, pebbles.",
        ["Click to add it.",
         "Set Radius X, Y and Z; Centre X/Y/Z moves it."],
        None),
    "rounded_box": (
        "Rounded box",
        "A box whose edges and corners are rounded — cases, buttons, "
        "soft blocks.",
        ["Click to add it.",
         "Set Width, Depth, Height and the Edge radius (0 = sharp)."],
        None),
    "loft": (
        "Loft (tube through sections)",
        "A smooth tube that passes through a list of cross-sections — "
        "tails, necks, horns, bent handles, ducts.",
        ["Click to add it.",
         "In Properties, each Sections row is one ring: its centre X, "
         "Y, Z and its two radii. Add rows to lengthen it.",
         "Smoothing rounds the path; Ends picks round or flat caps."],
        None),

    # -------------------------------------------------------- operations
    "linear_extrude": (
        "Linear extrude",
        "Turns a flat 2D shape into a solid by pushing it straight up "
        "(along Z).",
        [_SELECTION + " Pick 2D shapes: rectangle, circle, polygon, "
         "text or line.",
         "Click Linear extrude.",
         "Set Height. Optional: Twist (degrees over the height), Scale "
         "(top size vs bottom, 0 = a point), Center (extrude both ways)."],
        "Only 2D shapes can go inside — a 3D object there turns red."),
    "rotate_extrude": (
        "Rotate extrude (lathe)",
        "Spins a 2D profile round the Z axis like a lathe — cups, "
        "flanges, bottles, wheels.",
        ["Draw HALF the cross-section, to the right of the vertical "
         "axis (X ≥ 0): X becomes the radius, Y the height.",
         "Select it and click Rotate extrude.",
         "Angle below 360 makes a partial revolve (a slice)."],
        "A profile crossing X = 0 turns red — keep it on one side."),
    "sweep": (
        "Sweep along path",
        "Drives a flat 2D profile along a 3D path — pipes, handrails, "
        "cable runs, springs, chain links. Corners are mitred and the "
        "path can be smoothed into a curve.",
        ["Draw the cross-section as 2D shapes (a circle for a pipe, a "
         "rectangle for a rail) around the origin: seen with the path "
         "coming towards you, x is right and y is up.",
         "Select it and click Sweep along path.",
         "In Properties, type the Path points (X, Y, Z) the profile "
         "should follow; Smoothing rounds the corners into a curve.",
         "Wall thickness > 0 makes it hollow (a pipe); Closed loop "
         "joins the end to the start (an O-ring); Twist and Scale act "
         "over the length."],
        "Only 2D shapes go inside. The result is baked into the "
        "program, so a sweep cannot sit inside a loop — put the loop "
        "inside the sweep instead."),
    "translate": (
        "Translate (move)",
        "Moves the selection by X, Y and Z millimetres.",
        [_SELECTION, "Click Translate.", "Type the X/Y/Z offsets."],
        "Primitives already have their own X/Y/Z, and dragging in the "
        "2D view moves too — Translate is for moving a whole group."),
    "rotate": (
        "Rotate",
        "Turns the selection about X, then Y, then Z (degrees), around "
        "the origin (0, 0, 0).",
        [_SELECTION, "Click Rotate.", "Type the angles."],
        "It turns around the origin, so a part already moved away "
        "swings round: rotate first, then move."),
    "scale": (
        "Scale",
        "Multiplies the selection's size along X, Y and Z (1 = "
        "unchanged, 2 = double, 0.5 = half).",
        [_SELECTION, "Click Scale.", "Type the factors."],
        None),
    "mirror": (
        "Mirror",
        "Reflects the selection across a plane. (1, 0, 0) swaps left "
        "and right, (0, 1, 0) front and back, (0, 0, 1) up and down.",
        [_SELECTION, "Click Mirror.", "Set the plane's normal X/Y/Z."],
        "The original is not kept — use Symmetry to keep both halves."),
    "symmetry": (
        "Symmetry (mirror copy)",
        "Keeps its contents AND their mirror image: model one arm, one "
        "ear or one wing and the other half appears — and follows every "
        "edit.",
        [_SELECTION, "Click Symmetry.",
         "Set the mirror plane: its normal (1, 0, 0 = left/right) and "
         "a point on it."],
        None),
    "joint": (
        "Joint (pivot)",
        "Rotates its contents about a pivot point, like an elbow or a "
        "hinge. Joints nest, so a tree of them is a poseable skeleton.",
        [_SELECTION + " (e.g. a forearm and hand).",
         "Click Joint.",
         "Put the Pivot on the hinge point, then set the Bend X/Y/Z "
         "angles. Min/Max angle limit how far it may bend."],
        None),
    "blend": (
        "Smooth blend",
        "Melts shapes together like clay: where they meet, the seam "
        "becomes a smooth fillet instead of a sharp crease.",
        [_SELECTION + " Use spheres, capsules, ellipsoids, boxes, rounded "
         "boxes or cylinders.",
         "Click Smooth blend.",
         "Blend radius sets how far the melting reaches; Detail sets "
         "the mesh resolution (higher = finer, slower)."],
        "A blend cannot sit inside a loop — the loop varies, the "
        "melted mesh cannot."),
    "bend": (
        "Bend",
        "Curves the selection along an arc — bananas, arches, curled "
        "tails.",
        [_SELECTION, "Click Bend.",
         "Length axis = the long direction; Bend toward = which way it "
         "curls; Angle = the total bend.",
         "Max edge: smaller gives a smoother curve."],
        None),
    "twist": (
        "Twist",
        "Wrings the selection around an axis, turning by Angle over its "
        "length — drills, twisted columns, horns.",
        [_SELECTION, "Click Twist.", "Pick the Axis and the Angle."],
        None),
    "taper": (
        "Taper",
        "Shrinks (or grows) the selection towards its far end — "
        "pointed legs, tapered posts, fingers.",
        [_SELECTION, "Click Taper.",
         "Pick the Axis; Scale at the far end: 0.5 = half size, 2 = "
         "double."],
        None),
    "lattice": (
        "Lattice (free-form)",
        "Free-form reshaping: move the 8 corners of the bounding box "
        "and the shape follows smoothly — squash, lean or bulge it.",
        [_SELECTION, "Click Lattice.",
         "In Properties, each row moves one corner by dX, dY, dZ "
         "(row order: X changes fastest, then Y, then Z)."],
        None),
    "subdivide": (
        "Subdivide (smooth)",
        "Smooths a blocky shape by splitting and relaxing every "
        "triangle — boxes turn into pebbles.",
        [_SELECTION, "Click Subdivide.",
         "Levels 1–4: each level makes it smoother (and 4× heavier)."],
        None),
    "union": (
        "Group (union)",
        "Joins the selection into one object, so it moves, colours and "
        "combines as one.",
        [_SELECTION, "Click Group (Ctrl+G).",
         "Nothing selected? An empty group is added — drag objects "
         "into it in the tree."],
        "Ctrl+Shift+G ungroups."),
    "difference": (
        "Difference (cut)",
        "Cuts: keeps the FIRST object and subtracts everything after it "
        "— holes, slots, pockets, engraving.",
        ["Select the body FIRST, then the cutting shapes.",
         "Click Difference.",
         "In the tree the first child is the body; drag to reorder if "
         "the wrong one is being cut."],
        "Holes show cut only with the OpenSCAD engine (F5); the quick "
        "preview shows the body whole."),
    "intersection": (
        "Intersection",
        "Keeps only the volume where ALL the selected objects overlap "
        "— rounded-off corners, lens shapes, trimming.",
        [_SELECTION, "Click Intersection."],
        None),
    "fillet": (
        "Fillet edges (round / chamfer)",
        "Rounds the edges you click — SolidWorks' Fillet. A convex edge "
        "is rounded off, an inside corner is filled in; Chamfer cuts a "
        "flat instead of a curve.",
        [_SELECTION + " Pick the solid (or several).",
         "Click Fillet edges: the 3D view asks for edges.",
         "Click an edge to round it; one click on a cylinder's rim "
         "takes the whole rim, a click on a face rounds every edge "
         "round that face. Esc or right-click when done.",
         "Set the Radius (or the chamfer's setback) in Properties. "
         "Right-click the fillet ▸ Pick edges to add more."],
        "The rounding shows in the exact OpenSCAD render (a moment "
        "after each change, or F5) — the quick preview cannot cut."),
    "hull": (
        "Hull (shrink-wrap)",
        "Wraps the selection in the tightest convex skin — two spheres "
        "become a capsule, four pillars a rounded plate.",
        [_SELECTION, "Click Hull.",
         "Move or resize the pieces inside; the skin follows."],
        None),
    "minkowski": (
        "Minkowski (sweep one shape round another)",
        "Grows the first child by the shape of the second — a box plus "
        "a small sphere is a box with every edge rounded.",
        ["Select the body FIRST, then the shape to sweep round it "
         "(a small sphere for rounding).",
         "Click Minkowski."],
        "To round only chosen edges use Fillet edges instead; this "
        "rounds all of them and is slow on big parts."),
    "for_loop": (
        "For loop (repeat)",
        "Repeats its contents: the variable runs From → To by Step, or "
        "through a list of Values (like 0, 90, 180).",
        ["Select the object(s) to repeat and click For loop — or click "
         "with nothing selected and drag objects into the empty loop.",
         "Set the Variable name (i) and its range.",
         "Use it in any field: X = i * 20, Rotate Z = i * 45."],
        "Loops nest: a loop in a loop makes a grid."),
    "while_loop": (
        "While loop",
        "Repeats while a condition holds: the variable starts at the "
        "Initial value and is updated each time round.",
        ["Select what to repeat (or nothing, for an empty loop) and "
         "click While loop.",
         "Set e.g. Variable x, Initial 1, Condition x &lt; 100, "
         "Update x * 2.",
         "Use the variable in the contents' fields."],
        "Capped at 1000 rounds; written out as a list for OpenSCAD."),
    "if_else": (
        "If / else",
        "Shows its contents only when the condition is true, and the "
        "Else branch otherwise — options and alternating patterns.",
        ["Select the objects (or nothing) and click If / else.",
         "Type a Condition: with_lid, or i % 2 == 0 inside a loop.",
         "Put the alternative inside the Else row."],
        None),

    # -------------------------------------------------------- main bar
    "new": ("New document",
            "Starts an empty document. You are asked first if the "
            "current one has unsaved changes.", [], None),
    "open": ("Open",
             "Opens a KherveCAD document (.kcad). Also imports OpenSCAD "
             "programs (.scad) and meshes (.stl, .obj, .off, .3mf).",
             [], "You can also drag a file onto the window."),
    "save": ("Save",
             "Saves the document as .kcad — every object, colour, "
             "variable and assembly mate. File ▸ Save As picks a new "
             "name; File ▸ Export writes .scad or .stl.", [], None),
    "undo": ("Undo",
             "Takes back the last change — edits, drags and assistant "
             "steps alike. A whole drag is one step.", [], None),
    "redo": ("Redo", "Puts back what Undo took away.", [], None),
    "snap_objects": (
        "Snap objects together",
        "Attaches one part to another face-to-face, like a joint in "
        "Fusion — no need to type coordinates.",
        ["Click the face or edge of the part you want to MOVE (it stays "
         "highlighted in orange).",
         "Click the face on the part it should sit against.",
         "Fine-tune in the pop-up: Offset (gap in mm), Spin, Flip "
         "180°."],
        "Esc cancels. The mate is live: move the base part and the "
        "attached one follows."),
    "grid": ("Grid",
             "Shows or hides the millimetre grid in the 2D view.",
             [], None),
    "grid_snap": ("Snap to grid",
                  "Makes drawn points land on the grid, so sizes come "
                  "out as round numbers.", [], None),
    "grid_size": ("Grid spacing",
                  "The distance between grid lines, and the step that "
                  "Snap rounds to (down to 0.01 mm).", [], None),
    "plane": ("Sketch plane",
              "Which plane the 2D view shows: Top (XY), Front (XZ) or "
              "Side (YZ). New shapes are drawn on it.",
              ["Pick a plane.",
               "3D parts appear as outlines — drag one to move the part "
               "along the two axes shown."], None),
    "fit_sketch": ("Fit sketch",
                   "Zooms the 2D view so everything is in sight.",
                   [], None),
    "render": ("Render with OpenSCAD",
               "Runs the exact OpenSCAD render now — boolean holes "
               "really cut. It also happens by itself a moment after "
               "each change.", [],
               "Needs OpenSCAD (bundled with the installer; otherwise "
               "Edit ▸ Locate OpenSCAD)."),
    "fit_3d": ("Fit 3D view",
               "Frames the whole model in the 3D view. Drag there to "
               "orbit, right-drag or middle-drag to pan, wheel to zoom.",
               [], None),
    "vibe_model": (
        "Vibe Model",
        "Folds away the object tree, Properties, the 2D sketch and the "
        "drawing tools so the 3D model fills the window — for building "
        "by describing the part to an assistant and watching it appear.",
        ["Connect an assistant (AI ▸ Connect to Claude) or open the "
         "ChatBox.",
         "Click Vibe Model (Ctrl+Shift+M).",
         "Describe what you want; the model builds in 3D.",
         "Click again to bring the panels back and edit by hand."],
        "The buttons in the 3D view's corner zoom, pan, turn and focus "
        "without the mouse."),
    "assistant": ("Assistant chat",
                  "Opens the chat box: describe a part and the "
                  "assistant builds it in the tree. Needs your own "
                  "Claude, Mistral or Ollama API key.", [],
                  "No key? AI ▸ Connect to Claude lets Claude Desktop "
                  "or Claude Code build here instead."),
    "pattern": (
        "Pattern (linear / polar / grid)",
        "Repeats its contents as copies — in a row, round an axis, or "
        "on a grid — like Blender's Array or a SolidWorks pattern. A "
        "bolt circle, a row of holes, a spiral stair, a peg board.",
        ["Select what to repeat and click Pattern (or click with nothing "
         "selected and drag objects into the empty pattern).",
         "Choose the Kind: linear (Count copies at Step X/Y/Z), polar "
         "(Count copies turned about the Axis over Angle°) or grid "
         "(Count X/Y/Z at Step X/Y/Z).",
         "Polar: Angle 360 spreads the copies evenly round the circle; "
         "below 360 they span the angle, first at 0°, last at Angle. "
         "Rise per copy lifts each one along the axis — a helix."],
        "Every field takes an expression, so a pattern inside a loop can "
        "read the loop variable. Capped at 1000 copies."),
}

#: the operation families of the main toolbar: key -> (title, blurb)
GROUPS = {
    "extrude": ("Extrude", "turn 2D shapes into solids — straight up, "
                "round an axis, or along a path"),
    "transform": ("Move & transform", "move, turn, resize or mirror"),
    "combine": ("Combine", "group, cut and intersect solids"),
    "finish": ("Finish", "round chosen edges, wrap, offset"),
    "deform": ("Deform & sculpt", "melt, bend, twist and reshape"),
    "character": ("Character", "mirror halves and pose with joints"),
    "logic": ("Repeat & logic", "loops and conditions"),
}


def entry(key):
    """(title, what, steps, tip) for *key*; unknown keys fall back to
    the node type's label so a new tool is never silent."""
    if key in TIPS:
        return TIPS[key]
    from .model import NODE_TYPES
    label = NODE_TYPES.get(key, {}).get("label", key)
    return (label, f"Adds or applies {label}.", [], None)


def summary(key) -> str:
    """One line for the status bar."""
    title, what, _steps, _tip = entry(key)
    return f"{title} — {what}".replace("&lt;", "<")


def rich(key, shortcut: str = "", footer: str = "") -> str:
    """The HTML tooltip for *key*: title (+ shortcut), what it does,
    numbered how-to steps and a tip."""
    title, what, steps, tip = entry(key)
    keys = (f" &nbsp;<span style='color:#8a8a8a'>{shortcut}</span>"
            if shortcut else "")
    parts = [f"<b>{title}</b>{keys}",
             f"<p style='margin:4px 0 0 0'>{what}</p>"]
    if steps:
        items = "".join(f"<li>{s}</li>" for s in steps)
        parts.append("<p style='margin:6px 0 0 0'><b>How to use</b></p>"
                     f"<ol style='margin:2px 0 0 0'>{items}</ol>")
    if tip:
        parts.append(f"<p style='margin:4px 0 0 0; color:#8a8a8a'>"
                     f"<i>Tip:</i> {tip}</p>")
    if footer:
        parts.append(f"<p style='margin:6px 0 0 0; color:#8a8a8a'>"
                     f"{footer}</p>")
    return (f"<table width='{WIDTH}' cellspacing='0' cellpadding='0'>"
            f"<tr><td>{''.join(parts)}</td></tr></table>")


def group_footer(group_key, labels) -> str:
    """The line a group button adds under its current tool's tip."""
    title, blurb = GROUPS.get(group_key, (group_key, ""))
    return (f"<b>{title}</b> group ({blurb}) — the ▾ arrow lists: "
            + ", ".join(labels) + ".")


def apply(target, key, shortcut: str = ""):
    """Give a QAction / QWidget its rich tooltip and status-bar text."""
    target.setToolTip(rich(key, shortcut))
    if hasattr(target, "setStatusTip"):
        target.setStatusTip(summary(key))

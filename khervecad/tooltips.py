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
    "house_builder": (
        "House Builder",
        "Opens the House Builder: draw a house floor by floor on a floor "
        "plan — rooms, doors, windows, furniture, stairs, garden and roof "
        "— then build it into the document as real Objects.",
        ["Add rooms from the Room menu (bedroom, garage, corridor, porch, "
         "garden…) and drag them into place.",
         "Put doors and windows in the walls, then add furniture — "
         "double-click a piece to turn it.",
         "Pick a roof, then click Build house."],
        "Building again updates the same house, and the design is saved "
        "with the document."),
    "city_builder": (
        "City Builder",
        "Opens the City Builder: a 2D plan of a village, town or city — "
        "roads, buildings in many styles (incl. mosque and houses from "
        "around the world), trees, street lights and library pieces "
        "(parks, landmarks, bridges) — optionally on a landscape, then "
        "builds it into the document.",
        ["Generate a village, town or city layout, or draw roads point by "
         "point.",
         "Place buildings, trees and props; drag, press R to turn, Delete "
         "to remove.",
         "Click Build."],
        "Real places come from an assistant's import_map (OpenStreetMap "
        "and LiDAR); the result opens here to edit by hand."),
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
    "human": (
        "Human figure",
        "A realistic body — the MakeHuman base mesh (CC0) with its macro "
        "targets: gender, age, build and proportions as sliders, any "
        "height in mm. Real anatomy under the clothes, where capsules "
        "and lofts never get there.",
        ["Click to add it: a figure standing on the floor, facing -Y, "
         "arms slightly out.",
         "Set Gender, Age, Build and Proportions in Properties; Height "
         "scales the whole figure.",
         "Wrap it in a Sculpt to shape the face, and clothe it with "
         "lofts and shells drawn over it."],
        "Its OpenSCAD is one baked polyhedron, so it exports and prints "
        "like any solid."),
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
    "section_loft": (
        "Loft through sections",
        "Joins a series of 2D shapes — one cross-section each — into one "
        "solid, keeping their corners as sharp edges: car bodies, boat "
        "hulls, bottles with flats, wings.",
        ["Draw each cross-section as a polygon (or rectangle, circle) "
         "in the XY plane, around the same origin.",
         "Select them in order and click Loft through sections.",
         "In Properties, type one height (Z) per section, in the same "
         "order as the shapes in the tree.",
         "Smoothing adds curved in-between sections; the ones you drew "
         "stay exactly where they are."],
        "Give every section the same number of points and they join "
        "point to point, so each corner runs as a crisp edge. Rotate "
        "the loft to make it run along X."),
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
    "hair_cap": (
        "Hair cap",
        "Grows a thick, curly cap over part of the selection — hair on a "
        "head, fur on a back: a skin lifted off the surface by a "
        "thickness plus seeded bumps the size of a curl, closed back "
        "onto it.",
        [_SELECTION + " (the head, a human figure).",
         "Click Hair cap. Set Thickness, Curl height and Curl size; a "
         "different Seed gives different curls.",
         "Keep the face clear: the cap skips faces looking within the "
         "angle of the chosen direction (-y is the front); two corners "
         "in 'Only faces inside' limit it to the skull."],
        "Colour the cap grey, white or brown with a Color above it; a "
        "second cap with a smaller curl over the first reads as a set."),
    "paint": (
        "Paint from photo",
        "Colours every face of the selection from a picture projected "
        "onto an axis plane — skin, eyes and lips from the photo, a "
        "label on a bottle, a livery on a hull. The preview shows it; "
        "a print is one colour per part, as before.",
        [_SELECTION + " (a sculpted head, a generated mesh, a body).",
         "Click Paint from photo, then in Properties pick the picture "
         "and where it sits: plane, lower-left corner and width in mm — "
         "the same numbers as a reference image, so line it up with "
         "one first.",
         "Faces outside the picture keep their own colour."],
        "A front photo projects straight through the part, so the back "
        "gets it mirrored — add a second Paint with a back photo on the "
        "same plane, inside the first, to paint the back properly."),
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
    "sculpt": (
        "Sculpt (brush strokes)",
        "Pushes the surface about with a brush — Blender's sculpt mode: "
        "grab, inflate, smooth, flatten, pinch — for faces, muscles, "
        "dents and every organic shape a primitive cannot give.",
        [_SELECTION + " (a blend, a subdivided cage or an imported scan "
         "works best).",
         "Click Sculpt: the panel opens and the 3D view asks for clicks.",
         "Pick the brush, radius and strength, then click the surface "
         "where the brush lands; Mirror repeats each stroke across the "
         "part's middle so a face stays symmetric.",
         "Strokes are kept in Properties: edit or delete any of them "
         "later, and the mesh recomputes."],
        "Grab with a negative strength pulls the surface in; Inflate "
        "with a small radius is a blob, a large one a cheek."),
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
    "decimate": (
        "Decimate (fewer triangles)",
        "Makes a heavy part light: fewer triangles, the same shape — a "
        "scan, a sculpt, a threaded part or a tree that slows the view "
        "or the export. Flat areas lose triangles first, detail last.",
        [_SELECTION + " Pick the heavy solid.",
         "Click Decimate.",
         "Keep: the fraction of triangles to keep (0.25 = a quarter).",
         "Or within: a distance in mm the surface may move instead — "
         "0.05 is invisible on a print."],
        "A closed solid stays closed, so it still prints."),
    "remesh": (
        "Remesh (clean solid)",
        "Rebuilds a messy part as ONE clean closed solid of even "
        "triangles: overlapping pieces merge, inner walls and small "
        "holes in a scan disappear. Use it when a part will not print, "
        "bevel, shrinkwrap or cut.",
        [_SELECTION + " Pick the messy part.",
         "Click Remesh.",
         "Voxel size: the detail kept (mm) — smaller is finer and "
         "heavier.",
         "Snap keeps the original surface exactly where it was."],
        "Follow it with Decimate if the result is heavier than needed."),
    "bevel": (
        "Bevel edges",
        "Rounds or chamfers EVERY sharp edge of a part at once — outside "
        "edges, inside corners or both — with true rounded corners where "
        "three edges meet. The part keeps its size.",
        [_SELECTION + " Pick the part.",
         "Click Bevel edges.",
         "Width: the radius of the round (mm).",
         "Segments: steps across it (1 = a flat chamfer).",
         "Profile: 0.5 round, 0.25 flat, towards 1 squarer, lower a cove.",
         "Edges sharper than: leave gentle creases (a cylinder's facets) "
         "alone."],
        "To round only some edges, use Fillet edges and click them."),
    "shrinkwrap": (
        "Shrinkwrap (onto a surface)",
        "Presses one shape onto another: a garment, a cap, a strap or "
        "a decal hugs the body under it instead of floating a guessed "
        "distance off it — and follows it after a pose or a sculpt.",
        [_SELECTION + " Select the piece to wrap FIRST, then the "
         "target (Ctrl+click).",
         "Click Shrinkwrap.",
         "Move each vertex: nearest (the closest point of the target) "
         "or project (along its normal, or an axis).",
         "Which vertices move: outside (only those inside the target — "
         "clothes), all (onto the surface) or inside.",
         "Offset: how far off the surface it sits (mm)."],
        "Blocky piece? Set Refine to split it first, so it can bend."),
    "shell": (
        "Shell (hollow)",
        "Turns a solid into a hollow shell of even wall thickness — a "
        "cup, a case, a lid, a lighter print. One side can be left "
        "open.",
        [_SELECTION + " Pick the solid to hollow.",
         "Click Shell.",
         "Set the Wall thickness (mm).",
         "Open side: none keeps it closed; top / bottom / ±x / ±y "
         "removes the faces looking that way and joins the rims (a "
         "cup: open = top)."],
        "A wall thicker than half the part's smallest dimension leaves "
        "no room for a cavity; the shell turns red and says so."),
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
    "cut_through": (
        "Cut through",
        "Slices the 3D view with a plane, hides one half and fills the "
        "cut face in red, so you can see how the part is made inside — "
        "holes, walls, bores, threads, how parts sit in each other. Only "
        "the picture is cut: the model, exports and drawings stay whole.",
        ["Click Cut through (Ctrl+Alt+X).",
         "Pick X, Y or Z on the bar along the bottom of the 3D view.",
         "Drag the slider to move the cut through the model.",
         "⇄ keeps the other half; ✕ (or the button again) shows the "
         "whole model."],
        "Orbit while it is cut: the red face is the section, the rest "
        "is the inside of the part."),
    "blueprint": (
        "Blueprint (2D drawing)",
        "Opens the engineering drawing of the model in its own window: "
        "Front, Top, Right and isometric views laid out and dimensioned "
        "by themselves, a title block with the material and mass, and a "
        "toolbar of dimension, note, balloon, datum, tolerance and "
        "detail-view tools to finish it.",
        ["Build the model, then click Blueprint (Ctrl+Shift+D).",
         "Drag views to arrange them; add dimensions with Smart "
         "dimension (D) — click an edge, a hole or two points, then "
         "place.",
         "Double-click the title block to fill in the title, material "
         "and who drew it.",
         "Export PDF, DXF, SVG or PNG, or print."],
        "The sheet is saved in the .kcad; Update from model re-projects "
        "the views after you change the part."),
    "vibe_model": (
        "Vibe Model",
        "Folds away the object tree, Properties, the 2D sketch, the "
        "drawing tools and every toolbar button but file and undo, so "
        "the 3D model fills the window — for building by describing the "
        "part to an assistant and watching it appear.",
        ["Connect an assistant (AI ▸ Connect to Claude).",
         "Click Vibe Model (Ctrl+Shift+M).",
         "Describe what you want; the model builds in 3D.",
         "Click again to bring the panels back and edit by hand."],
        "The buttons in the 3D view's corner zoom, pan, turn and focus "
        "without the mouse."),
    "resize": (
        "Resize (absolute size)",
        "Scales what it holds to a size in millimetres rather than by a "
        "factor — OpenSCAD's resize(). Make a part exactly 40 mm long "
        "without working out the scale.",
        ["Select the objects and click Resize.",
         "Type the new size along X, Y and/or Z; 0 keeps that axis.",
         "Tick Auto on an axis left at 0 to scale it with the others, "
         "keeping the proportions."],
        "OpenSCAD scales about the origin, like scale(): centre the part "
        "first if it should grow evenly."),
    "multmatrix": (
        "Matrix transform (multmatrix)",
        "Applies a 4 x 4 affine matrix — the general transform that "
        "translate, rotate, scale, mirror and shear are all cases of. "
        "Every .csg file OpenSCAD writes places its shapes this way.",
        ["Select the objects and click Matrix transform.",
         "Edit the rows: the first three columns turn, scale and shear; "
         "the fourth column moves (X, Y, Z).",
         "Leave the last row 0, 0, 0, 1."],
        "Put a number off the diagonal (row 1, column 2) for a shear — "
        "something no other transform can do."),
    "render": (
        "Render (cache as mesh)",
        "OpenSCAD's render(): tells OpenSCAD to compute its contents as "
        "one finished mesh in its own preview. The shape is unchanged; a "
        "complex boolean inside a loop previews faster.",
        ["Select the objects and click Render.",
         "Raise Convexity if OpenSCAD's preview shows see-through "
         "faces (the most walls a ray can cross, halved)."],
        "KherveCAD's own preview ignores it; it is kept so the program "
        "reads the same in OpenSCAD."),
    "intersection_for": (
        "Intersection for",
        "A for loop whose copies are INTERSECTED instead of joined: only "
        "the volume every iteration shares remains. Three boxes turned "
        "60° apart intersect into a hexagonal prism.",
        ["Select what to repeat and click Intersection for (or click "
         "with nothing selected and drag objects in).",
         "Set the Variable and its range (From, To, Step) or a list of "
         "Values.",
         "Use the variable in the contents, e.g. a Rotate Z of i."],
        "The built-in preview draws the first iteration; the OpenSCAD "
        "render shows the true intersection."),
    "let": (
        "Let (local variables)",
        "Names values for what it holds only — OpenSCAD's let(). Work a "
        "radius out once from a diameter and use it in every child.",
        ["Select the objects and click Let (or insert an empty one and "
         "drag objects in).",
         "Write the bindings: r = d / 2, h = r * 3 — later ones may use "
         "earlier ones.",
         "Type the names into the children's fields (Radius: r)."],
        "The names exist only inside the Let; a Variable at the top "
        "level is seen everywhere."),
    "echo": (
        "Echo (print)",
        "OpenSCAD's echo(): prints values to OpenSCAD's console when the "
        "program runs — to check a computed size or a loop count.",
        ["Insert ▸ Code & files ▸ Echo.",
         "Write the arguments as in OpenSCAD: \"width = \", w, "
         "area = w * h."],
        "A named argument prints as name = value."),
    "assert": (
        "Assert (check)",
        "OpenSCAD's assert(): stops the program with a message when a "
        "condition is false. In KherveCAD the node turns red at once, "
        "with the message, so a parameter out of range is caught while "
        "editing.",
        ["Insert ▸ Code & files ▸ Assert.",
         "Write the Condition (wall >= 1.2) and a Message — an "
         "expression, so str(\"wall \", wall, \" is too thin\") works."],
        "Put asserts next to the Variables they guard."),
    "gear": (
        "Gear (involute)",
        "A true involute gear by module, tooth count and pressure angle — "
        "spur, helical, herringbone, internal (ring), rack, bevel or worm "
        "— with bore, backlash and root clearance. Two gears of the same "
        "module and pressure angle mesh at a centre distance of m (z1 + "
        "z2) / 2.",
        ["Insert ▸ Mechanical features ▸ Gear.",
         "Choose the Kind, then the Module (tooth size) and Teeth.",
         "Set Thickness, a Bore, and for a helical or herringbone gear "
         "the Helix angle; a bevel gear needs its mate's tooth count.",
         "Print-in-place pairs want 0.1–0.2 mm of Backlash."],
        "Every field takes an expression, so teeth = ratio * 10 keeps a "
        "pair in step; the code is kcad_gear(...), real OpenSCAD."),
    "thread": (
        "Thread (screw thread)",
        "A real helical screw thread — ISO metric, trapezoidal, square, "
        "buttress, tapered pipe or bottle neck — male, or as the slightly "
        "larger tap you subtract to make a nut or a threaded hole. Any "
        "number of starts, right or left hand.",
        ["Insert ▸ Mechanical features ▸ Thread.",
         "Set the Profile, Major diameter, Pitch and Length (M8: 8 mm, "
         "1.25).",
         "For a nut or a threaded hole tick Internal and put the thread "
         "inside a Difference with the part; 0.2 mm Clearance prints "
         "well."],
        "A thread is a twisted cross-section, so it previews exactly and "
        "renders fast — no boolean inside."),
    "hole": (
        "Hole (counterbore, countersink, nut trap…)",
        "The solid to cut for a fastener: plain, counterbore, countersink, "
        "nut trap, heat-set insert, slot, or a teardrop that prints "
        "horizontally without support. Its top sits at z = 0 and it goes "
        "down, so it drops onto a face.",
        ["Insert ▸ Mechanical features ▸ Hole.",
         "Pick the Kind and the sizes (M3: 3.2 mm hole, 6 mm head).",
         "Move it onto the face, then select it with the part and click "
         "Difference."],
        "Extends above the face keeps the cut clean on a flush face; the "
        "teardrop runs along X with its point up."),
    "knurl": (
        "Knurled cylinder",
        "A cylinder covered in diamond knurling — two sets of helical "
        "grooves crossing — for a knob or a thumb screw you can grip.",
        ["Insert ▸ Mechanical features ▸ Knurled cylinder.",
         "Set the Outer diameter and Length, how many Diamonds round and "
         "the Groove depth (0.6–1 mm prints well)."],
        "Put it in a Group with the knob's other shapes; the helix angle "
        "sets how tall the diamonds are."),
    "polyhedron_solid": (
        "Regular polyhedron",
        "A Platonic or Archimedean solid — tetrahedron to icosahedron, "
        "cuboctahedron, the football (truncated icosahedron) and more — "
        "sized by the sphere through its corners.",
        ["Insert ▸ Shapes & patterns ▸ Regular polyhedron.",
         "Pick the Solid and its Circumradius."],
        "Dice, lamp shades, a geodesic starting point."),
    "star": (
        "Regular polygon / star",
        "A 2D regular polygon, or a star of that many tips between an "
        "outer and an inner radius.",
        ["Insert ▸ Shapes & patterns ▸ Regular polygon / star.",
         "Set Sides / tips and the Outer radius; an Inner radius of 0 "
         "gives the plain polygon.",
         "Extrude it for a solid."],
        "Turn° sets where the first tip points (90 = up)."),
    "rounded_polygon": (
        "Rounded polygon (radius per corner)",
        "A 2D outline whose every corner has its own fillet radius — a "
        "bracket profile with a big inside radius and small outside ones, "
        "in one shape (Round-Anything's polyRound).",
        ["Insert ▸ Shapes & patterns ▸ Rounded polygon.",
         "Edit the Corners table: X, Y and the Radius of each corner (0 "
         "keeps it sharp).",
         "Extrude it."],
        "A radius too big for a short edge is shrunk to fit."),
    "bezier_shape": (
        "Bézier shape (closed)",
        "A smooth 2D outline of cubic Bézier curves — a logo, a cam, a "
        "guitar body.",
        ["Insert ▸ Shapes & patterns ▸ Bézier shape.",
         "Rows come in threes: a point on the curve, then two control "
         "points pulling the curve toward the next point.",
         "Extrude it."],
        "The last curve closes back to the first point."),
    "honeycomb": (
        "Honeycomb panel (2D)",
        "A rectangle perforated with hexagonal cells — extrude it for a "
        "light, stiff, printable panel or grille.",
        ["Insert ▸ Shapes & patterns ▸ Honeycomb panel.",
         "Set the Width, Height, Cell size, Wall between cells and the "
         "solid Margin.",
         "Extrude it."],
        "Only whole cells are cut, so the edge stays solid."),
    "textured": (
        "Textured cylinder / panel",
        "A cylinder or a flat panel with a relief pattern on its surface — "
        "ribs, waves, diamonds, bricks, hexagons, dimples or checkers — "
        "for grips, lids, lithophane-like panels and decoration.",
        ["Insert ▸ Mechanical features ▸ Textured cylinder / panel.",
         "Choose the Shape and the Pattern, then its size (Pattern size) "
         "and how deep it goes (Relief depth).",
         "Raise Samples per pattern for a smoother relief."],
        "Round a cylinder the pattern size is adjusted so it closes "
        "without a seam."),
    "svg_path": (
        "SVG path shape",
        "A 2D shape typed as an SVG path — M, L, H, V, C, S, Q, T, A and Z, "
        "absolute or relative — so curves and arcs are one line of text. "
        "A subpath inside another is a hole.",
        ["Insert ▸ Shapes & patterns ▸ SVG path shape.",
         "Type the path: M 0 0 L 40 0 A 10 10 0 0 1 40 20 L 0 20 Z.",
         "Extrude it."],
        "y runs up, as everywhere in KherveCAD (not down as in an SVG "
        "file)."),
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

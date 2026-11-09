# The ribbon, tool by tool

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


## Features tab


### Features ▸ Create


**Cube**  
Adds a box — the most common starting block.

1. Click. In the Main tab it becomes a new Object and the Object tab opens on it; in the Object tab it is added to the part you are editing.
2. Set Width (X), Depth (Y) and Height (Z) in Properties.
3. X/Y/Z move it; Center puts its middle on that point instead of its corner.

**Sphere**  
Adds a ball — eyes, knobs, joints, domes.

1. Click to add it at the origin (see Cube for where it lands).
2. Set the Radius; X/Y/Z move its centre.
3. Segments sets smoothness (more = rounder, slower).

**Cylinder**  
Adds a cylinder — shafts, legs, pins, holes. A different top radius makes a cone (0 comes to a point).

1. Click to add it (see Cube for where it lands).
2. Set Height and the bottom and top radius.
3. Center stands it on its middle instead of its base.

*Tip:* Inside a Difference, a cylinder drills a hole.

**Capsule**  
A rod with rounded ends between two points — arms, legs, fingers, handles.

1. Click to add it.
2. Set the Start and End points and the Radius.
3. Wrap it in a Joint to pose it, or a Blend to melt it into a body.

**Ellipsoid**  
A sphere stretched differently along X, Y and Z — heads, bodies, eggs, pebbles.

1. Click to add it.
2. Set Radius X, Y and Z; Centre X/Y/Z moves it.

**Rounded box**  
A box whose edges and corners are rounded — cases, buttons, soft blocks.

1. Click to add it.
2. Set Width, Depth, Height and the Edge radius (0 = sharp).

**Loft (tube through sections)**  
A smooth tube that passes through a list of cross-sections — tails, necks, horns, bent handles, ducts.

1. Click to add it.
2. In Properties, each Sections row is one ring: its centre X, Y, Z and its two radii. Add rows to lengthen it.
3. Smoothing rounds the path; Ends picks round or flat caps.

**3D Sketch Curve**  
A smooth (or straight) line through points in space, drawn as a round wire — a cable, a handrail, a bent rod, a coil, the rail for a sweep. Exported to STEP as an exact B-spline pipe.

1. Insert ▸ Shapes & patterns ▸ 3D curve.
2. Edit the Points table: one row per point it passes through (X, Y, Z). Add rows to add bends.
3. Pick Smooth or Straight, tick Closed loop for a ring, and set the Wire thickness.
4. Right-click ▸ Make a Sweep Along This Curve to give it any profile.

*Tip:* Thin it right down and hide it to keep it as a guide.

**Regular polyhedron**  
A Platonic or Archimedean solid — tetrahedron to icosahedron, cuboctahedron, the football (truncated icosahedron) and more — sized by the sphere through its corners.

1. Insert ▸ Shapes & patterns ▸ Regular polyhedron.
2. Pick the Solid and its Circumradius.

*Tip:* Dice, lamp shades, a geodesic starting point.

### Features ▸ Extrude


**Extruded Boss/Base**  
Turns a flat sketch shape into a solid by pushing it straight out of its plane — the usual way a part begins, and how a boss is added to one.

1. Draw the shape in a sketch (Sketch Mode, then a plane or a flat face) — or select 2D shapes you already have: rectangle, circle, polygon, text, lines that close an area.
2. Click Extrude. One closed shape is extruded at once; overlapping shapes show their regions in the 3D view — click the ones to keep, then Done or right-click. With no sketch left to extrude it asks for a face to sketch a boss on.
3. Its window opens beside a blue arrow in the 3D view: drag the arrow or type the Distance; Direction is One side, Two sides or Symmetric; End condition is Blind or Through all; Reverse direction turns it round.
4. OK or Enter keeps it; Cancel or Esc takes it back. Later, select the extrude: the arrow returns and Properties holds the same settings, with Twist and Scale (top) to shape it.

*Tip:* Only 2D shapes can go inside — a 3D object there turns red.

**Revolved Boss/Base**  
Spins a 2D profile round the Z axis like a lathe — cups, flanges, bottles, wheels.

1. Draw HALF the cross-section, to the right of the vertical axis (X ≥ 0): X becomes the radius, Y the height.
2. Select it and click Rotate extrude.
3. Angle below 360 makes a partial revolve (a slice).

*Tip:* A profile crossing X = 0 turns red — keep it on one side.

**Swept Boss/Base**  
Drives a flat 2D profile along a 3D path — pipes, handrails, cable runs, springs, chain links. Corners are mitred and the path can be smoothed into a curve.

1. Draw the cross-section as 2D shapes (a circle for a pipe, a rectangle for a rail) around the origin: seen with the path coming towards you, x is right and y is up.
2. Select it and click Sweep along path.
3. In Properties, type the Path points (X, Y, Z) the profile should follow; Smoothing rounds the corners into a curve.
4. Wall thickness > 0 makes it hollow (a pipe); Closed loop joins the end to the start (an O-ring); Twist and Scale act over the length.

*Tip:* Only 2D shapes go inside. The result is baked into the program, so a sweep cannot sit inside a loop — put the loop inside the sweep instead.

**Lofted Boss/Base**  
Joins a series of 2D shapes — one cross-section each — into one solid, keeping their corners as sharp edges: car bodies, boat hulls, bottles with flats, wings.

1. Draw each cross-section as a polygon (or rectangle, circle) in the XY plane, around the same origin.
2. Select them in order and click Loft through sections.
3. In Properties, type one height (Z) per section, in the same order as the shapes in the tree.
4. Smoothing adds curved in-between sections; the ones you drew stay exactly where they are.

*Tip:* Give every section the same number of points and they join point to point, so each corner runs as a crisp edge. Rotate the loft to make it run along X.

**Drag extrude**  
Extrude a 2D shape by dragging, as in SolidWorks and Fusion: click the shape in the 3D view, then drag its blue Z arrow up or down. A Rotate extrude gets a curved arrow for its angle.

1. Click this, then click a rectangle, polygon or circle in the 3D view (or select one first).
2. Drag the arrow up or down — Ctrl snaps to the grid.
3. Select something else when done (Esc takes a new one back).

*Tip:* Linear extrude and Rotate extrude show the arrow by themselves.

### Features ▸ Cut


**Extruded Cut**  
Cuts a shape sketched on a face straight into the part, as SolidWorks' Extruded Cut: pick the face, draw, set the depth.

1. Click Extruded Cut, then the flat face to cut into (it lights up under the mouse): the view turns to face it and the Sketch tab opens.
2. Draw the shape on the face — the Rectangle is ready (click two corners); Circle, Slot and Line are on the Sketch tab. Points snap to the face's corners, middles and edges.
3. A rectangle, circle or slot is cut as soon as it is drawn; lines once they close an area, alone or with the face's edges (the green button, or right-click).
4. The view turns back and the Extruded Cut window opens: drag the blue arrow or type the Distance, choose Through all under End condition, tick Reverse direction to go the other way.
5. Smart Dimension still works now, to place and size the shape. OK or Enter keeps the cut; Cancel or Esc takes it away.

*Tip:* With sketch shapes already selected, Extruded Cut cuts them at once. While drawing a Line, bring the mouse back onto the last point and out again (or press A) for a tangent arc.

**Hole Wizard**  
SolidWorks' Hole Wizard: choose the hole — type (clearance, tapped, counterbore, countersink, nut trap), standard size (ISO M1-M64, ANSI #0-1" UNC / UNF), fit and end condition — then click the faces of a part: every click drills one hole square to that face. The holes are one feature in the tree.

1. Click Hole Wizard (Features tab).
2. Choose type, size, fit and Through all / Blind in the panel.
3. Click a face of a part — one hole per click, as many as you like.
4. Esc or Done finishes. Select the feature later and press Update to re-size all its holes.

*Tip:* The holes stay ordinary nodes, so the OpenSCAD program cuts them.

**Revolved Cut**  
Cuts a shape sketched on a face into the part (SolidWorks' Revolved Cut): the profile is turned about the sketch's own Y axis — draw it to the right of that axis.

1. Click the button, then the flat face to cut into: the view turns to face it and the Sketch tab opens.
2. Draw the shape on the face — the Rectangle is ready; Circle, Slot and Line are on the Sketch tab. Points snap to the face's corners, middles and edges.
3. A rectangle, circle or slot is cut as soon as it is drawn; lines once they close an area (the green button, or right-click).
4. Set its numbers in Properties; Smart Dimension places and sizes the sketch.

*Tip:* Or select a face sketch you already drew and click it.

**Swept Cut**  
Cuts a shape sketched on a face into the part (SolidWorks' Swept Cut): the profile is swept along a path you then set in Properties.

1. Click the button, then the flat face to cut into: the view turns to face it and the Sketch tab opens.
2. Draw the shape on the face — the Rectangle is ready; Circle, Slot and Line are on the Sketch tab. Points snap to the face's corners, middles and edges.
3. A rectangle, circle or slot is cut as soon as it is drawn; lines once they close an area (the green button, or right-click).
4. Set its numbers in Properties; Smart Dimension places and sizes the sketch.

*Tip:* Or select a face sketch you already drew and click it.

**Lofted Cut**  
Cuts a shape sketched on a face into the part (SolidWorks' Lofted Cut): the cut runs through the sketch's shapes as sections, one height each (Properties).

1. Click the button, then the flat face to cut into: the view turns to face it and the Sketch tab opens.
2. Draw the shape on the face — the Rectangle is ready; Circle, Slot and Line are on the Sketch tab. Points snap to the face's corners, middles and edges.
3. A rectangle, circle or slot is cut as soon as it is drawn; lines once they close an area (the green button, or right-click).
4. Set its numbers in Properties; Smart Dimension places and sizes the sketch.

*Tip:* Or select a face sketch you already drew and click it.

**Boundary Cut**  
Cuts a shape sketched on a face into the part (SolidWorks' Boundary Cut): the cut runs through the sketch's shapes as sections, one height each (Properties).

1. Click the button, then the flat face to cut into: the view turns to face it and the Sketch tab opens.
2. Draw the shape on the face — the Rectangle is ready; Circle, Slot and Line are on the Sketch tab. Points snap to the face's corners, middles and edges.
3. A rectangle, circle or slot is cut as soon as it is drawn; lines once they close an area (the green button, or right-click).
4. Set its numbers in Properties; Smart Dimension places and sizes the sketch.

*Tip:* Or select a face sketch you already drew and click it.

### Features ▸ Features


**Hole**  
The solid to cut for a fastener: plain, counterbore, countersink, nut trap, heat-set insert, slot, or a teardrop that prints horizontally without support. Its top sits at z = 0 and it goes down, so it drops onto a face.

1. Insert ▸ Mechanical features ▸ Hole.
2. Pick the Kind and the sizes (M3: 3.2 mm hole, 6 mm head).
3. Move it onto the face, then select it with the part and click Difference.

*Tip:* Extends above the face keeps the cut clean on a flush face; the teardrop runs along X with its point up.

**Thread**  
A real helical screw thread — ISO metric, trapezoidal, square, buttress, tapered pipe or bottle neck — male, or as the slightly larger tap you subtract to make a nut or a threaded hole. Any number of starts, right or left hand.

1. Insert ▸ Mechanical features ▸ Thread.
2. Set the Profile, Major diameter, Pitch and Length (M8: 8 mm, 1.25).
3. For a nut or a threaded hole tick Internal and put the thread inside a Difference with the part; 0.2 mm Clearance prints well.

*Tip:* A thread is a twisted cross-section, so it previews exactly and renders fast — no boolean inside.

**Gear (involute)**  
A true involute gear by module, tooth count and pressure angle — spur, helical, herringbone, internal (ring), rack, bevel or worm — with bore, backlash and root clearance. Two gears of the same module and pressure angle mesh at a centre distance of m (z1 + z2) / 2.

1. Insert ▸ Mechanical features ▸ Gear.
2. Choose the Kind, then the Module (tooth size) and Teeth.
3. Set Thickness, a Bore, and for a helical or herringbone gear the Helix angle; a bevel gear needs its mate's tooth count.
4. Print-in-place pairs want 0.1–0.2 mm of Backlash.

*Tip:* Every field takes an expression, so teeth = ratio * 10 keeps a pair in step; the code is kcad_gear(...), real OpenSCAD.

**Knurled cylinder**  
A cylinder covered in diamond knurling — two sets of helical grooves crossing — for a knob or a thumb screw you can grip.

1. Insert ▸ Mechanical features ▸ Knurled cylinder.
2. Set the Outer diameter and Length, how many Diamonds round and the Groove depth (0.6–1 mm prints well).

*Tip:* Put it in a Group with the knob's other shapes; the helix angle sets how tall the diamonds are.

**Textured cylinder / panel**  
A cylinder or a flat panel with a relief pattern on its surface — ribs, waves, diamonds, bricks, hexagons, dimples or checkers — for grips, lids, lithophane-like panels and decoration.

1. Insert ▸ Mechanical features ▸ Textured cylinder / panel.
2. Choose the Shape and the Pattern, then its size (Pattern size) and how deep it goes (Relief depth).
3. Raise Samples per pattern for a smoother relief.

*Tip:* Round a cylinder the pattern size is adjusted so it closes without a seam.

**Base Flange/Tab**  
A plate with one flange on each of its four edges, set by numbers — the quick way to a tray or a bracket. The Sheet Metal tab makes anything more.

1. Click it: a plate with flanges appears as a new part.
2. In Properties set the plate size, Thickness, Bend radius and each edge's flange length and angle (0 = no flange, negative = bent down).
3. Right-click it in the tree ▸ Unfold for the flat blank, or Export flat pattern DXF.

*Tip:* Convert to Sheet Metal (Sheet Metal tab) turns it into a full sheet metal body.

### Features ▸ Move & transform


**Move/Copy Bodies**  
Moves the selection by X, Y and Z millimetres.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Translate.
3. Type the X/Y/Z offsets.

*Tip:* Primitives already have their own X/Y/Z, and dragging in the 2D view moves too — Translate is for moving a whole group.

**Rotate Bodies**  
Turns the selection about X, then Y, then Z (degrees), around the origin (0, 0, 0).

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Rotate.
3. Type the angles.

*Tip:* It turns around the origin, so a part already moved away swings round: rotate first, then move.

**Scale**  
Multiplies the selection's size along X, Y and Z (1 = unchanged, 2 = double, 0.5 = half).

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Scale.
3. Type the factors.

**Mirror**  
Reflects the selection across a plane. (1, 0, 0) swaps left and right, (0, 1, 0) front and back, (0, 0, 1) up and down.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Mirror.
3. Set the plane's normal X/Y/Z.

*Tip:* The original is not kept — use Symmetry to keep both halves.

**Resize (absolute size)**  
Scales what it holds to a size in millimetres rather than by a factor — OpenSCAD's resize(). Make a part exactly 40 mm long without working out the scale.

1. Select the objects and click Resize.
2. Type the new size along X, Y and/or Z; 0 keeps that axis.
3. Tick Auto on an axis left at 0 to scale it with the others, keeping the proportions.

*Tip:* OpenSCAD scales about the origin, like scale(): centre the part first if it should grow evenly.

**Matrix transform (multmatrix)**  
Applies a 4 x 4 affine matrix — the general transform that translate, rotate, scale, mirror and shear are all cases of. Every .csg file OpenSCAD writes places its shapes this way.

1. Select the objects and click Matrix transform.
2. Edit the rows: the first three columns turn, scale and shear; the fourth column moves (X, Y, Z).
3. Leave the last row 0, 0, 0, 1.

*Tip:* Put a number off the diagonal (row 1, column 2) for a shear — something no other transform can do.

**Gumball (move / turn handles)**  
Arrows and rings on the selected part, to move and turn it by hand in the 3D view.

1. Select a part, then switch the Gumball on.
2. Drag an arrow to move along that axis, a ring to turn about it. Hold Ctrl to snap to the grid and to 15°.
3. Esc while dragging puts the part back. Drag anywhere else to orbit as usual.
4. Switch it off with the same button.

*Tip:* Exact values go in Properties (Position / Rotation).

**Snap objects**  
Attaches one part to another face-to-face, like a joint in Fusion — no need to type coordinates.

1. Click the face or edge of the part you want to MOVE (it stays highlighted in orange).
2. Click the face on the part it should sit against.
3. Fine-tune in the pop-up: Offset (gap in mm), Spin, Flip 180°.

*Tip:* Esc cancels. The mate is live: move the base part and the attached one follows.

### Features ▸ Combine


**Combine: Add**  
Joins the selection into one object, so it moves, colours and combines as one.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Group (Ctrl+G).
3. Nothing selected? An empty group is added — drag objects into it in the tree.

*Tip:* Ctrl+Shift+G ungroups.

**Combine: Subtract**  
Cuts: keeps the FIRST object and subtracts everything after it — holes, slots, pockets, engraving.

1. Select the body FIRST, then the cutting shapes.
2. Click Difference.
3. In the tree the first child is the body; drag to reorder if the wrong one is being cut.

*Tip:* Holes show cut only with the OpenSCAD engine (F5); the quick preview shows the body whole.

**Combine: Common**  
Keeps only the volume where ALL the selected objects overlap — rounded-off corners, lens shapes, trimming.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Intersection.

**Render (cache as mesh)**  
OpenSCAD's render(): tells OpenSCAD to compute its contents as one finished mesh in its own preview. The shape is unchanged; a complex boolean inside a loop previews faster.

1. Select the objects and click Render.
2. Raise Convexity if OpenSCAD's preview shows see-through faces (the most walls a ray can cross, halved).

*Tip:* KherveCAD's own preview ignores it; it is kept so the program reads the same in OpenSCAD.

### Features ▸ Finish


**Fillet**  
Rounds the edges you click — SolidWorks' Fillet. A convex edge is rounded off, an inside corner is filled in; Chamfer cuts a flat instead of a curve.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view. Pick the solid (or several).
2. Click Fillet edges: the 3D view asks for edges.
3. Click an edge to round it; one click on a cylinder's rim takes the whole rim, a click on a face rounds every edge round that face. Esc or right-click when done.
4. Set the Radius (or the chamfer's setback) in Properties. Right-click the fillet ▸ Pick edges to add more.

*Tip:* The rounding shows in the exact OpenSCAD render (a moment after each change, or F5) — the quick preview cannot cut.

**Chamfer**  
Rounds or chamfers EVERY sharp edge of a part at once — outside edges, inside corners or both — with true rounded corners where three edges meet. The part keeps its size.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view. Pick the part.
2. Click Bevel edges.
3. Width: the radius of the round (mm).
4. Segments: steps across it (1 = a flat chamfer).
5. Profile: 0.5 round, 0.25 flat, towards 1 squarer, lower a cove.
6. Edges sharper than: leave gentle creases (a cylinder's facets) alone.

*Tip:* To round only some edges, use Fillet edges and click them.

**Move Face**  
Moves a flat face straight out (a boss, a taller wall) or in (a pocket, a recess), like SketchUp — with an optional inset that leaves a rim around it.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view. Pick the part.
2. Click Push / pull, then click flat faces in the 3D view.
3. Each face comes out 5 mm: set its Distance in Properties (negative cuts in) and its Inset (a rim).
4. Esc when done; right-click ▸ Pick faces to add more.

*Tip:* Faces apply in order: click the top you just raised to raise it again.

**Split**  
Cuts a part with a flat plane: keep the top, the bottom, or both halves pulled apart — to see inside, flatten a base, or split a part for printing.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view. Pick the part.
2. Click Bisect.
3. Set the plane's point and normal (0, 0, 1 is a horizontal cut), and what to keep.

**Hull**  
Wraps the selection in the tightest convex skin — two spheres become a capsule, four pillars a rounded plate.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Hull.
3. Move or resize the pieces inside; the skin follows.

**Minkowski (round edges)**  
Grows the first child by the shape of the second — a box plus a small sphere is a box with every edge rounded.

1. Select the body FIRST, then the shape to sweep round it (a small sphere for rounding).
2. Click Minkowski.

*Tip:* To round only chosen edges use Fillet edges instead; this rounds all of them and is slow on big parts.

**Shell**  
Turns a solid into a hollow shell of even wall thickness — a cup, a case, a lid, a lighter print. One side can be left open.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view. Pick the solid to hollow.
2. Click Shell.
3. Set the Wall thickness (mm).
4. Open side: none keeps it closed; top / bottom / ±x / ±y removes the faces looking that way and joins the rims (a cup: open = top).

*Tip:* A wall thicker than half the part's smallest dimension leaves no room for a cavity; the shell turns red and says so.

### Features ▸ Repeat & logic


**For loop**  
Repeats its contents: the variable runs From → To by Step, or through a list of Values (like 0, 90, 180).

1. Select the object(s) to repeat and click For loop — or click with nothing selected and drag objects into the empty loop.
2. Set the Variable name (i) and its range.
3. Use it in any field: X = i * 20, Rotate Z = i * 45.

*Tip:* Loops nest: a loop in a loop makes a grid.

**While loop**  
Repeats while a condition holds: the variable starts at the Initial value and is updated each time round.

1. Select what to repeat (or nothing, for an empty loop) and click While loop.
2. Set e.g. Variable x, Initial 1, Condition x &lt; 100, Update x * 2.
3. Use the variable in the contents' fields.

*Tip:* Capped at 1000 rounds; written out as a list for OpenSCAD.

**If / else**  
Shows its contents only when the condition is true, and the Else branch otherwise — options and alternating patterns.

1. Select the objects (or nothing) and click If / else.
2. Type a Condition: with_lid, or i % 2 == 0 inside a loop.
3. Put the alternative inside the Else row.

**Linear / Circular Pattern**  
Repeats its contents as copies — in a row, round an axis, or on a grid — like Blender's Array or a SolidWorks pattern. A bolt circle, a row of holes, a spiral stair, a peg board.

1. Select what to repeat and click Pattern (or click with nothing selected and drag objects into the empty pattern).
2. Choose the Kind: linear (Count copies at Step X/Y/Z), polar (Count copies turned about the Axis over Angle°) or grid (Count X/Y/Z at Step X/Y/Z).
3. Polar: Angle 360 spreads the copies evenly round the circle; below 360 they span the angle, first at 0°, last at Angle. Rise per copy lifts each one along the axis — a helix.

*Tip:* Every field takes an expression, so a pattern inside a loop can read the loop variable. Capped at 1000 copies.

**Scatter on surface**  
Copies one piece over a surface — spikes down a spine, warts, scales, barnacles, rows of teeth, eye clusters, rivets. Like Blender's particles: each copy stands along the surface normal, sized and turned a little at random.

1. Model the piece at the origin standing up along +Z, base at z = 0 (a cone for a spike).
2. Select the piece, then the body (Ctrl+click), and click Scatter: the first child is the piece, the rest the surface.
3. In Properties: how many copies and how far apart, size and its variation, random spin and lean, sink into the surface, only faces looking one way, or a region.
4. Mode Path puts the copies evenly along points you give — a spine, a jaw line — each dropped onto the surface; Taper makes them smaller towards the ends.

*Tip:* Edit the piece and every copy follows. Sink a little so no gap shows under a copy on a curved body.

**Intersection for**  
A for loop whose copies are INTERSECTED instead of joined: only the volume every iteration shares remains. Three boxes turned 60° apart intersect into a hexagonal prism.

1. Select what to repeat and click Intersection for (or click with nothing selected and drag objects in).
2. Set the Variable and its range (From, To, Step) or a list of Values.
3. Use the variable in the contents, e.g. a Rotate Z of i.

*Tip:* The built-in preview draws the first iteration; the OpenSCAD render shows the true intersection.

**Let (local variables)**  
Names values for what it holds only — OpenSCAD's let(). Work a radius out once from a diameter and use it in every child.

1. Select the objects and click Let (or insert an empty one and drag objects in).
2. Write the bindings: r = d / 2, h = r * 3 — later ones may use earlier ones.
3. Type the names into the children's fields (Radius: r).

*Tip:* The names exist only inside the Let; a Variable at the top level is seen everywhere.

### Features ▸ Reference Geometry


**Plane offset from a face**  
A reference plane parallel to a flat face, a distance off it — to sketch above, inside or beside a part.

1. Click this, then a flat face in 3D.
2. Type the distance.

*Tip:* Right-click the plane in the tree ▸ Sketch on This Plane.

**Plane through three points**  
A plane through three points of the model.

1. Click three faces or edges: an edge gives its nearer corner.

*Tip:* Good for a slanted cut through corners.

**Plane at an angle through an edge**  
A plane through an edge, turned an angle from a face — a chamfer's plane, a rib's slope.

1. Click the edge, then the face it turns from.
2. Type the angle.

*Tip:* 90° stands it square on the face.

**Plane parallel to a main plane**  
A plane parallel to Front, Top or Right, a distance away — the middle of a part, or above it, with nothing to click.

1. Choose the main plane.
2. Type the distance.

*Tip:* A rib in the middle of a part: Front + half its depth.

**Axis of a round face or edge**  
An axis along a round face's centre or an edge.

1. Click a round face (its axis) or an edge.

*Tip:* Use it to revolve or pattern about.

**Axis where two planes meet**  
The line where two reference planes cross.

1. Select two Planes in the tree (Ctrl+click), then click this.

*Tip:* Parallel planes never meet.

**Point**  
A reference point on the model.

1. Click a face (its middle) or an edge (its nearer end).

*Tip:* It stays in the tree and draws nothing.

**Sketch in 3D (rectangle, circle, line)**  
Draw rectangles, circles and lines straight on a plane in the 3D view, without leaving it.

1. Click a plane or a flat face.
2. Rectangle: two corners; Circle: centre then rim; Line: point to point.
3. Drag a corner to change it; Done or Esc ends.

*Tip:* R / C / L switch tools; Alt draws off the grid.

**Extrude up to a face**  
The selected extrude stops exactly at the face you click, and follows it when the part changes.

1. Select the Linear extrude.
2. Click this, then the face.

*Tip:* Direction 2 depth (Properties) extrudes the other way too.

**Measure (click two things)**  
Click a face or an edge to read its size; click a second one to read the distance and angle between them.

1. Click a face or edge.
2. Click another.
3. Esc ends.

*Tip:* Parallel faces also give the face-to-face distance.

**Show main planes in 3D**  
Shows or hides the Front, Top and Right planes in the 3D view.

1. Click to switch.

*Tip:* Also on the 3D view's own bar.

## Sketch tab


### Sketch ▸ Create


**Sketch Mode**  
Sketch in 2D, SolidWorks' way: the 3D view turns to look straight at where you sketch and becomes the sketch. What it sketches on follows what is selected.

1. A 2D shape (or the extrude holding it) selected: edit that sketch.
2. A part selected: click the face of it to sketch on.
3. Nothing selected: the current plane (Top, Front or Side).
4. Click Exit Sketch Mode (same button) to turn back to 3D.

*Tip:* Right-click a shape in the tree ▸ Edit Sketch does the same.

**Smart Dimension**  
Fusion's sketch Dimension (D): sets a size that DRIVES the shapes — type 25 and the line becomes 25 mm.

1. A circle: click it, type the diameter.
2. A line's length: click it, then anywhere empty.
3. Two lines: the angle between them. Two points: their distance. A point and a line: the distance between them.
4. A value may be an expression of the variables (w / 2).

*Tip:* Delete constraint removes a dimension like any constraint.

**Create region**  
Makes a Regions node from overlapping sketch shapes: the regions you click, the shapes inside it with their Smart Dimensions — extrude or revolve it later.

1. Draw overlapping shapes (a rectangle and a circle on it).
2. Click inside each region to keep; they turn blue.
3. Enter or right-click makes the Regions node.

*Tip:* Change a Smart Dimension and the region follows.

**Line**  
Draws a straight bar between two points. It is a real 2D solid (a hull of two circles), so it can be extruded like any shape.

1. Press where the line starts.
2. Drag to the end point — the length shows in the status bar.
3. Release. Set its thickness (Width) in Properties.
4. Use Extrude to turn it into a 3D rod or wall.

*Tip:* Turn Snap on to land the ends on round grid values.

**Corner Rectangle**  
Draws a rectangle on the sketch plane — the usual start of a plate, a box or a bracket.

1. Press at one corner.
2. Drag to the opposite corner; the size reads live in mm.
3. Release, then type exact Width/Height in Properties.
4. Extrude it to give it thickness.

**Circle**  
Draws a circle, or a part of one (a quarter, a semicircle) — rods, discs, holes and arcs.

1. Press at the centre.
2. Drag outwards to the radius (r and Ø show live).
3. Release. In Properties, Angle 180 makes a semicircle, 90 a quarter; Segments sets how smooth it is.

*Tip:* A circle inside a Difference cuts a round hole.

**Polygon (free)**  
Draws any straight-sided outline, one corner at a time — gussets, profiles, custom brackets.

1. Click each corner in turn.
2. Double-click (or press Enter) to close the shape — at least three corners.
3. Esc abandons it.
4. Edit any corner exactly in the points table in Properties.

**Text**  
Places a line of lettering on the sketch — labels, name plates, stamps.

1. Click where the text should start.
2. Type the words and the Size in Properties.
3. Extrude it to make raised or engraved lettering.

*Tip:* Put extruded text in a Difference to engrave it into a part.

**Center Rectangle**  
Draws a rectangle from its centre out — a plate centred on a hole or on the origin.

1. Click (or press) at the centre.
2. Click (or release) at a corner; the rectangle is twice that far each way.
3. Becomes an ordinary rectangle: edit Width/Height in Properties.

**Centerpoint Arc**  
Draws a pie slice of a circle — a sector from a centre, a start and an end, counter-clockwise.

1. Click the centre.
2. Click where the arc starts (sets the radius).
3. Click where it ends.
4. It is a circle with Start angle and Angle in Properties.

**3 Point Arc**  
Draws the area between an arc and its chord through three points — a D-shape, a rounded end, a lens.

1. Click the start.
2. Click the end.
3. Click a point the arc passes through.

*Tip:* Becomes a polygon; edit its points in Properties.

**Ellipse**  
Draws an ellipse from its centre and a corner of its box.

1. Click the centre.
2. Click a corner: the half widths are the distances along X and Y.

*Tip:* It is a circle inside a Scale — change the scale to stretch it.

**Straight Slot**  
Draws a slot (a stadium shape) centre to centre — for adjustable bolt holes and guides.

1. Click the first end's centre.
2. Click the other end's centre.
3. Click to the side to set the width.

*Tip:* It is a Line of that width (the hull of two circles): change its ends or width in Properties.

**Spline**  
Draws a smooth closed curve through the points you click — organic outlines, cams, logos.

1. Click each point the curve passes through.
2. Enter, right-click or double-click finishes (3 points or more).
3. Backspace takes a point back, Esc cancels.

*Tip:* Becomes a polygon of the smoothed curve.

**Centerline**  
A dashed reference line. Relations and dimensions use it — a mirror line, a centre to dimension from, an axis to revolve about — but it is never part of the solid.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click where the centerline starts.
3. Click where it ends. It snaps level, upright and onto points like the Line.
4. Use it: Mirror Entities about it, Symmetric, or Smart Dimension from it.

*Tip:* Any line can be switched to a centerline afterwards with Construction (Modify panel).

**Point**  
A sketch point: a small construction mark to dimension to, to make other shapes Coincident with, or to mark a hole's centre.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click where the point goes — it snaps to ends, middles, centres and the origin.
3. Smart Dimension it from an edge or the origin to place it exactly.

*Tip:* It is construction geometry: an extrude ignores it.

**Polyline**  
Straight lines joined end to end in one go, kept together as one Polyline group with their ends Coincident.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click the first point, then every corner in turn.
3. Backspace takes the last point back.
4. Enter, right-click or double-click ends it; click the first point again to close the outline.

*Tip:* For lines that also turn into arcs on the way, use Line.

**3 Point Corner Rectangle**  
A rectangle at any angle: two clicks give one side, the third its depth.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click one corner.
3. Click the next corner — this first side may lean at any angle.
4. Move away from that side and click to set the depth.

*Tip:* Square to the axes? Corner Rectangle is one click fewer.

**2-point circle**  
A circle from the two ends of its diameter — when you know what it must pass through, not where its centre is.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click one end of the diameter.
3. Click the opposite end: the circle passes through both.

*Tip:* Give it a size afterwards with Smart Dimension (click the circle, then empty space).

**Perimeter Circle**  
A circle through three points on its rim. Clicked on three lines or sides instead, it becomes the circle touching all three and stays Tangent to them.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click a first point on the rim (or a first line).
3. Click a second.
4. Click a third: the circle through the three is drawn.

*Tip:* Three sides of a triangle give its inscribed circle.

**Tangent circle**  
The circle that touches three lines — the round that fits exactly into a corner or a triangle.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click the first line.
3. Click the second line.
4. Click the third: the circle touching all three appears.

*Tip:* The lines may be sides of a polygon or rectangle.

**Tangent arc**  
An arc that carries on smoothly from the end of a line, with no kink where they meet.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click near the END of the line to go on from.
3. Move: the arc follows the cursor, leaving the line in its own direction.
4. Click where the arc ends. Straight across from the end gives a half circle.

*Tip:* While drawing with Line, bring the mouse back onto the last point and out again (or press A) for the same arc without changing tool.

**Polygon**  
A regular polygon — triangle, square, hexagon… — from its centre and one corner.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click the centre.
3. Click where one corner goes: that sets the size and the turn.
4. Type the number of sides when asked (6 = a hexagon).

*Tip:* Polygon (free) draws any outline corner by corner instead.

**Style Spline**  
A smooth curve PULLED towards the points you click without passing through them — gentler than Spline, good for styled outlines.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click the control points in order; the curve starts at the first and ends at the last.
3. Backspace takes a point back.
4. Enter, right-click or double-click ends it.

*Tip:* Spline is the one that goes THROUGH every clicked point.

**Conic**  
One smooth bow between two points — a piece of an ellipse — shaped by where its two end directions would meet.

1. Open a sketch first: Sketch Mode, then click a plane or a flat face.
2. Click where the curve starts.
3. Click where it ends.
4. Click the shoulder: the point both ends aim at. Further out gives a fuller bow.

*Tip:* Handy for a blend between two straight lines that is softer than a round.

### Sketch ▸ Shapes


**Regular polygon / star**  
A 2D regular polygon, or a star of that many tips between an outer and an inner radius.

1. Insert ▸ Shapes & patterns ▸ Regular polygon / star.
2. Set Sides / tips and the Outer radius; an Inner radius of 0 gives the plain polygon.
3. Extrude it for a solid.

*Tip:* Turn° sets where the first tip points (90 = up).

**Rounded polygon (radius per corner)**  
A 2D outline whose every corner has its own fillet radius — a bracket profile with a big inside radius and small outside ones, in one shape (Round-Anything's polyRound).

1. Insert ▸ Shapes & patterns ▸ Rounded polygon.
2. Edit the Corners table: X, Y and the Radius of each corner (0 keeps it sharp).
3. Extrude it.

*Tip:* A radius too big for a short edge is shrunk to fit.

**Bézier shape (closed)**  
A smooth 2D outline of cubic Bézier curves — a logo, a cam, a guitar body.

1. Insert ▸ Shapes & patterns ▸ Bézier shape.
2. Rows come in threes: a point on the curve, then two control points pulling the curve toward the next point.
3. Extrude it.

*Tip:* The last curve closes back to the first point.

**SVG path shape**  
A 2D shape typed as an SVG path — M, L, H, V, C, S, Q, T, A and Z, absolute or relative — so curves and arcs are one line of text. A subpath inside another is a hole.

1. Insert ▸ Shapes & patterns ▸ SVG path shape.
2. Type the path: M 0 0 L 40 0 A 10 10 0 0 1 40 20 L 0 20 Z.
3. Extrude it.

*Tip:* y runs up, as everywhere in KherveCAD (not down as in an SVG file).

**Honeycomb panel (2D)**  
A rectangle perforated with hexagonal cells — extrude it for a light, stiff, printable panel or grille.

1. Insert ▸ Shapes & patterns ▸ Honeycomb panel.
2. Set the Width, Height, Cell size, Wall between cells and the solid Margin.
3. Extrude it.

*Tip:* Only whole cells are cut, so the edge stays solid.

### Sketch ▸ Modify


**Construction**  
Turns the selected sketch shapes into construction geometry and back: drawn dashed, used by constraints and dimensions, never part of the solid (OpenSCAD's % modifier).

1. Select sketch shapes.
2. Click Construction.

**Trim Entities**  
Removes the piece of a line between the lines or circles that cross it.

1. Click the piece to remove.
2. Nothing crosses it: the whole line goes. A middle piece splits the line in two.

**Extend Entities**  
Runs a line on until it meets another line or a circle.

1. Click near the end to extend.

**Sketch fillet**  
Rounds a corner of a polygon or rectangle, or where two lines meet.

1. Click the corner (or one line, then the other).
2. Type the radius.

*Tip:* A rectangle becomes a polygon.

**Sketch chamfer**  
Cuts a corner off at 45° by a distance.

1. Click the corner (or one line, then the other).
2. Type the distance.

**Mirror Entities**  
Mirrors sketch shapes about a line — usually a centerline — as SolidWorks does: the copies are tied to the originals by Symmetric relations, so changing one side changes the other.

1. Click this: a panel opens top-left of the sketch.
2. Box 1, Entities to mirror: click the lines, circles and shapes (already selected ones are filled in).
3. Box 2, Mirror about: click the centerline — or click the box, then any line.
4. OK (or Enter) makes the copies; Cancel or Esc leaves.

*Tip:* A rectangle mirrored about a slanted line becomes a polygon.

**Create region**  
Makes a Regions node from overlapping sketch shapes: the regions you click, the shapes inside it with their Smart Dimensions — extrude or revolve it later.

1. Draw overlapping shapes (a rectangle and a circle on it).
2. Click inside each region to keep; they turn blue.
3. Enter or right-click makes the Regions node.

*Tip:* Change a Smart Dimension and the region follows.

**Offset (round corners)**  
Grows or shrinks the selected 2D shapes by a distance, rounding or keeping the corners — walls round an outline, clearances.

1. Select 2D shapes.
2. Click Offset.
3. Set r (round) or delta (sharp) in Properties; negative shrinks.

**Move/Copy Bodies**  
Moves the selection by X, Y and Z millimetres.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Translate.
3. Type the X/Y/Z offsets.

*Tip:* Primitives already have their own X/Y/Z, and dragging in the 2D view moves too — Translate is for moving a whole group.

**Rotate Bodies**  
Turns the selection about X, then Y, then Z (degrees), around the origin (0, 0, 0).

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Rotate.
3. Type the angles.

*Tip:* It turns around the origin, so a part already moved away swings round: rotate first, then move.

**Scale**  
Multiplies the selection's size along X, Y and Z (1 = unchanged, 2 = double, 0.5 = half).

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Scale.
3. Type the factors.

**Mirror**  
Reflects the selection across a plane. (1, 0, 0) swaps left and right, (0, 1, 0) front and back, (0, 0, 1) up and down.

1. Select the object(s) in the tree (Ctrl-click to add more), or click one in the 2D view.
2. Click Mirror.
3. Set the plane's normal X/Y/Z.

*Tip:* The original is not kept — use Symmetry to keep both halves.

**Linear / Circular Pattern**  
Repeats its contents as copies — in a row, round an axis, or on a grid — like Blender's Array or a SolidWorks pattern. A bolt circle, a row of holes, a spiral stair, a peg board.

1. Select what to repeat and click Pattern (or click with nothing selected and drag objects into the empty pattern).
2. Choose the Kind: linear (Count copies at Step X/Y/Z), polar (Count copies turned about the Axis over Angle°) or grid (Count X/Y/Z at Step X/Y/Z).
3. Polar: Angle 360 spreads the copies evenly round the circle; below 360 they span the angle, first at 0°, last at Angle. Rise per copy lifts each one along the axis — a helix.

*Tip:* Every field takes an expression, so a pattern inside a loop can read the loop variable. Capped at 1000 copies.

### Sketch ▸ Constraints


**Delete constraint**  
Removes one constraint or dimension: click its mark on the sketch (H, V, =, ∥, a value…). The shapes stay where they are.

1. Pick the tool; the mark under the cursor turns red.
2. Click it. Ctrl+Z brings it back.

**Coincident**  
Makes things touch: two points become one (line ends meet, a corner lands on a centre), or a point sits ON a line or circle — whichever is highlighted when you click.

1. Pick the tool, then click: a point, then a point.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Horizontal**  
Makes a line level — or two points level with each other.

1. Pick the tool, then click: a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Vertical**  
Makes a line upright — or two points one above the other.

1. Pick the tool, then click: a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Equal**  
Makes two things the SAME SIZE: two lines (or rectangle / polygon edges) the same length, two circles the same radius. Change one and the other follows.

1. Pick the tool, then click: a curve, then a curve.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Parallel**  
Keeps two lines (or edges) parallel.

1. Pick the tool, then click: a line, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Perpendicular**  
Keeps two lines at a right angle.

1. Pick the tool, then click: a line, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Tangent**  
Makes a line or circle just touch a circle.

1. Pick the tool, then click: a curve, then a circle.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Concentric**  
Puts two circles on one centre.

1. Pick the tool, then click: a circle, then a circle.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Collinear**  
Puts two lines on one straight line.

1. Pick the tool, then click: a line, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Midpoint**  
Puts a point at the middle of a line.

1. Pick the tool, then click: a point, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Symmetric**  
Mirrors two points about a line.

1. Pick the tool, then click: a point, then a point, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Fix**  
Locks a point where it is now.

1. Pick the tool, then click: a point.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Distance**  
Drives the distance between two points.

1. Pick the tool, then click: a point, then a point.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Horizontal distance**  
Drives the horizontal distance between two points.

1. Pick the tool, then click: a point, then a point.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Vertical distance**  
Drives the vertical distance between two points.

1. Pick the tool, then click: a point, then a point.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Length**  
Drives a line's length.

1. Pick the tool, then click: a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Point to line distance**  
Drives the distance from a point to a line.

1. Pick the tool, then click: a point, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Radius**  
Drives a circle's radius.

1. Pick the tool, then click: a circle.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Diameter**  
Drives a circle's diameter.

1. Pick the tool, then click: a circle.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Angle**  
Drives the angle between two lines.

1. Pick the tool, then click: a line, then a line.
2. Points (ends, corners, centres) win over curves under the cursor; right-click or Esc starts again.
3. Type the value — a number or an expression of the variables (w / 2).

*Tip:* Drag a shape afterwards and the rest follows the constraints.

**Fully Define Sketch**  
Adds the constraints the sketch already looks like it has: nearly level / upright lines, line ends that meet.

1. Select a shape of the sketch (or nothing for the whole scope).
2. Click Auto constrain.

*Tip:* The status bar says how many degrees of freedom are left.

**Display/Delete Relations**  
Lists the sketch's constraints and dimensions, says whether it is fully constrained, and edits or deletes them.

1. Select a shape of the sketch.
2. Click Constraints…

### Sketch ▸ Insert


**Import 2D drawing**  
Reads an SVG or DXF outline into the document.

1. Click and pick the file.

## Surfaces tab


### Surfaces ▸ Curves


**3D Sketch**  
Click points in the 3D view to draw a smooth curve through them. Points SNAP to corners, the middle of edges, edges and surfaces — the marker says which — or land on the ground grid in empty space.

1. Insert ▸ Draw 3D Curve, or Ctrl+Alt+C.
2. Click each point. Hold Shift to go straight up or down from the last point; hold Alt to switch snapping off.
3. Or just type a point — 10, 20, 5 — or @0, 0, 15 for 15 above the last one, then Enter.
4. Enter, right-click or double-click finishes; Backspace takes a point back; C (or clicking the first point) closes a loop.

*Tip:* Dragging still turns the view, so you can look round between clicks.

**3D Sketch Curve**  
A smooth (or straight) line through points in space, drawn as a round wire — a cable, a handrail, a bent rod, a coil, the rail for a sweep. Exported to STEP as an exact B-spline pipe.

1. Insert ▸ Shapes & patterns ▸ 3D curve.
2. Edit the Points table: one row per point it passes through (X, Y, Z). Add rows to add bends.
3. Pick Smooth or Straight, tick Closed loop for a ring, and set the Wire thickness.
4. Right-click ▸ Make a Sweep Along This Curve to give it any profile.

*Tip:* Thin it right down and hide it to keep it as a guide.

### Surfaces ▸ From curves


**Loft — a skin through the curves, in order**  
A skin stretched through two or more 3D curves, in the order you selected them — a hull, a duct, a blade.

1. Draw the curves with 3D Sketch (Curves panel), one per section.
2. Select them in the tree in order: click the first, Ctrl+click the next ones.
3. Click Loft. The skin is made with a wall thickness, so it is a real solid.
4. In Properties change the Wall thickness, tick Ruled for straight sides, or Capped to close a loft of closed curves into a solid.

*Tip:* The curves stay inside the surface: edit a curve's points and the surface follows.

**Sweep — first curve is the rail, the rest are profiles**  
Drives a profile curve along a rail curve — a pipe, a moulding, a handle.

1. Draw the rail (the path) and the profile with 3D Sketch.
2. Select the RAIL first, then Ctrl+click the profile.
3. Click Sweep.
4. Set the Wall thickness in Properties; a closed profile sweeps a solid bar.

*Tip:* For a round pipe, Swept Boss/Base on the Features tab needs only the path and a circle.

**Sweep along two rails — first two curves are rails**  
Like Sweep, but the profile is stretched between TWO rails as it travels, so the surface widens and narrows with them.

1. Draw the two rails and one profile that reaches from one rail to the other.
2. Select rail 1, Ctrl+click rail 2, then Ctrl+click the profile.
3. Click Sweep along two rails.
4. Adjust the Wall thickness in Properties.

*Tip:* Start both rails at the profile's two ends.

**Patch — fill inside the first (closed) curve**  
Fills the inside of a closed curve with a smooth surface — a lid, a filled hole, a panel between edges.

1. Draw one CLOSED 3D curve (press C to close it while drawing); it need not be flat.
2. Select it. Ctrl+click other curves the surface must pass through, if any.
3. Click Patch.
4. Set the Wall thickness in Properties.

*Tip:* An open curve cannot be patched — close it first.

**Revolve — turn the curve about the Z axis**  
Turns a curve about the Z axis: a bowl, a vase, a bell.

1. Draw the curve as the profile seen from the side, away from the Z axis (it must not cross it).
2. Select it and click Revolve.
3. In Properties set the Angle (360 = all the way round) and the Wall thickness.

*Tip:* Revolved Boss/Base on the Features tab revolves a flat sketch shape into a solid instead.

**Extrude — push the curve straight up**  
Pushes a curve straight up into a wall; a closed curve becomes a solid block.

1. Draw the curve with 3D Sketch.
2. Select it and click Extrude.
3. Set the Height and the Wall thickness in Properties.

*Tip:* A curved fence, a rib, a shaped wall from one stroke.

## Sheet Metal tab


### Sheet Metal ▸ Create


**Base Flange/Tab**  
The flat sheet every sheet metal part starts from. With a sketch shape selected (rectangle, polygon, circle) the sheet takes that outline; with nothing selected it is 100 × 60 mm.

1. Optional: draw the outline in a sketch and select it.
2. Click Base Flange/Tab — a 2 mm sheet appears and stays selected.
3. In Properties set the Thickness, Bend radius and K-factor (or apply a rule with Sheet Metal Rules).
4. Go on with Edge Flange, Hem or Fold.

*Tip:* Unfold shows the flat blank at any time.

**Convert to Sheet Metal**  
Turns a plate you already have — a thin cube or a sketch shape extruded to the sheet's thickness — into a sheet metal body, in the same place, so it can take flanges and unfold.

1. Select the plate in the tree.
2. Click Convert to Sheet Metal.
3. Its thinnest side becomes the thickness; the status bar says what it found.

*Tip:* A cube standing on edge is converted standing on edge.

**Edge Flange**  
Bends a wall up (or down) from an edge of the sheet, with the bend radius and allowance worked out for you.

1. Select the sheet metal body (the only one in view is taken by itself).
2. Click Edge Flange, then click the edge in the 3D view — Esc lets you choose it from a list instead.
3. In the window set the Height (to the outside), the Angle (90 = square; negative bends down), the Bend radius and, to stop short of the corners, the two Insets.
4. OK: the wall is added and the status bar gives the new flat blank size.

*Tip:* A flange's own outer edge can take another flange — that is how a box lip is made.

**Fold**  
Bends the flat sheet along a line across it (SolidWorks' Sketched Bend). The outline stays the flat blank; the bend allowance is centred on the line.

1. Select the sheet metal body while it is still flat.
2. Click Fold.
3. Give the bend line by its two ends (X, Y on the sheet — it starts as a line across the middle), the Angle and the Bend radius.
4. OK.

*Tip:* Fold BEFORE adding flanges or hems: a fold changes the edges they sit on, and is refused afterwards.

**Hem**  
Folds an edge right back over itself — a safe, stiff, rounded edge — leaving the rule's hem gap inside.

1. Select the sheet metal body.
2. Click Hem, then click the edge in the 3D view.
3. Set the Length of the folded-back strip; tick Fold under to turn it down instead of over.
4. OK.

*Tip:* The hem gap comes from the body's rule (Sheet Metal Rules).

**Path Flange**  
Several flanges in a row off one edge, a bend at every corner — a Z, a return lip, a channel — typed as length, angle pairs.

1. Select the sheet metal body.
2. Click Path Flange, then click the edge.
3. Type the segments as “length, angle; length, angle”: 20, 90; 10, 90 goes up 20 then turns in 10.
4. OK.

*Tip:* A negative angle bends the other way: 20, 90; 10, -90 is a Z.

**Contour Flange**  
A NEW sheet metal body from an open profile seen from the side — a channel, a Z or a hat section — with one bend at every corner, stretched to a width.

1. Click Contour Flange (nothing needs selecting).
2. Type the profile's points as “X, Z; X, Z; …” in order: 0, 30; 0, 0; 50, 0; 50, 30 is a U channel 50 wide, 30 high.
3. Set the Width (how long the section runs).
4. OK: the body is made and can take edge flanges and hems.

*Tip:* Keep the corners square to start; the bend radius rounds them.

**Perforate**  
A field of round holes over the flat sheet, kept clear of the edges and the bends — in the part, the flat pattern and the DXF.

1. Select the sheet metal body.
2. Click Perforate.
3. Set the Hole diameter, the Pitch (centre to centre — more than the diameter), the Margin and Staggered or Square.
4. OK: the status bar counts the holes; Unfold shows them on the blank.

*Tip:* Run it again to change the field: it replaces the last one.

**Create Flat Pattern**  
Puts a flat copy of the body beside it: the blank to cut, with its bend lines, while the folded part stays as it is.

1. Select the sheet metal body.
2. Click Create Flat Pattern.
3. The status bar gives the blank's size and the number of bends.

*Tip:* For the cutting file use Export Flat Pattern as DXF.

### Sheet Metal ▸ Modify


**Unfold**  
Shows the selected body flat — every bend opened out — to check the blank and its holes.

1. Select the sheet metal body.
2. Click Unfold.
3. Click Refold to fold it back up.

*Tip:* Nothing is lost: it is the same body, shown flat.

**Refold**  
Folds an unfolded body back up to its bent shape.

1. Select the unfolded sheet metal body.
2. Click Refold.

**Sheet Metal Rules**  
Named sets of thickness, bend radius, K-factor and hem gap — “Steel 2 mm”, “Aluminium 1.5 mm”. A body given a rule follows it: change the rule and every such body changes.

1. Click Sheet Metal Rules.
2. New… adds a rule; select one to edit its four values.
3. With a sheet metal body selected, apply the rule to it.
4. Close.

*Tip:* The rules are document variables, so they are saved with the file and written into the OpenSCAD program.

### Sheet Metal ▸ Export


**Export Flat Pattern as DXF**  
Writes the flat blank for a laser or punch: CUT outlines and holes, BEND_UP and BEND_DOWN lines and ETCH notes on their own layers, in millimetres.

1. Select the sheet metal body.
2. Click Export Flat Pattern as DXF.
3. Choose where to save the file.

*Tip:* Send the bend table with it so the folder knows each angle.

**Export Bend Table**  
Every bend as a CSV table: direction, angle, radius, length, allowance and where its centre line lies on the flat blank.

1. Select the sheet metal body.
2. Click Export Bend Table.
3. Choose where to save the file; open it in any spreadsheet.

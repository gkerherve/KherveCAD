"""The chapters of the User Guide (userguide.py shows them).

``chapters()`` returns (anchor, title, html) in reading order. A chapter
whose html is ``"@reference"`` is replaced by the tool reference that
userguide.py builds from tooltips.py. Screenshots come from
``khervecad/help/`` via ``figure()``; regenerate them with
``packaging/make_help_screenshots.py``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""


def chapters():
    from .userguide import figure, kbd
    K = kbd
    return [
        ("welcome", "Welcome", f"""
<p>KherveCAD is a CAD program for people who want real, printable,
exportable solids without learning a programming language first. You
draw, extrude, combine and arrange; behind the scenes every step is one
line of an <b>OpenSCAD</b> program, and OpenSCAD is the engine that
turns it into exact geometry.</p>
<p>The one idea to hold on to: <b>your model is a tree of objects</b>.
Every tool either adds a row to that tree or changes one. The program in
the <b>Code</b> tab is written from the tree, so the two always agree
&mdash; you can work in whichever you prefer.</p>
{figure("window", "The KherveCAD window with an example model loaded.")}
<table>
<tr><td><b>1</b></td><td><b>Object tree &amp; tabs</b> &mdash; the
model itself. Main (the assembly), Object (the part you are building),
Masters, Variables and Code.</td></tr>
<tr><td><b>2</b></td><td><b>Properties</b> &mdash; every setting of the
selected object: sizes, positions, angles, colour.</td></tr>
<tr><td><b>3</b></td><td><b>2D sketch</b> &mdash; a millimetre grid
where you draw profiles and drag parts into place.</td></tr>
<tr><td><b>4</b></td><td><b>3D preview</b> &mdash; the solid result.
Orbit, pan and zoom with the mouse.</td></tr>
<tr><td><b>5</b></td><td><b>Drawing tools &amp; solids</b> &mdash;
sketch tools, measuring, and one-click 3D shapes.</td></tr>
<tr><td><b>6</b></td><td><b>Main toolbar</b> &mdash; file, undo, the
operations (grouped), snapping, the sketch controls and the 3D
view.</td></tr>
</table>
<p><b>Selection is shared.</b> Click an object anywhere &mdash; tree, 2D
or 3D &mdash; and it is selected in all of them: the Properties panel
shows its settings, the sketch outlines it and the 3D view tints it
red.</p>
<p><b>Hover any icon</b> for a tooltip that says what it does and how to
use it, step by step. Press {K("F1")} to come back to this guide.</p>
"""),

        ("first-part", "Your first part in five minutes", f"""
<p>This walk-through makes a plate with a hole in it &mdash; the four
moves that build most parts: <i>draw, extrude, add, cut</i>.</p>

<h3>Step 1 &mdash; draw a rectangle</h3>
<ol>
<li>Pick the <b>Rectangle</b> tool in the left toolbar (or press
{K("R")}).</li>
<li>In the 2D sketch, press at one corner, drag to the other and let
go. The size reads live in millimetres.</li>
<li>Type exact numbers in <b>Properties</b>: Width 60, Height 40.</li>
</ol>
<p>Because you drew in the <b>Main</b> tab, KherveCAD makes the shape
into a new <b>Object</b> (a part) and opens the <b>Object</b> tab on it:
parts are built in the Object tab and arranged in Main.</p>
{figure("tutorial_1_rectangle", "A rectangle, drawn and sized. The "
        "Object tab has opened on the new part.")}

<h3>Step 2 &mdash; extrude it into a plate</h3>
<ol>
<li>With the rectangle selected, open the <b>Extrude</b> group on the
main toolbar and pick <b>Linear extrude</b>.</li>
<li>In Properties set <b>Height</b> to 8. The rectangle is now a plate:
in the tree, <i>Linear extrude</i> wraps <i>Rectangle</i>.</li>
</ol>
{figure("tutorial_2_extrude", "Linear extrude wraps the rectangle and "
        "gives it height.")}

<h3>Step 3 &mdash; add a cylinder where the hole goes</h3>
<ol>
<li>Click <b>Cylinder</b> in the left toolbar. It appears at the origin,
inside the part you are editing.</li>
<li>In Properties set both radii to 8, Height 20 and Z to &minus;6, so
it passes right through the plate.</li>
</ol>
{figure("tutorial_3_cylinder", "The cylinder pokes through the plate; "
        "it is selected, so it is tinted and its settings are shown.")}

<h3>Step 4 &mdash; cut the hole</h3>
<ol>
<li>In the tree, click <i>Linear extrude</i>, then Ctrl-click
<i>Cylinder</i> (the body first, then the cutter).</li>
<li>Open the <b>Combine</b> group and pick <b>Difference</b>. The
cylinder is subtracted from the plate.</li>
</ol>
{figure("tutorial_4_difference", "Difference: the first object minus "
        "everything after it. The hole is cut by the OpenSCAD engine.")}
<p>That is a finished part. Save it with {K("Ctrl+S")}, export it for
3D printing with <b>File &rsaquo; Export STL</b>, or click <b>To
Main</b> to place it into an assembly. Everything you did is undoable
one step at a time with {K("Ctrl+Z")}.</p>
<p class='tip'><i>Tip:</i> the same four moves with other shapes make
almost anything: a polygon extruded into a bracket, circles cut from a
plate for a flange, text extruded and cut into a nameplate.</p>
"""),

        ("window", "The window, panel by panel", f"""
<h3>The tabs above the tree</h3>
<p><b>Main</b> is the <i>assembly</i>: every part in your document, each
one row, placed where it belongs. The <b>Common segments ($fn)</b> box
at the top sets how smooth every circle, sphere and cylinder is (higher
is smoother and slower); untick it to let each shape use its own
value.</p>
{figure("tab_main", "Main tab: the document's parts and their "
        "placement.", 430)}
<p><b>Object</b> is where one part is <i>built</i>. Choose the part in
the drop-down, or <b>+ New</b> to start one; the pencil button renames
it and <b>To Main</b> places another copy of it into the assembly.
While this tab is open, the 2D and 3D views show only this part, at its
own origin.</p>
{figure("tab_object", "Object tab: the construction of one part, step "
        "by step.", 430)}
<p><b>Masters</b> holds reusable definitions &mdash; see the chapter on
Masters. <b>Variables</b> is a small spreadsheet of named numbers
(<i>w</i>, <i>wall</i>&hellip;) you can use in any field. <b>Code</b>
shows the OpenSCAD program and lets you edit it.</p>
{figure("tab_variables", "Variables tab: named values used by "
        "expressions like <i>w - 2 * wall</i>.", 430)}

<h3>Properties</h3>
<p>Every setting of the selected object, generated from its type: sizes,
position, angles, segments, colour, text. Any number field also accepts
an <b>expression</b> &mdash; <code>wall * 2</code>, <code>i * 10</code>,
<code>cos(a) * r</code> &mdash; which is how a model becomes adjustable.
A polygon shows its corners as an editable table.</p>
{figure("properties", "Properties of a cylinder.", 430)}

<h3>The 2D sketch</h3>
<p>A millimetre grid on one plane of the model &mdash; <b>Top (XY)</b>,
<b>Front (XZ)</b> or <b>Side (YZ)</b>, chosen in the main toolbar. The
two axes are coloured like the 3D gizmo (X red, Y green, Z blue).
Shapes are drawn here; a selected shape shows its size with dimension
arrows and square handles to resize it. 3D parts appear as filled
outlines you can drag. Middle-drag pans, the wheel zooms, and the scale
bar at the bottom left tells you how big a grid square is. The small
bar in the top-right corner does the same without the mouse: the arrows
scroll, the magnifiers zoom (hold a button to repeat), <b>Focus</b>
(&#x25CE;) frames the selected part wherever it is &mdash; handy when a
part is nowhere near the origin &mdash; and <b>Fit all</b> shows
everything.</p>
{figure("sketch", "The 2D sketch: a selected rectangle with its "
        "automatic dimensions, and a circle.")}

<h3>The 3D preview</h3>
<p>The solid result. <b>Left-drag</b> orbits, <b>right- or
middle-drag</b> pans, the <b>wheel</b> zooms and a <b>double-click</b>
frames the whole model. The floating bar at the top left sets
<b>brightness</b> and <b>contrast</b> (&#x27F2; resets them) and has
<b>Redraw</b> (&#x27F3;). The bar at the top right turns the model,
pans, zooms, frames the selected part (<b>Focus</b>) or the whole model
(<b>Fit all</b>). The label at the bottom says what you are
looking at: <i>built-in preview</i> (instant, approximate) or
<i>OpenSCAD</i> (exact), and how many parts are exact already.</p>
{figure("view3d_plate", "The 3D preview with the lighting bar.")}

<h3>The status bar</h3>
<p>From left to right: the cursor position in the sketch, messages,
the current file, the sketch zoom (1&nbsp;mm = n pixels) and the
engine: <i>OpenSCAD (ready)</i>, <i>(rendering&hellip;)</i> or
<i>built-in preview</i> when OpenSCAD is not installed.</p>
"""),

        ("toolbars", "The toolbars", f"""
<p>The <b>left toolbar</b> holds the drawing tools (one is always
active &mdash; Select by default), the two measuring tools, and the 3D
solids that are added with one click. The <b>main toolbar</b> along the
top is split into sections:</p>
{figure("toolbar_main", "The main toolbar and its sections.", 900)}
<ul>
<li><b>File</b> &mdash; New, Open, Save.</li>
<li><b>Undo</b> &mdash; Undo and Redo.</li>
<li><b>Operations</b> &mdash; six drop-down groups (below).</li>
<li><b>Assembly</b> &mdash; Snap objects together (the magnet).</li>
<li><b>Sketch</b> &mdash; grid, snap-to-grid, grid spacing, the sketch
plane and Fit sketch.</li>
<li><b>3D view</b> &mdash; Render with OpenSCAD, Fit 3D.</li>
<li><b>AI</b> &mdash; the assistant chat.</li>
</ul>
<h3>How the operation groups work</h3>
<p>Each group button is a family of tools. <b>Click the icon</b> and it
runs the tool shown &mdash; the one you used last in that family (it is
remembered between sessions). <b>Click the small arrow</b> next to it
to see the whole family and pick another; hovering a tool in the list
shows its full tooltip.</p>
<table><tr>
<td>{figure("group_extrude", "Extrude", 190)}</td>
<td>{figure("group_transform", "Move &amp; transform", 190)}</td>
<td>{figure("group_combine", "Combine", 190)}</td>
</tr><tr>
<td>{figure("group_deform", "Deform &amp; sculpt", 230)}</td>
<td>{figure("group_character", "Character", 260)}</td>
<td>{figure("group_logic", "Repeat &amp; logic", 190)}</td>
</tr></table>
<p>Operations act on the <b>selection</b>: select objects first (in the
tree or the sketch), then pick the operation &mdash; it wraps them, so
the tree shows e.g. <i>Rotate</i> with your objects inside. Group, the
loops and If/else also work with nothing selected: they add an empty
node you can drag objects into.</p>
<p>Every tool is described one by one in the <b>Tool reference</b>
chapter.</p>
"""),

        ("reference", "Tool reference", "@reference"),

        ("sketching", "Drawing in 2D", f"""
<p>2D shapes are the start of most parts: draw the outline, then give
it depth. Pick a tool in the left toolbar, draw in the sketch, then
refine the numbers in Properties.</p>
<ul>
<li><b>Rectangle</b> {K("R")} &mdash; drag corner to corner.</li>
<li><b>Circle</b> {K("C")} &mdash; press at the centre, drag out to the
radius. <i>Angle</i> 180 gives a semicircle, 90 a quarter.</li>
<li><b>Polygon</b> {K("P")} &mdash; click each corner, double-click or
{K("Enter")} to close, {K("Esc")} to abandon.</li>
<li><b>Line</b> {K("L")} &mdash; a bar between two points, with a
<i>Width</i>; it extrudes like any shape.</li>
<li><b>Text</b> {K("T")} &mdash; click to place, type the words in
Properties.</li>
</ul>
<h3>Grid, snap and planes</h3>
<p><b>Grid</b> shows the millimetre grid; <b>Snap</b> makes drawn points
land on it; the <b>Grid</b> box sets the spacing (down to 0.01 mm). The
<b>Plane</b> box picks which plane you draw on: Top (XY) for plates and
footprints, Front (XZ) for profiles you will revolve, Side (YZ).</p>
<h3>Measuring</h3>
<p><b>Measure</b> {K("M")}: click two points &mdash; the distance shows in
the status bar and nothing is added. <b>Add dimension</b> {K("D")}: the
same, but it leaves a dimension line on the sketch (View &rsaquo; Clear
Dimensions removes them). Both snap to corners and edges. Selected
shapes also show their own size automatically (View &rsaquo; Dimensions
on selection).</p>
<h3>Editing shapes</h3>
<p>With <b>Select</b> {K("V")}: click to select, drag to move, drag a
square handle to resize. A polygon's corners are edited exactly in the
points table in Properties. View &rsaquo; Fit Sketch
{K("Ctrl+Shift+F")} and Zoom to Selection reframe the view.</p>
<p class='tip'><i>Tip:</i> 2D shapes combine too &mdash; a Difference of
two circles is a ring, a Union of rectangles an L-shape &mdash; before
you extrude.</p>
"""),

        ("solids", "Making solids", f"""
<h3>From a 2D shape</h3>
<p><b>Linear extrude</b> pushes the selected 2D shapes straight up by a
<i>Height</i>. <i>Twist</i> turns the top as it rises (a twisted vase),
<i>Scale</i> shrinks or grows the top (0 makes a point, a pyramid),
<i>Center</i> extrudes equally up and down.</p>
<p><b>Rotate extrude</b> spins a profile round the vertical axis like a
lathe. Draw <i>half</i> the cross-section, to the right of the Y axis:
its X becomes the radius and its Y the height. A profile that crosses
X&nbsp;=&nbsp;0 turns red. An <i>Angle</i> below 360 makes a slice.</p>
<h3>Ready-made solids</h3>
<p>The bottom of the left toolbar adds a solid with one click:
<b>Cube</b>, <b>Sphere</b>, <b>Cylinder</b> (a different top radius makes
a cone), <b>Capsule</b> (a rod with round ends between two points),
<b>Ellipsoid</b>, <b>Rounded box</b> and <b>Loft</b> (a smooth tube
through a list of cross-sections). In the Main tab a new solid becomes
its own part and the Object tab opens on it; in the Object tab it is
added to the part you are building.</p>
<p><b>Segments</b> sets how many facets make a round shape. The document
default is the <b>Common segments ($fn)</b> box in the Main tab.</p>
<h3>Other ways in</h3>
<ul>
<li><b>Insert &rsaquo; Part Library</b> {K("Ctrl+L")} &mdash;
parametric flanges, fasteners with real threads, valves, glassware,
furniture.</li>
<li><b>File &rsaquo; Import Mesh</b> {K("Ctrl+Shift+I")} &mdash; STL, OBJ,
OFF or 3MF files, or drag the file onto the window.</li>
<li><b>Insert &rsaquo; OpenSCAD code</b> &mdash; a block of raw OpenSCAD
(e.g. a BOSL2 call) that the engine renders.</li>
</ul>
"""),

        ("combine", "Moving and combining", f"""
<h3>Moving, turning, resizing</h3>
<p>Most solids have their own <b>X / Y / Z</b> in Properties, and you can
drag any part in the sketch. The <b>Move &amp; transform</b> group wraps
the selection instead: <b>Translate</b> (move by X/Y/Z), <b>Rotate</b>
(degrees about X, then Y, then Z, around the origin), <b>Scale</b>
(factors; 1 = unchanged) and <b>Mirror</b> (reflect; the original is
not kept).</p>
<p class='tip'><i>Tip:</i> Rotate turns around the origin, so rotate a
part <i>before</i> moving it away, or it will swing round in a big
arc.</p>
<h3>Combining</h3>
<ul>
<li><b>Group (union)</b> {K("Ctrl+G")} &mdash; many objects become one.
{K("Ctrl+Shift+G")} ungroups.</li>
<li><b>Difference</b> &mdash; keeps the <b>first</b> child and cuts every
other child out of it. Order matters: select the body first. In the
tree, drag the rows (or {K("Ctrl+&uarr;")}/{K("Ctrl+&darr;")}) to change
which one is the body.</li>
<li><b>Intersection</b> &mdash; keeps only where all children overlap.</li>
</ul>
<p>Right-click &rsaquo; <b>Apply operation</b> in the tree offers the rest:
<b>Hull</b> (shrink-wrap around the children &mdash; two spheres make a
capsule), <b>Minkowski</b> (sweep one shape around another),
<b>Offset</b> (round or inset 2D corners) and <b>Round edges</b> (a
small Minkowski sphere that fillets a finished solid).</p>
<p class='tip'><i>Why is my hole not cut?</i> The instant built-in
preview draws a Difference as its first child only. The OpenSCAD engine
cuts it for real a moment later (the badge reads <i>OpenSCAD</i> or
<i>n/n parts exact</i>); press {K("F5")} to render right away.</p>
"""),

        ("tree", "Working with the object tree", f"""
<p>The tree <i>is</i> the model: one row per step, children indented
under the operation that wraps them.</p>
<table>
<tr><td>Select</td><td>click; Ctrl-click adds; {K("Tab")} /
{K("Shift+Tab")} (or {K("A")} / {K("Q")}) step to the next / previous
object</td></tr>
<tr><td>Hide / show</td><td>{K("Space")} or right-click &rsaquo; Hide. Hidden
rows turn grey and italic, and everything under them is dimmed.</td></tr>
<tr><td>Rename</td><td>right-click &rsaquo; Rename</td></tr>
<tr><td>Reorder / move</td><td>drag and drop; {K("Ctrl+&uarr;")} /
{K("Ctrl+&darr;")} within the parent</td></tr>
<tr><td>Copy &amp; paste</td><td>{K("Ctrl+C")} {K("Ctrl+X")}
{K("Ctrl+V")} &mdash; works between two KherveCAD windows too</td></tr>
<tr><td>Duplicate / delete</td><td>{K("Ctrl+D")} / {K("Delete")}</td></tr>
<tr><td>Colour</td><td>right-click &rsaquo; Colour&hellip;</td></tr>
</table>
<p>The right-click menu also has <b>Apply operation</b>, <b>Group /
Ungroup</b>, <b>Make Object</b>, <b>Make Master</b> and, on a part,
<b>Edit in Object tab</b> (or double-click it), <b>Anchors</b> and
<b>Attach / Detach</b>.</p>
<p>A placed part shows extra grey <b>Position</b>, <b>Rotation</b> and
<b>Color</b> rows under it: they mirror where the part has been placed
(by dragging, snapping or typing) and cannot be edited themselves &mdash;
click them to select the part.</p>
<h3>Names that say what things are</h3>
<p>A tree of ten rows all called <i>Cube</i> is hard to read. Rename
rows as you go, in the form <b>Cube [Body]</b>: the part in brackets is
a label, and it is also written into the program as a comment, so it
survives saving as .scad and importing again. It works the other way
too &mdash; when an assistant (or you) writes OpenSCAD with a comment at
the end of a line, the comment becomes the label:</p>
<pre>color("pink") cube(body, center=true);  // Body
for (px = [-1, 1]) for (py = [-1, 1])  // Legs</pre>
{figure("named_rows", "Rows named from the comments in the code: Cube "
        "[Body], Cube [Head], For px [Legs]&hellip;", 430)}
<h3>Red means broken</h3>
<p>A row that cannot work &mdash; a bad expression, an empty extrude, a 3D
solid inside an extrude, a revolve crossing its axis &mdash; turns
<b>red</b>. Hover it for the reason; its lines are red in the Code tab
too. OpenSCAD's own errors are mapped back to the rows that caused
them.</p>
"""),

        ("logic", "Variables, expressions and logic", f"""
<h3>Variables</h3>
<p>Give important sizes a name in the <b>Variables</b> tab &mdash;
<i>w = 60</i>, <i>wall = 2</i> &mdash; and use the name in any field:
Width <code>w</code>, inner width <code>w - 2 * wall</code>. Change the
variable and everything that uses it follows. The <b>Scope</b> box
switches between document-wide variables and those of the Object being
edited.</p>
<h3>Expressions</h3>
<p>Any number field takes an expression: <code>+ - * / % ^</code>,
comparisons, <code>a ? b : c</code>, and <code>sin cos tan sqrt abs
min max round floor ceil pow</code>&hellip; (angles in degrees).
Vectors work too: <code>size.x</code>, <code>pts[2]</code>.</p>
<h3>Repeating and choosing</h3>
<ul>
<li><b>For loop</b> repeats its contents. The variable runs
<i>From</i> &rarr; <i>To</i> by <i>Step</i>, or through a list of
<i>Values</i>. Use it in the contents: X = <code>i * 20</code> makes a
row, Rotate Z = <code>i * 60</code> a ring. A loop inside a loop makes
a grid.</li>
<li><b>While loop</b> repeats while a condition holds, updating its
variable each time (e.g. start 1, condition <code>x &lt; 100</code>,
update <code>x * 2</code>).</li>
<li><b>If / else</b> shows its contents only when the condition is true,
and its <i>Else</i> row otherwise &mdash; switch features on and off
with a variable, or alternate parts inside a loop with <code>i % 2 ==
0</code>.</li>
</ul>
<p>With objects selected, these wrap them; with nothing selected they
add an empty node to drag objects into. The <b>Examples &rsaquo;
Learn</b> menu has a numbered tutorial for each.</p>
"""),

        ("assemblies", "Parts and assemblies", f"""
<p>KherveCAD separates <b>building a part</b> from <b>arranging
parts</b>, like SolidWorks or Onshape:</p>
<ul>
<li>An <b>Object</b> is a part definition, built in the <b>Object
tab</b>. It becomes its own OpenSCAD <code>module</code>.</li>
<li>The <b>Main tab</b> is the assembly: <b>instances</b> of Objects,
each with its own position, rotation and colour. One Object can be
placed many times &mdash; edit it once and every copy changes.</li>
</ul>
<h3>Making and placing parts</h3>
<ul>
<li><b>Insert &rsaquo; New Object</b> {K("Ctrl+Alt+N")}, or <b>+ New</b>
in the Object tab, starts an empty part.</li>
<li>Right-click objects &rsaquo; <b>Make Object</b> turns them into a
part.</li>
<li><b>To Main</b> in the Object tab (or right-click in Main &rsaquo;
Insert Object) places another instance.</li>
<li>Drag a part's outline in the sketch to move it on the chosen plane,
or type its X/Y/Z and angles in Properties.</li>
</ul>
<h3>Snapping parts together</h3>
<p>The <b>Snap objects</b> tool {K("J")} joins two parts face to face,
like a joint in Fusion 360:</p>
<ol>
<li>Press {K("J")} (or the magnet in the main toolbar). A banner across
the 3D view tells you what to click.</li>
<li>Click the face or edge of the part you want to <b>move</b>. The
face under the cursor lights up first, named after the anchor it will
use; the one you click stays orange.</li>
<li>Click the face on the part it should sit against. The part jumps
into place.</li>
<li>A small window opens to fine-tune: <b>Offset</b> (a gap in mm),
<b>Spin</b> (turn about the joint), <b>Flip 180&deg;</b> and
<b>Detach</b>.</li>
</ol>
<p>{K("Esc")} (or a right-click) cancels. A snap is <b>live</b>: move the
base part and everything attached follows. Dragging an attached part, or
typing its position, detaches it (the status bar says so).</p>
<h3>Anchors and the Attach dialog</h3>
<p>Every part has automatic <b>anchors</b> &mdash; its origin, the centres
of its six faces, twelve edge midpoints and eight corners &mdash; drawn as
coloured markers when the part is selected. Right-click a part &rsaquo;
<b>Anchors</b> to add your own by clicking the model, to <b>set the
origin</b> to any anchor, or to remove one. Right-click &rsaquo;
<b>Attach&hellip;</b> opens the Attach dialog, where you choose the two
anchors by name; every change previews live and Cancel puts everything
back.</p>
{figure("dialog_attach", "The Attach dialog: which anchor of this part "
        "meets which anchor of the other.", 450)}
<p>Inside the Object tab the same tools snap the <b>groups that make up
one part</b> to each other, so a part can itself be assembled from
pieces.</p>
"""),

        ("masters", "Masters and linked copies", f"""
<p>A <b>Master</b> is a reusable piece kept in the <b>Masters</b> tab; a
<b>Linked copy</b> places it in the model with its own position. Edit
the master and every copy changes &mdash; the classic example is one
bolt copied round a bolt circle.</p>
<ol>
<li>Right-click an object &rsaquo; <b>Make Master</b>. It moves to the
Masters tab and a Linked copy is left where it was.</li>
<li>In the Masters tab, select a master and add more copies; give each
copy its position (or put one copy in a For loop).</li>
</ol>
{figure("tab_masters", "The Masters tab.", 430)}
<p>Masters are for repeated <i>geometry</i> inside one model; Objects
are for <i>parts</i> in an assembly. Examples &rsaquo; Learn &rsaquo;
21&nbsp;&middot;&nbsp;Masters and Mechanical &rsaquo; Bolt circle show
both.</p>
"""),

        ("colour", "Colour and materials", """
<p>Right-click an object &rsaquo; <b>Colour&hellip;</b>, or use the colour
field in Properties. A colour is an ordinary row in the tree (OpenSCAD's
<code>color()</code>) with an <b>opacity</b> and a <b>material</b>:
Plastic, Metal, Matte, Clay, Glass, Rubber, Skin, Gold, Copper or
Emissive (<i>Default</i> follows the 3D render style). Glass is
see-through.</p>
<p>In the Main tab, colour an instance directly: each copy of a part
can have its own colour. Colours and materials are saved with the
document and exported in the .scad program; the exact OpenSCAD render
of each part is tinted with its colour.</p>
"""),

        ("character", "Characters and organic shapes", f"""
<p>For animals, figures, plants and anything soft, KherveCAD has
shapes and operations that go beyond boxes and cylinders.</p>
<h3>Soft solids</h3>
<p><b>Capsule</b> (limbs, fingers), <b>Ellipsoid</b> (heads, bodies,
eggs), <b>Rounded box</b> (soft blocks) and <b>Loft</b> (tails, necks,
horns: a tube through a list of rings).</p>
<h3>The Character group</h3>
<ul>
<li><b>Symmetry</b> &mdash; keeps its contents and their mirror image:
model the left arm and the right one appears, and follows every
edit.</li>
<li><b>Joint</b> &mdash; rotates its contents about a pivot, like an
elbow. Put the pivot on the hinge, then bend. Joints nest, so a tree of
them is a skeleton you can pose.</li>
</ul>
<h3>The Deform &amp; sculpt group</h3>
<ul>
<li><b>Smooth blend</b> &mdash; melts the shapes inside together like
clay, with smooth fillets where they meet. <i>Blend radius</i> is how
far the melting reaches.</li>
<li><b>Bend</b>, <b>Twist</b>, <b>Taper</b> &mdash; curve, wring or
narrow the contents along an axis.</li>
<li><b>Lattice</b> &mdash; move the eight corners of the bounding box and
the shape follows smoothly.</li>
<li><b>Subdivide</b> &mdash; smooths a blocky shape.</li>
</ul>
<table><tr>
<td>{figure("character_tulip", "Flowers &rsaquo; Tulip", 360)}</td>
<td>{figure("character_oak", "Trees &rsaquo; Oak", 360)}</td>
</tr></table>
<p>The <b>Examples</b> menu has a garden of flowers and trees built this
way &mdash; open one and look at its tree to see how.</p>
"""),

        ("view3d", "The 3D view", f"""
<table>
<tr><td>Orbit</td><td>left-drag</td></tr>
<tr><td>Pan</td><td>right-drag or middle-drag</td></tr>
<tr><td>Zoom</td><td>mouse wheel</td></tr>
<tr><td>Frame everything</td><td>double-click, {K("Ctrl+F")} or the Fit
3D button</td></tr>
<tr><td>Buttons</td><td>the bar in the top-right corner: turn left /
right, pan, zoom in / out (hold to repeat), <b>Focus</b> on the selected
part, <b>Fit all</b></td></tr>
<tr><td>Standard views</td><td>View &rsaquo; 3D Camera: Isometric, Top,
Bottom, Front, Back, Left, Right</td></tr>
</table>
<p><b>View &rsaquo; 3D Render Style</b> changes the look (Shaded, Matte,
Clay, Toon, Brushed metal, Gold, Copper, Wireframe, X-ray);
<b>3D Background</b> and <b>3D Projection</b> (perspective or
orthographic) are next to it. The floating bar sets brightness and
contrast. None of these change the model.</p>
{figure("render_styles", "Four of the render styles.")}
<h3>Preview and exact render</h3>
<p>Every change redraws instantly with the <b>built-in preview</b>. If
OpenSCAD is installed (it is included with the installer), an
<b>exact</b> render follows a moment later, one part at a time &mdash;
the badge counts <i>n/m parts exact</i>. Holes are only really cut in
the exact render. {K("F5")} renders immediately.</p>
<p>The preview draws in an exact back-to-front order that completes a
moment after each change, by itself. If the view ever looks stale,
<b>Redraw</b> (&#x27F3; on the lighting bar) rebuilds it from the tree.</p>
"""),

        ("library", "Part Library and Examples", f"""
<h3>Part Library</h3>
<p><b>Insert &rsaquo; Part Library</b> {K("Ctrl+L")} opens a catalogue of
parametric parts: CF and KF vacuum flanges, fittings, valves and pumps;
bolts, screws and nuts from M3 to M20 with real threads; laboratory
glassware; furniture. Pick a category, a part and a standard size, adjust
any dimension, then <b>Insert</b>. The window stays open while you work.
Each part arrives as one Object; its construction is in the Object
tab.</p>
{figure("dialog_library", "The Part Library.", 560)}
<p>The <b>Library</b> menu inserts the same parts at their default size
in one click.</p>
<h3>Examples</h3>
<p>The <b>Examples</b> menu replaces the document with a ready-made
model: <b>Learn</b> (21 numbered tutorials, one technique each, from a
single cube to masters), <b>Mechanical</b> (brackets, gears, bearings,
pulleys, a bolted flange), <b>Projects</b>, <b>Showcase</b>,
<b>Flowers</b>, <b>Trees</b>, <b>Vacuum</b> and <b>Room</b>. Open one
and click through its tree to see how it is made. You are asked before
unsaved work is replaced.</p>
{figure("menu_examples", "The Examples menu.", 140)}
"""),

        ("code", "OpenSCAD code", f"""
<p>The <b>Code</b> tab shows the OpenSCAD program written from the tree.
Selecting an object highlights its lines; broken objects are tinted
red.</p>
{figure("tab_code", "The Code tab for the plate-with-a-hole part.", 430)}
<ul>
<li><b>Edit and apply</b>: change the text and press <b>Apply code</b>
&mdash; it is read back into real, editable objects.</li>
<li><b>Scope</b>: <i>Whole program</i> or <i>Active object</i> (just the
part open in the Object tab).</li>
<li>The toolbar has undo/redo, cut/copy/paste and indent; {K("Tab")} /
{K("Shift+Tab")} indent and dedent the selected lines.</li>
</ul>
<h3>Import and export</h3>
<ul>
<li><b>File &rsaquo; Export OpenSCAD</b> {K("Ctrl+E")} writes a standalone
.scad file; <b>Import OpenSCAD</b> {K("Ctrl+I")} (or opening a .scad
file) reads one back as objects. Export &rarr; import &rarr; export gives
the same program.</li>
<li>Files that use features KherveCAD cannot turn into objects can be
loaded as a single <b>raw OpenSCAD block</b>: the engine renders it,
and it is edited as text.</li>
<li>A comment at the end of a line names that object in the tree:
<code>cube(10);  // Lid</code> becomes <b>Cube [Lid]</b>.</li>
</ul>
"""),

        ("ai", "Assistants: Claude and the ChatBox", f"""
<h3>Connect to Claude (no API key)</h3>
<p><b>AI &rsaquo; Connect to Claude (Simple)&hellip;</b> lets Claude
Desktop, Claude Code, Cursor, Cline, VS Code or LM Studio build directly
in the open document, using the account you already have.</p>
<ol>
<li>Tick <b>Let assistants connect to this document</b>.</li>
<li>Leave <b>The assistant may</b> on <b>Full</b> (recommended), so it
can also open and export the files you mention. <i>Edit</i> keeps it
inside the open document; <i>Read only</i> lets it only look.</li>
<li>Under <b>Connect an application</b>, pick yours and press
<b>Connect</b>; restart that application.</li>
<li>In its chat, <b>mention KherveCAD</b>: <i>&ldquo;in KherveCAD, build
a 40 mm bracket with two M6 holes&rdquo;</i>.</li>
</ol>
<p>The assistant works with real objects: it reads and edits the tree,
writes OpenSCAD that arrives as editable rows (labelled, e.g. <b>Cube
[Body]</b>), inserts library parts, assembles Objects and looks at the 3D
view to check its work. Each of its steps is one {K("Ctrl+Z")}. The
connection stays on this computer.</p>
<p>The assistant labels every piece it builds (<b>Cube [Front-left
leg]</b>, <b>Sphere [Left eye]</b>), and when it makes a part an
<b>Object</b> or a <b>Master</b> it tells you what it made, why, and in
which tab to find it.</p>
<h3>Vibe Model</h3>
<p>Building by conversation? Click <b>Vibe Model</b> at the right end
of the main toolbar ({K("Ctrl+Shift+M")}, or View &rsaquo; Vibe Model):
the tree, Properties, the 2D sketch and the drawing tools fold away and
the 3D model fills the window, so you can describe the part and watch it
build. Click again to bring everything back and edit by hand. The name
borrows from <i>vibe coding</i> &mdash; building software by describing
it to an AI.</p>
<h3>The ChatBox</h3>
<p><b>AI &rsaquo; ChatBox</b> {K("Ctrl+/")} (or the robot button) docks a
chat on the right that works with your own <b>Claude, Mistral or
Ollama</b> API key (the gear button). Describe a part, or paste a
picture of one; the reply is applied to the document &mdash; inside the
part you are editing when the Object tab is open. Type <b>/help</b> for
its commands.</p>
{figure("chat_panel", "The ChatBox.", 270)}
"""),

        ("files", "Files, Git and publishing", f"""
<ul>
<li><b>.kcad</b> is KherveCAD's own format: every object, colour,
variable, part and snap. Save {K("Ctrl+S")}, Save As
{K("Ctrl+Shift+S")}, Open {K("Ctrl+O")}, Open Recent.</li>
<li><b>Open</b> also accepts .scad programs and meshes (.stl, .obj, .off,
.3mf); so does dragging a file onto the window.</li>
<li><b>Export STL</b> {K("Ctrl+Shift+E")} for 3D printing (exact when
OpenSCAD is installed); <b>Export OpenSCAD</b> {K("Ctrl+E")}.</li>
<li><b>Export PNG</b> {K("Ctrl+Alt+E")} saves a picture of the 3D view in
its colours, style and lighting: the <b>current view</b> exactly as the
camera shows it, or <b>all standard views</b> (front-right and back-left
isometric, front, back, left, right, top, bottom), one file each. Pick a
size up to 4K, and tick <b>Transparent background</b> to drop the picture
onto a slide or a web page. Your own camera never moves.</li>
<li><b>File &rsaquo; Show in File Explorer</b> opens the document's
folder; <b>New Window</b> {K("Ctrl+Shift+N")} opens a second document.</li>
<li><b>View &rsaquo; Add Reference Image&hellip;</b> puts a photo or
drawing on the sketch plane to trace over; it shows in both views.</li>
</ul>
<h3>Git</h3>
<p>The <b>Git</b> menu versions the folder holding your document:
<b>Commit</b> {K("Ctrl+K")} saves a snapshot with a message,
<b>Push</b> / <b>Pull</b> sync with GitHub or GitLab, and <b>Connect to
GitHub / GitLab</b> sets up the remote.</p>
<h3>Publishing to Printables</h3>
<p><b>File &rsaquo; Publish to Printables&hellip;</b>
{K("Ctrl+Shift+P")} prepares everything for an upload: STL and 3MF
files, the .scad and .kcad, preview pictures of every side (the
front-right isometric first, as the cover), a description and the
upload form's answers. It then opens the Printables
upload page; the final upload is yours to click.</p>
"""),

        ("updates", "Updates", f"""
<p>KherveCAD keeps itself up to date from its GitHub releases.</p>
<ul>
<li>An installed copy checks <b>once a day</b>, a few seconds after it
starts. When a newer version exists, a window lists <b>what
changed</b>: the release notes and every improvement since your
version.</li>
<li><b>Download and install</b> fetches it in the background (with a
progress bar you can cancel), then closes KherveCAD, installs and starts
the new version. You are asked to save unsaved work first.</li>
<li><b>Skip this version</b> stops the reminder for that version only;
<b>Later</b> asks again next time.</li>
<li><b>Help &rsaquo; Check for Updates&hellip;</b> checks now;
<b>Help &rsaquo; Check for Updates Automatically</b> turns the daily
check on or off.</li>
</ul>
{figure("dialog_update", "An update is available: what changed, and "
        "the choice to install it.", 620)}
<p>The version number is <b>0.1.<i>N</i></b>, where <i>N</i> counts the
changes made to KherveCAD so far &mdash; it goes up by one with each
change, and the title bar and Help &rsaquo; About show it.</p>
<p class='tip'>A portable copy, or KherveCAD run from its source code,
is not replaced automatically: the update window offers the download
page instead.</p>
"""),

        ("shortcuts", "Keyboard shortcuts", f"""
<p>On a Mac, {K("Ctrl")} is the {K("&#8984; Cmd")} key.</p>
<table>
<tr><td colspan='2'><b>Tools</b></td></tr>
<tr><td>{K("V")} {K("L")} {K("R")} {K("C")} {K("P")} {K("T")}</td>
<td>Select, Line, Rectangle, Circle, Polygon, Text</td></tr>
<tr><td>{K("M")} {K("D")}</td><td>Measure, Add dimension</td></tr>
<tr><td>{K("J")}</td><td>Snap objects together</td></tr>
<tr><td>{K("Enter")} / {K("Esc")}</td><td>Finish / abandon a polygon;
{K("Esc")} also cancels a snap</td></tr>
<tr><td colspan='2'><b>File</b></td></tr>
<tr><td>{K("Ctrl+N")} {K("Ctrl+O")} {K("Ctrl+S")}</td><td>New, Open,
Save ({K("Ctrl+Shift+S")} Save As, {K("Ctrl+Shift+N")} New
Window)</td></tr>
<tr><td>{K("Ctrl+I")} {K("Ctrl+Shift+I")}</td><td>Import OpenSCAD, Import
mesh</td></tr>
<tr><td>{K("Ctrl+E")} {K("Ctrl+Shift+E")}</td><td>Export OpenSCAD, Export
STL</td></tr>
<tr><td>{K("Ctrl+Alt+E")}</td><td>Export PNG</td></tr>
<tr><td>{K("Ctrl+Shift+P")}</td><td>Publish to Printables</td></tr>
<tr><td colspan='2'><b>Edit</b></td></tr>
<tr><td>{K("Ctrl+Z")} {K("Ctrl+Y")}</td><td>Undo, Redo (also
{K("Ctrl+Shift+Z")})</td></tr>
<tr><td>{K("Ctrl+X")} {K("Ctrl+C")} {K("Ctrl+V")}</td><td>Cut, Copy,
Paste</td></tr>
<tr><td>{K("Ctrl+D")} {K("Delete")}</td><td>Duplicate, Delete</td></tr>
<tr><td>{K("Ctrl+G")} {K("Ctrl+Shift+G")}</td><td>Group, Ungroup</td></tr>
<tr><td>{K("Ctrl+&uarr;")} {K("Ctrl+&darr;")}</td><td>Move up / down in
the tree</td></tr>
<tr><td>{K("Tab")} {K("Shift+Tab")} ({K("A")} {K("Q")})</td><td>Next /
previous object</td></tr>
<tr><td>{K("Space")}</td><td>Hide / show the selection</td></tr>
<tr><td colspan='2'><b>Insert &amp; view</b></td></tr>
<tr><td>{K("Ctrl+Alt+N")}</td><td>New Object</td></tr>
<tr><td>{K("Ctrl+L")}</td><td>Part Library</td></tr>
<tr><td>{K("Ctrl++")} {K("Ctrl+-")} {K("Ctrl+0")}</td><td>Sketch zoom
in, out, reset</td></tr>
<tr><td>{K("Ctrl+Shift+F")} {K("Ctrl+F")}</td><td>Fit sketch, Fit 3D
view</td></tr>
<tr><td>{K("Ctrl+'")} {K("Ctrl+Shift+'")}</td><td>Grid, Snap to
grid</td></tr>
<tr><td>{K("F5")}</td><td>Render with OpenSCAD</td></tr>
<tr><td colspan='2'><b>Other</b></td></tr>
<tr><td>{K("Ctrl+/")}</td><td>ChatBox</td></tr>
<tr><td>{K("Ctrl+K")}</td><td>Git commit</td></tr>
<tr><td>{K("F1")}</td><td>This guide ({K("Ctrl+F")} inside it
searches)</td></tr>
</table>
"""),

        ("troubleshooting", "Troubleshooting", f"""
<h3>A hole or cut does not show</h3>
<p>The instant preview draws a Difference as its first child. Wait for
the badge to read <i>OpenSCAD</i> or <i>n/n parts exact</i>, or press
{K("F5")}. If the status bar says <i>built-in preview</i>, OpenSCAD was
not found: install it, or point to it with <b>Edit &rsaquo; Locate
OpenSCAD&hellip;</b></p>
<h3>Something turned red</h3>
<p>Hover the red row: the tooltip says what is wrong (a typo in an
expression, a 3D solid inside an extrude, a revolve profile crossing
the axis&hellip;). Undo {K("Ctrl+Z")} if you are not sure.</p>
<h3>An operation did nothing</h3>
<p>Operations act on the selection. Select objects first &mdash; in the
Object tab, select them in <i>that</i> tab's tree.</p>
<h3>The model is slow</h3>
<p>Lower <b>Common segments ($fn)</b> in the Main tab (32&ndash;48 is
plenty while designing), or a big shape's own Segments. Orbiting a large
model shows a lighter draft and snaps back to full detail when you let
go.</p>
<h3>The 3D view looks wrong</h3>
<p>Press <b>Redraw</b> (&#x27F3;) on the lighting bar, or
<b>Fit 3D</b> if the model is out of view.</p>
<h3>An assistant cannot see KherveCAD</h3>
<p>Check that <b>Let assistants connect</b> is ticked in AI &rsaquo;
Connect to Claude, that the application was restarted after
<b>Connect</b>, and mention KherveCAD in the chat.</p>
<h3>KherveCAD crashed</h3>
<p>A report is written to <code>khervecad_crash.log</code> in your
temporary folder (<code>%TEMP%</code> on Windows). Please attach it when
you report the problem.</p>
"""),
    ]

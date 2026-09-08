"""The Help > User Guide window: a detailed, scrollable HTML guide.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QTextBrowser,
                             QVBoxLayout)

from . import APP_NAME


def _section(title, body):
    return f"<h2 style='color:#3776ab'>{title}</h2>\n{body}\n"


def _kbd(keys):
    return (f"<code style='background:#eee;padding:1px 5px;"
            f"border-radius:3px'>{keys}</code>")


GUIDE_HTML = f"""
<h1><span style='color:#3776ab'>Kherve</span><span
 style='color:#e07b39'>CAD</span> &mdash; User Guide</h1>
<p>KherveCAD is an easy-to-use CAD program with <b>OpenSCAD as the
engine</b>. Your model is a <b>tree of objects</b> &mdash; 2D shapes, 3D
primitives, extrusions, transforms and booleans &mdash; that maps
one-to-one to an OpenSCAD program. Every tool just creates or edits nodes
in that tree, and the <b>Code</b> tab is regenerated from it, so the two
can never disagree.</p>

{_section("1. The layout", '''
<p>The window has four panels:</p>
<ul>
<li><b>Objects / Code</b> (top-left) &mdash; the object tree, and a
read-only view of the generated OpenSCAD program.</li>
<li><b>Properties</b> (bottom-left) &mdash; the editable parameters of the
selected object.</li>
<li><b>2D Sketch</b> (top-right) &mdash; a millimetre grid where you draw
profiles and lay out (assemble) parts.</li>
<li><b>3D Preview</b> (bottom-right) &mdash; the shaded result you can
orbit, pan and zoom.</li>
</ul>
<p>Selection is shared: pick an object in any panel and the tree, the
properties, the sketch outline and the 3D geometry all highlight it (in
amber).</p>
''')}

{_section("2. Drawing 2D shapes", f'''
<p>The <b>vertical toolbar</b> holds the sketch tools: <b>Select</b>,
<b>Line</b>, <b>Rectangle</b>, <b>Circle</b>, <b>Polygon</b> and
<b>Text</b>. Pick one and draw in the 2D view; the size is shown live as
you drag, and everything reads in <b>millimetres</b>.</p>
<ul>
<li>The <b>grid</b> and <b>snap</b> toggles (main toolbar) keep points on
round coordinates.</li>
<li>Drag a shape to move it; drag its handles to resize; a polygon's
points are editable as a table in the Properties panel.</li>
<li>A <b>circle</b> has an <i>angle</i> (90 = quarter, 180 = semicircle)
that compiles to a partial fan.</li>
<li>Middle-mouse drag pans, the wheel zooms; use <b>Fit Sketch</b> or
<b>Zoom to Selection</b> to reframe.</li>
</ul>
''')}

{_section("3. Making solids &mdash; extrude &amp; revolve", '''
<p>2D profiles become solids through the operations on the main toolbar,
which <b>wrap</b> the selected object:</p>
<ul>
<li><b>Linear Extrude</b> &mdash; push a profile up by a height (with
optional twist, scale and a draft angle).</li>
<li><b>Rotate Extrude</b> &mdash; revolve a profile around the Y axis to
make lathe-turned shapes (flanges, cups, cones).</li>
</ul>
<p>You can also drop in <b>3D primitives</b> directly &mdash; <b>Cube</b>,
<b>Sphere</b> and <b>Cylinder</b> &mdash; from the vertical toolbar, or
<b>import an STL</b>.</p>
''')}

{_section("4. Transforms &amp; booleans", '''
<p>Operations that reshape or combine objects wrap the current selection:</p>
<ul>
<li><b>Translate / Rotate / Scale / Mirror</b> &mdash; move objects in
space.</li>
<li><b>Union</b> (group), <b>Difference</b> (cut) and
<b>Intersection</b> &mdash; the boolean operations. Difference subtracts
every later child from the first.</li>
<li><b>Hull</b> and <b>Minkowski</b> &mdash; convex wrapping and
offsetting; <b>Round Edges</b> uses a small Minkowski sphere to fillet a
finished solid.</li>
<li><b>Offset</b> rounds or insets 2D corners before extruding.</li>
</ul>
<p>Select several objects and apply an operation, or select one and wrap
it, then drag more objects in via the tree.</p>
''')}

{_section("5. The object tree", f'''
<p>The <b>Objects</b> tab is the model. Right-click a node for
<b>Hide/Show</b>, <b>Apply operation</b>, <b>Group / Ungroup</b>,
<b>Rename</b>, <b>Set Colour</b>, <b>Duplicate</b> and <b>Delete</b>.</p>
<ul>
<li><b>Drag &amp; drop</b> reparents and reorders nodes.</li>
<li>{_kbd("Ctrl+X / Ctrl+C / Ctrl+V")} cut, copy and paste subtrees &mdash;
even between two running copies of the app.</li>
<li>{_kbd("Ctrl+&uarr; / Ctrl+&darr;")} reorder within the parent; the
arrow keys walk the tree.</li>
<li>Hidden objects stay in the program (emitted with OpenSCAD's
<code>*</code> modifier) so visibility round-trips.</li>
</ul>
<p>Control-flow nodes &mdash; <b>for</b>, <b>while</b>, <b>if/else</b> and
<b>assign</b> &mdash; let a model repeat and branch; numeric fields accept
expressions like <code>i * 10</code>, so loop variables work everywhere.</p>
''')}

{_section("6. Assembling parts", '''
<p>The 2D view doubles as an <b>assembly view</b>. Pick a plane &mdash;
<b>Top (XY)</b>, <b>Front (XZ)</b> or <b>Side (YZ)</b> &mdash; and every
top-level 3D part appears as a draggable projected outline. Drop a part
where you want it and KherveCAD commits the move into a translate node
(<i>Position (&hellip;)</i>).</p>
''')}

{_section("7. The Part Library", '''
<p><b>Insert &rarr; Part Library</b> opens a non-modal catalogue of
parametric parts &mdash; so it stays open while you edit. It includes
vacuum hardware (CF and KF flanges, blanks, nipples, tees, crosses,
turbo-pump shells, gate and right-angle valves) and fasteners (M3&ndash;M20
hex bolts, socket screws and nuts with real helical ISO threads). Every
part is an ordinary node subtree you can edit further.</p>
''')}

{_section("8. Rendering &amp; the OpenSCAD engine", f'''
<p>Any change re-tessellates instantly with the <b>built-in preview</b>.
If the <b>OpenSCAD binary</b> is found (on PATH, a common install dir, or
via <b>Edit &rarr; Locate OpenSCAD</b>), an exact render replaces the
preview a moment later &mdash; with proper booleans &mdash; and STL export
uses it too.</p>
<ul>
<li>{_kbd("F5")} forces a render; <b>Fit 3D</b> reframes the preview.</li>
<li><b>View &rarr; 3D Render Style</b> switches between shaded, brushed
metal, matte, wireframe and x-ray.</li>
<li>Broken nodes turn <b>red</b> in the tree (hover for the reason) and
their lines are tinted red in the Code tab.</li>
</ul>
''')}

{_section("9. KherveAI &mdash; the chat assistant", '''
<p>The <b>KherveAI</b> box (toolbar robot button) chats with Claude,
Mistral or Ollama Cloud. It knows your model and can reply with
<code>scad</code> blocks that are applied straight into the tree. Put your
API key in the settings or an environment variable; slash commands cover
common actions.</p>
''')}

{_section("10. Any AI assistant &mdash; the MCP server", '''
<p>The built-in chat is not the only assistant that can build here.
<b>AI &rsaquo; Connect to Claude (Simple)&hellip;</b> opens KherveCAD to any program on
your machine that speaks the <b>Model Context Protocol</b> &mdash;
<b>Claude Desktop, Claude Code, Cursor, Cline, VS Code, LM Studio</b> and
others.</p>
<ol>
<li>Tick <b>Enable MCP server</b> (remembered next time you start).</li>
<li>Choose what connected assistants may do: <b>Read only</b> (inspect
the model and look at the 3D view), <b>Edit</b> (build, assemble and save
over the open file) or <b>Full</b> (also open, save and export files it
chooses itself).</li>
<li>Pick your assistant under <b>Connect a host</b> and press
<b>Connect</b> &mdash; KherveCAD writes the entry into that
application's own settings, so there is no config file to edit by hand.
Restart it afterwards.</li>
</ol>
<p>A connected assistant gets the whole app rather than a chat reply: it
reads and edits the object tree, applies OpenSCAD programs as real
editable nodes, inserts library parts, makes Objects and mates them into
assemblies, and <b>looks at the 3D view</b> from any angle to check its
own work. Each call is a single undo step, so <b>Ctrl+Z</b> takes your
model back exactly as it does for your own edits. The connection is local
only (127.0.0.1), needs a token that changes every session, and is off
until you tick the box.</p>
''')}

{_section("11. Files, undo &amp; import/export", f'''
<ul>
<li>Documents save as <b>.kcad</b> &mdash; plain JSON that round-trips
every node, parameter, colour and visibility flag.</li>
<li><b>Export</b> to <b>.scad</b> (OpenSCAD) or <b>.stl</b>; <b>import</b>
a <b>.scad</b> file back in (the export &rarr; import round-trip is
lossless), or a mesh (<b>.stl / .obj / .off / .3mf</b>) &mdash; drag any
of these onto the window or use File &rsaquo; Open.</li>
<li><b>Undo / Redo</b> ({_kbd("Ctrl+Z")} / {_kbd("Ctrl+Shift+Z")}) covers
every edit as whole-document snapshots, so drags and spinbox scrubs stay a
single step.</li>
</ul>
''')}

<hr>
<p style='color:gray'>KherveCAD by Gwilherm Kerherve &mdash; Imperial
College London. Part of the Kherve family of native scientific apps.</p>
"""


class UserGuideDialog(QDialog):
    """A scrollable, link-enabled window showing the user guide."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — User Guide")
        self.resize(720, 640)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(GUIDE_HTML)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def show_user_guide(parent=None):
    UserGuideDialog(parent).exec_()

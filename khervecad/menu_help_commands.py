"""Hand-written help for the menu commands that are not Library parts
(see menu_help.py). Keys are the item's label, lower-case, without "&",
"…" or a shortcut; each value is (title, what, steps, tip).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

_B = "Opens in its own window; it can stay open while you edit the model."
_CHEM = ("Chemistry Builder",
         "One window for everything atomic: molecules from a name or "
         "SMILES, crystal blocks, surface slabs, CIF files, doping, "
         "molecules adsorbed on a surface and reaction films — with "
         "distances, angles and torsions drawn on the structure.",
         ["Pick a start (compound, crystal, surface or CIF file).",
          "Edit and measure: add, move, bond or delete atoms; click "
          "atoms to read a distance, angle or torsion.",
          "Build into document puts the result in your model, with the "
          "cell box."], "Export… writes XYZ, MOL, SDF, PDB or CIF.")

COMMANDS = {
    # ------------------------------------------------------------ builders
    "house builder": (
        "House Builder",
        "Design a whole house on a floor plan: draw rooms, drop doors, "
        "windows and furniture, pick walls, roof and finishes, then "
        "build it into the model.",
        ["Choose a floor, then add rooms (or start from Template).",
         "Click a room to resize it by its handles; add doors, windows "
         "and furniture from the catalogue.",
         "Set walls, roof style and garden, then press Build.",
         "Build again after editing: it updates the same house."],
        "Rooms with the same name become one open space."),
    "city builder": (
        "City Builder",
        "Lay out a village, town or city on a 2D plan: roads, buildings "
        "of many styles and world cultures, trees, street lights and "
        "park props — optionally on real terrain.",
        ["Press Generate for a layout, or place roads and buildings "
         "with the tools.",
         "Select a piece to change its style, floors, size, walls, roof "
         "and colour; drag or turn it on the plan.",
         "Press Build to put the city in the document."],
        "Import a real map by asking an assistant (import_map)."),
    "human builder": (
        "Human Builder",
        "Build a person from the anatomical base mesh: gender, age, "
        "build, skin, hair, clothes, pose and stance — with live front, "
        "side and back views.",
        ["Pick the body, the hair and the clothes from the lists.",
         "Choose a gesture and a stance.",
         "Insert adds the figure; Update selected rebuilds the one you "
         "picked."], "Random gives a new person every click."),
    "car builder": (
        "Car Builder",
        "Pick one of 40 classic and super cars at its published "
        "dimensions, then set paint, wheels, tyres, finish and size.",
        ["Choose a make and a model.",
         "Set paint, rim style, tyres and calipers.",
         "Insert places the car; Update selected rebuilds it in place."],
        "Sizes include 1:18, 1:43 and full size."),
    "lego builder": (
        "Lego Builder",
        "Build with Lego bricks on a stud grid, level by level: every "
        "piece (bricks, plates, tiles, slopes, arches, Technic…) in "
        "every colour.",
        ["Pick a piece and a colour on the left.",
         "Click the plan to place it; right-click erases; R turns it.",
         "Use ▲▼ to go up a level; green shows where it fits, red "
         "where it does not."],
        "Baseplates up to 96 × 96 studs sit in their own Object."),
    "crystal builder": (
        "Crystal Builder",
        "Build any crystal as a unit cell, supercell or nanoparticle "
        "(sphere, cube, prism, octahedron…) from 120+ structures, with "
        "bonds and coordination polyhedra.",
        ["Pick a crystal (or open a CIF file).",
         "Choose unit cell, supercell or particle and its size.",
         "Build — the live count warns before a model gets too big."],
        "Lengths are in nanometres."),
    "compound builder": (
        "Compound Builder",
        "Build a molecule from a name, formula or SMILES, a whole "
        "balanced reaction, or a protein from a sequence, PDB ID or "
        "AlphaFold.",
        ["Molecule tab: pick a compound or type a SMILES.",
         "Reaction tab: type '2 H2 + O2 -> 2 H2O' — it balances itself.",
         "Protein tab: sequence, PDB ID or file; pick the style."],
        "A bad SMILES or sequence disables Build and says why."),
    "chemistry builder": _CHEM,
    "surface builder": (
        "Surface Builder",
        "A slab of any crystal cut along any (hkl) plane — Si(111), "
        "quartz (0001), rutile (110) — bulk-terminated, with the cell "
        "and layer count you choose.",
        ["Pick the crystal and the Miller indices.",
         "Set the cell size and number of layers.",
         "Build puts the slab in the document."], None),
    "chamber designer": (
        "Chamber Designer",
        "Design a UHV chamber: pick a body, wall and mu-metal liner, "
        "then aim ports at focal points and fit each with a flange and "
        "an accessory, on a bench or frame.",
        ["Choose the body and its orientation.",
         "Double-click the map to add a port; drag to aim it; pick its "
         "flange, length and accessory.",
         "The check reports collisions and wrong flange families."], None),
    "convert selection to lego": (
        "Convert selection to Lego",
        "Turns the selected part into a Lego model: it is scaled to N "
        "studs across, coloured from the palette and packed with real "
        "bricks.",
        ["Select a part.", "Choose the studs across, bricks or plates "
         "and colours.", "The result is a new Object beside the source."],
        "The source is never touched."),
    "fuse lego into one solid": (
        "Fuse Lego into one solid",
        "Merges a brick build into a single solid, one box set per "
        "colour — good for printing it as one piece.",
        ["Select the Lego Object.", "Click the command.",
         "A fused copy appears beside it."], None),
    "village": ("Random village",
                "Replaces the city with a new small village layout.",
                ["Click it — each click gives a different layout."],
                "Open City Builder to edit what you got."),
    "town": ("Random town",
             "Replaces the city with a new town layout.",
             ["Click it — each click gives a different layout."], None),
    "city": ("Random city",
             "Replaces the city with a new large layout with towers.",
             ["Click it — each click gives a different layout."], None),
    # ----------------------------------------------------------- library
    "part library (customise)": (
        "Part Library",
        "Browse every part, pick its size, colour and options, and "
        "insert it. The window stays open while you work.",
        ["Choose a category and a part.", "Set its size and options.",
         "Click Insert — it arrives as one Object."], "Ctrl+L."),
    "openscad libraries (bosl2, mcad...)": (
        "OpenSCAD libraries",
        "See which OpenSCAD libraries are installed (BOSL2, MCAD, "
        "NopSCADlib, dotSCAD…), install more with one click, and insert "
        "the include line.",
        ["Click a library to install it.",
         "Use Insert include line to add it to your program."], None),
    "save selection to my library": (
        "Save Selection to My Library",
        "Keeps the selected Object in your own library, with a title, "
        "description and area, so you can reuse it in any document.",
        ["Select an Object.", "Give it a title and a description.",
         "Find it later under Library ▸ My Library."], None),
    "manage my library": (
        "Manage My Library",
        "Rename, describe, move or delete saved parts, make sections "
        "and import .kcad files.", [], "Deleted parts go to the trash."),
    "open my library folder": (
        "Open My Library folder",
        "Shows the folder on disk where your saved parts live.", [], None),
    "save new objects automatically": (
        "Save new objects automatically",
        "When on, every named Object you make is saved to My Library a "
        "few seconds after the last change.", [],
        "Generic names like 'Object 2' are skipped."),
    "to be continued": ("", "", [], None),
    # -------------------------------------------------------------- file
    "new": ("New", "Starts an empty document.",
            ["Click New (Ctrl+N). You are asked to save changes first."],
            None),
    "new window": ("New window", "Opens another KherveCAD window with "
                   "an empty document, beside this one.", [], None),
    "open": ("Open", "Opens a .kcad document, or imports a .scad program, "
             "a mesh (STL, OBJ, OFF, 3MF, GLB), a STEP/IGES file or a "
             "CIF crystal.", ["Click Open (Ctrl+O) and pick a file."],
             "You can also drag a file onto the window."),
    "save": ("Save", "Saves the document as a .kcad file; the whole "
             "design is also kept in My Library.", [], "Ctrl+S."),
    "save as": ("Save as", "Saves the document under a new name.", [],
                None),
    "show in file explorer": (
        "Show in file explorer", "Reveals the saved file in Finder or "
        "Explorer.", [], None),
    "clear recent files": ("Clear recent files",
                           "Empties the Open Recent list.", [], None),
    "import openscad": (
        "Import OpenSCAD", "Reads a .scad program into real editable "
        "nodes — modules, loops, variables and library calls included.",
        ["Pick a .scad file."],
        "Code the importer cannot model is kept as raw OpenSCAD."),
    "import mesh (stl/obj/off/3mf)": (
        "Import mesh", "Brings in a triangle mesh as one part.",
        ["Pick the file.",
         "If it is the wrong size, right-click it ▸ Imported mesh to "
         "fix the units."], None),
    "import cad file (step/iges/rhino)": (
        "Import CAD file", "Opens STEP, IGES, BREP or Rhino .3dm files; "
        "an assembly arrives as its named, coloured parts.",
        ["Pick the file and the smoothness."],
        "Needs the OpenCascade add-on; the message names the pip "
        "command if it is missing."),
    "import 2d drawing (svg/dxf)": (
        "Import 2D drawing", "Reads an SVG or DXF outline and extrudes "
        "it 3 mm in a new Object.", ["Pick the file."], None),
    "import height map (surface)": (
        "Import height map", "Turns a picture or .dat grid into a "
        "terrain-like solid: brighter = higher.", ["Pick the file."],
        None),
    "import animated character (glb)": (
        "Import animated character",
        "Loads a rigged GLB character as a body you can dress with "
        "parts, pose and send to a game.", ["Pick the .glb file."], None),
    "export openscad": ("Export OpenSCAD",
                        "Writes the program shown in the Code tab as a "
                        "standalone .scad file.", [], None),
    "export stl": ("Export STL",
                   "Writes the exact OpenSCAD render as an STL for "
                   "printing or other software.",
                   ["Pick a file. If your units are not millimetres you "
                    "are asked whether to scale."],
                   "Needs OpenSCAD for booleans to be cut exactly."),
    "export for other cad (step/iges/rhino)": (
        "Export for other CAD",
        "Writes STEP, IGES, BREP or Rhino files with true surfaces "
        "where the shape allows.", ["Choose the format by file type."],
        "One named, coloured product per top-level part."),
    "export animated character (glb)": (
        "Export animated character",
        "Writes the dressed, posed character as an animated GLB.", [],
        None),
    "pose character": ("Pose character", "Poses an imported character "
                       "from one of its animation clips.",
                       ["Pick a clip and a time."], None),
    "export png": ("Export PNG", "Saves pictures of the 3D view — the "
                   "current camera or all standard views — at up to 4K, "
                   "optionally transparent.", [], None),
    "export turntable movie": (
        "Export turntable movie", "Records an MP4 or GIF: a turntable, "
        "a light sweep, a tumble — and moving parts if you have "
        "sliders.", ["Choose the motion, length and size."],
        "Needs ffmpeg."),
    "render photo (blender)": (
        "Render photo (Blender)", "A photo-real render through Blender "
        "Cycles with materials and lighting.", ["Choose size and "
        "quality, then Render."], "Needs Blender installed."),
    "blueprint (2d drawing)": (
        "Blueprint", "The 2D engineering drawing: projected views, "
        "sections, dimensions, notes, tolerances, parts list and title "
        "block; exports PDF, DXF, SVG, PNG.", [], "Ctrl+Shift+D."),
    "bill of materials": (
        "Bill of materials", "Every part with quantity, material, mass "
        "and cost; export to CSV, Excel, HTML or JSON, or place it on "
        "the blueprint.", [], "Ctrl+Alt+B."),
    "make 2d drawing of this view": (
        "Make 2D drawing of this view", "Turns the current 3D camera "
        "into a flat drawing you can export.", [], None),
    "publish to printables": (
        "Publish to Printables", "Prepares a complete upload folder: "
        "STL/3MF, pictures, description and form answers, then opens "
        "Printables.", ["Check the title and description."],
        "Printables has no upload API: you press the last button."),
    "send to planetcraft": (
        "Send to PlanetCraft", "Sends the model or the selection as a "
        "walking creature into the PlanetCraft game.",
        ["Name it and choose person, animal or monster."], None),
    "p&&&id (process diagram)": (
        "P&ID", "Draw a piping and instrumentation diagram with ISO "
        "10628 / ISA symbols: place equipment, route process and signal "
        "lines, tag and number them, with schedules and exports.",
        ["Pick a symbol from the palette and click to place it.",
         "Connect port to port; lines route themselves.",
         "Open the schedules for the equipment, valve, instrument and "
         "line lists."], "Ctrl+Alt+I."),
    "exit": ("Exit", "Quits KherveCAD.", [], None),
    # -------------------------------------------------------------- edit
    "undo": ("Undo", "Takes back the last change.", [], "Ctrl+Z."),
    "redo": ("Redo", "Brings back what Undo took away.", [], "Ctrl+Y."),
    "delete": ("Delete", "Removes the selected objects.", [],
               "Delete key."),
    "duplicate": ("Duplicate", "Makes a copy of the selection beside "
                  "it.", [], "Ctrl+D."),
    "group": ("Group", "Wraps the selection in a group that moves "
              "together.", [], "Ctrl+G."),
    "ungroup": ("Ungroup", "Dissolves a group, keeping its contents.",
                [], None),
    "options": (
        "Options", "Every preference in one window, like SolidWorks' "
        "Tools ▸ Options: language, theme and interface style (System "
        "Options); units, scale, common segments and how many decimals "
        "dimensions show (Document Properties).", [],
        "Ctrl+, opens it."),
    "document units": (
        "Document units", "What one model unit means: nm, µm, mm, cm, "
        "m or in. A label only — nothing is rescaled.", [],
        "Readouts, mass and print estimates follow it."),
    "document scale (1 : n)": (
        "Document scale", "Says how much smaller than life the model "
        "is (a planet at 1 : 212 600 000), so the scale bar reads "
        "true.", ["Type 1:250000000 or 25:1."], None),
    "locate openscad": ("Locate OpenSCAD", "Points KherveCAD at your "
                        "OpenSCAD program for exact renders.", [], None),
    "new object": ("New object", "Creates an empty Object (a reusable "
                   "part definition) and opens it in the Object tab.",
                   [], None),
    "english": ("English", "Switches the interface to English.", [], None),
    "中文": ("中文", "切换到中文界面 (Chinese).", [], None),
    "français": ("Français", "Passe l'interface en français.", [], None),
    "español": ("Español", "Cambia la interfaz a español.", [], None),
    "日本語": ("日本語", "インターフェースを日本語に切り替えます。", [], None),
    "हिन्दी": ("हिन्दी", "इंटरफ़ेस हिन्दी में बदलें।", [], None),
    # -------------------------------------------------------------- view
    "customizer (sliders)": (
        "Customizer", "A panel of sliders and drop-downs for the "
        "document's annotated variables, grouped by tab. Press ▶ on a "
        "slider to animate it.", [], None),
    "animate ($t)": (
        "Animate", "Plays OpenSCAD's $t animation: scrub, play, set the "
        "frame rate and export frames.", [], None),
    "clear dimensions": ("Clear dimensions", "Removes the measurements "
                         "drawn on the sketch.", [], None),
    "add reference image": (
        "Add reference image", "Places a picture on an axis plane to "
        "trace or compare against, with opacity and size.",
        ["Pick the image, then set the plane and width."],
        "Compare to Reference overlays it on the model."),
    "clear reference images": ("Clear reference images",
                               "Removes every reference picture.", [],
                               None),
    "zoom in": ("Zoom in", "Magnifies the 2D sketch.", [], "Ctrl++."),
    "zoom out": ("Zoom out", "Shrinks the 2D sketch.", [], "Ctrl+-."),
    "reset 2d zoom": ("Reset 2D zoom", "Back to 100 % in the sketch.",
                      [], None),
    "fit sketch": ("Fit sketch", "Zooms the 2D view to show everything.",
                   [], "Ctrl+Shift+F."),
    "zoom to selection": ("Zoom to selection", "Frames the selected "
                          "part in the 2D view.", [], None),
    "fit 3d view": ("Fit 3D view", "Frames the whole model in the 3D "
                    "view.", [], "Ctrl+F."),
    "gumball (move / turn handles)": (
        "Gumball", "Arrows and rings on the selected part: drag an "
        "arrow to move it, a ring to turn it.",
        ["Select a part and switch Gumball on.",
         "Drag a handle; Ctrl snaps to the grid or 15°."], None),
    "isometric": ("Isometric view", "The standard three-quarter view.",
                  [], None),
    "top": ("Top view", "Looks straight down.", [], None),
    "bottom": ("Bottom view", "Looks straight up.", [], None),
    "front": ("Front view", "Looks from the front (-Y).", [], None),
    "back": ("Back view", "Looks from the back (+Y).", [], None),
    "right": ("Right view", "Looks from the right (+X).", [], None),
    "left": ("Left view", "Looks from the left (-X).", [], None),
    "perspective": ("Perspective", "Distant things look smaller, like "
                    "a camera.", [], None),
    "orthographic": ("Orthographic", "No perspective: parallel lines "
                     "stay parallel, good for measuring.", [], None),
    "shaded": ("Shaded", "Plain lit surfaces.", [], None),
    "matte": ("Matte", "Soft, non-shiny surfaces.", [], None),
    "clay": ("Clay", "A uniform clay look that shows form, not colour.",
             [], None),
    "toon": ("Toon", "Flat cartoon shading with outlines.", [], None),
    "brushed metal": ("Brushed metal", "Shiny metal with highlights.",
                      [], None),
    "gold": ("Gold", "A gold finish for the whole model.", [], None),
    "copper": ("Copper", "A copper finish for the whole model.", [], None),
    "wireframe": ("Wireframe", "Only the edges of the triangles.", [],
                  None),
    "x-ray": ("X-ray", "See-through, to look inside.", [], None),
    "theme": ("Theme", "Follows the colour theme of the window.", [],
              None),
    "studio": ("Studio background", "A neutral photo-studio backdrop.",
               [], None),
    "light": ("Light", "A light theme / background.", [], None),
    "slate": ("Slate", "A blue-grey theme / background.", [], None),
    "dark": ("Dark", "A dark theme / background.", [], None),
    "blueprint": ("Blueprint", "Classic blueprint-blue background.", [],
                  None),
    "ocean": ("Ocean", "A blue theme.", [], None),
    "forest": ("Forest", "A green theme.", [], None),
    "sand": ("Sand", "A warm, sandy theme.", [], None),
    "graphite": ("Graphite", "A dark grey theme.", [], None),
    "high contrast": ("High contrast", "A theme with strong contrast "
                      "for easier reading.", [], None),
    "outwards (radial)": ("Explode outwards", "Each part moves away "
                          "from the assembly's centre.", [], None),
    "along x": ("Explode along X", "Parts separate along X only.", [],
                None),
    "along y": ("Explode along Y", "Parts separate along Y only.", [],
                None),
    "along z": ("Explode along Z", "Parts separate along Z only.", [],
                None),
    "across x (side to side)": ("Cut across X", "Slices the view with a "
                                "plane across X.", [], None),
    "across y (front to back)": ("Cut across Y", "Slices the view with "
                                 "a plane across Y.", [], None),
    "across z (top to bottom)": ("Cut across Z", "Slices the view with "
                                 "a horizontal plane.", [], None),
    "move the cut up": ("Move the cut up", "Slides the cut plane 2 % "
                        "further.", [], "Ctrl+Alt+Up."),
    "move the cut down": ("Move the cut down", "Slides the cut plane "
                          "2 % back.", [], "Ctrl+Alt+Down."),
    "keep the other half": ("Keep the other half", "Swaps which side of "
                            "the cut stays visible.", [], None),
    "build a house to cut it by storey": (
        "Cut at a storey", "Once a house is built with the House "
        "Builder, this menu lists its floors so you can cut exactly at "
        "one.", [], None),
    # ----------------------------------------------------------- analyse
    # ribbon buttons that had no card (2026-10-20, the user: every icon
    # needs its detail help when hovered)
    "exploded view": (
        "Exploded view", "Pulls the parts of an assembly apart so you "
        "can see how they fit; the tree is not changed.",
        ["Click to switch it on or off.",
         "The arrow picks the distance and the direction (outwards, X, "
         "Y or Z)."], "Select a sub-assembly to explode only that."),
    "code & files": (
        "Code & files", "Adds things that are not shapes: a variable, an "
        "echo or assert, an STL file, a block of raw OpenSCAD code, or a "
        "sheet-metal part.", ["Click and choose from the list."], None),
    "heat map": (
        "Heat map", "Paints the part by a measurement: wall thickness, "
        "overhangs, draft angle, curvature or zebra stripes.",
        ["Click and choose the map.", "Choose Off to remove it."],
        "Red is where the part needs attention."),
    "show dimensions": (
        "Show dimensions", "Shows the sizes of every shape in the 2D "
        "view: a rectangle's width and height, a circle's diameter, a "
        "line's length, each side of a polygon, a part's overall sizes.",
        ["Click to switch it on or off (also on the 2D view's own bar)."],
        None),
    "connect to claude (simple)": (
        "Connect to Claude", "Lets an AI assistant (Claude Desktop, Claude "
        "Code, Cursor…) drive KherveCAD directly: build, edit, render and "
        "check models.",
        ["Click, switch the connection on, then connect your assistant "
         "in one click."], "Only this computer can connect."),
    "chatbox (requires api key)": (
        "ChatBox", "A chat panel on the right: describe a part and the "
        "assistant writes the OpenSCAD program for it.",
        ["Click to open it.", "Add your API key the first time."], None),
    "mesh from photo": (
        "Mesh from photo", "Turns one picture into a 3D surface with an "
        "image-to-3D service or a local model, and imports it.",
        ["Choose the picture and the generator.",
         "Give its key or command, then Generate."],
        "The far side is guessed: sculpt it afterwards."),
    "language": (
        "Language", "The language of the menus, buttons and User Guide.",
        ["Click and choose a language."], None),
    "import image stack (tiff)": (
        "Import image stack", "Turns a stack of TIFF images (microscope, "
        "CT) into a 3D solid, choosing the threshold on a slice viewer.",
        ["Choose the .tif file or folder of slices.",
         "Set the threshold, voxel size and smoothing, then Build."],
        None),
    "compare to reference image (overlay)": (
        "Compare to reference image", "Draws your reference pictures "
        "over the model, half see-through, so you can see where the "
        "outline leaves the photo.",
        ["Add a reference image first (Insert ▸ Add Reference Image).",
         "Click to switch the overlay on or off."], None),
    "common segments ($fn)": (
        "Common segments ($fn)", "One segment count for every round "
        "object (cylinders, spheres, revolves) — higher is smoother and "
        "slower. 0 lets each object keep its own; 8 or fewer sides keep "
        "intended polygons such as hex heads.",
        ["Type the number of segments (45 is the default)."], None),
    "mass properties": ("Mass properties", "Volume, surface area, "
                        "centre of mass, bounding box and weight for the "
                        "selection or the whole model.", [], None),
    "check for 3d printing": (
        "Check for 3D printing", "Tests the part for printing: "
        "watertight, overhangs, thin walls, footprint — each pass, "
        "warn or fail, with the faulting faces tinted.", [], None),
    "check interference": ("Check interference", "Finds parts that "
                           "overlap, contain or sit inside each "
                           "other.", [], None),
    "check sharp edges": (
        "Check sharp edges", "Finds the edges whose faces meet at a "
        "sharp angle, tints them on the model and can fillet them or "
        "note \"break sharp edges\" on the Blueprint.",
        ["Select a part (or nothing for every part).",
         "Choose the angle, then Fillet these or Note on drawing."], None),
    "check fits & tolerances": (
        "Check fits & tolerances", "Measures the gap between touching "
        "or mated parts, names the ISO fit of a pin in a bore, and adds "
        "up the Blueprint's toleranced dimensions (worst case and RSS).",
        ["Select two or more parts (or none for all).",
         "Read the gaps and fits; set limits for the stack-up."], None),
    "check welds": (
        "Check welds", "Finds where parts touch, reads the joint (lap, "
        "T, corner, butt, fillet) and advises the process (TIG, MIG...), "
        "filler and weld size — and judges the welds you recorded.",
        ["Select the welded parts (or none for all).",
         "Record the advised welds, or place the list on the "
         "Blueprint."], None),
    "off": ("Heat map off", "Removes the colour overlay.", [], None),
    "wall thickness": ("Wall thickness map", "Paints the part red where "
                       "walls are thinner than your minimum.", [], None),
    "overhangs": ("Overhang map", "Paints faces that overhang more than "
                  "the limit.", [], None),
    "draft angle (moulding)": ("Draft angle map", "Shows which faces "
                               "have enough draft to release from a "
                               "mould.", [], None),
    "curvature": ("Curvature map", "Colours the surface by how much it "
                  "curves.", [], None),
    "zebra stripes (smoothness)": ("Zebra stripes", "Reflection "
                                   "stripes that reveal kinks in a "
                                   "surface.", [], None),
    # --------------------------------------------------------------- git
    "commit": ("Commit", "Saves a snapshot of the document's folder in "
               "Git.", [], "Ctrl+K."),
    "push": ("Push", "Sends your commits to the remote repository.", [],
             None),
    "pull": ("Pull", "Fetches changes from the remote repository.", [],
             None),
    "connect to github / gitlab": (
        "Connect to GitHub / GitLab", "Links this document's folder to "
        "a remote repository.", [], None),
    # -------------------------------------------------------------- help
    "user guide": ("User guide", "The full manual with search and "
                   "screenshots.", [], "F1."),
    "check for updates": ("Check for updates", "Looks for a newer "
                          "KherveCAD and installs it.", [], None),
    "about": ("About", "Version and credits.", [], None),
    "show help while hovering menus": (
        "Show help while hovering menus", "Turns this help card on or "
        "off.", [], None),
    "part library": ("Part Library", "Browse and insert parts.", [],
                     "Ctrl+L."),
}
COMMANDS.pop("to be continued", None)

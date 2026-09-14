# Using KherveCAD from any AI assistant (MCP)

KherveCAD ships an [MCP](https://modelcontextprotocol.io) server, so
assistants other than the built-in chat — Claude Desktop, Claude Code,
Cursor, Zed, Continue, or anything else that speaks the Model Context
Protocol — can build in an open document directly.

The built-in chat replies with an OpenSCAD program you then apply. An
MCP client gets the **whole application** instead: 46 tools over the
object tree, the code, the part library, assemblies, the document —
and a **picture of the 3D preview**.

- **Understand it** — `list_node_types` is the vocabulary: every node
  type, its parameters and their ranges, so a client that has never
  seen KherveCAD looks names up instead of guessing.
  `get_document_info` reports the bounding box in mm, the validation
  errors, and whether the OpenSCAD engine was found; `list_tree` and
  `get_node` walk the model; `get_code` shows the generated program,
  for the whole document or for one Object standalone.
- **See it** — `render_view` returns a PNG of the 3D preview as a real
  MCP image block, from any of the seven camera presets. A part that
  is wrong is obvious in the picture and invisible in the tree, and
  checking a second angle costs one call.
- **Build it, two ways that compose** — node by node (`add_node`,
  `set_params`, `wrap_nodes`, `move_node`, `duplicate_node`,
  `delete_nodes`, `ungroup_node`, `set_color`, `round_edges`), or
  `apply_code`, which **parses an OpenSCAD program into real nodes**.
  Not pasted text: the result is an ordinary editable tree, which is
  why an assistant can write fifty lines of OpenSCAD and the user can
  still drag one corner of it afterwards.
- **Parametric, not hard-coded** — any numeric parameter accepts an
  expression string (`"wall * 2"`, `"i * 10"`, `"cos(a) * r"`). That is
  how a loop variable or a document variable reaches a parameter, and
  it is what makes a model adjustable after the assistant has gone.
- **Parts and assemblies** — `make_object` promotes nodes into a part
  definition that compiles to its own OpenSCAD module; `add_instance`
  places another copy of it with its own placement and colour;
  `attach_parts` mates one part to another anchor-to-anchor, live, so
  moving the parent moves the child; `kind` concentric (slides along
  the axis) or angle (a hinge), `align` same (flush), `ratio` (a gear
  mate) and `min_offset`/`max_offset` (a limit) cover the other common
  mates. `list_anchors` gives the names —
  every part has automatic bounding-box anchors plus any the user
  picked. `make_master` / `add_linked_copy` are the other kind of
  reuse. `insert_part` reaches the parametric library: CF/KF vacuum
  components, ISO-threaded fasteners, chemistry glassware, furniture.
- **Documents** — `set_render_options`, `load_example`,
  `new_document`, `open_document` (.kcad, .scad, or a mesh),
  `save_document` and `export_document` (.scad, .stl, .3mf, or a
  .png of the 3D view: `view` is `current` — the user's camera — one
  of the standard views, or `all`, one numbered file per view with
  the front-right isometric first; optional `width`, `height`,
  `transparent`).
- **Units** — a document has a unit (`get_document_info` → `unit`:
  nm, um, mm, cm, m or in; `set_render_options unit` changes it). It
  is a label, never a rescale: every coordinate and size in every tool
  is in that unit, so a 100 nm particle is written `100` in a
  nanometre document. Keys ending `_mm`, `_mm2`, `_mm3` are always
  true millimetres. Mass is computed at true size; cost and print time
  only for mm, cm and inch documents. An STL/3MF of another unit is
  written 1:1 (a slicer reads 1 unit as 1 mm) unless
  `export_document` gets `scale_to_mm: true`.
- **Sharing** — `publish_to_printables` assembles a Printables upload
  folder from the open model: STL, 3MF, the parametric .scad, the
  .kcad project, preview renders and a description the assistant
  writes. See below — it prepares the upload, it does not perform it.
- **Checking** — `mass_properties` (volume, area, centre of mass, box,
  mass and cost for a material, a rough print time),
  `check_printability` (watertight, overhangs, thin walls, footprint —
  pass / warn / fail with plain messages), `check_interference` (which
  parts overlap, contain each other, or are clear), and `list_edges` /
  `fillet_edges` for rounding chosen edges. All read-only except
  `fillet_edges`.

Each call is **one undo step**, so **Ctrl+Z in KherveCAD reverts a
remote assistant's change** just like your own — and two calls are two
steps, so you can reject the last one on its own.

## How it fits together

There are two doors into the same bridge:

```
 MCP host  ──stdio──▶  khervecad.mcp_server  ──loopback TCP──▶  KherveCAD
(Claude Desktop,       (short-lived process                     (your open
 Cline, VS Code, …)     the host owns)                           document)

 MCP host  ──HTTP POST────────────────────────────────────────▶  KherveCAD
(Open WebUI, n8n, …)   http://127.0.0.1:<port>/mcp              (same tools)
```

Same tools, same access level, same undo behaviour — the HTTP endpoint
is a second skin on the bridge, not a wider one. It binds to 127.0.0.1,
requires the same bearer token, and validates `Origin` so a web page in
your browser cannot drive the model (a local HTTP server needs no CORS
preflight, which is the DNS-rebinding hole the MCP spec warns about).
Copy URL and token from **Or configure by hand: URL only**.

CAD tools have to edit a live object tree and read back what the
viewers are showing, so they run inside the application's GUI thread.
MCP hosts, meanwhile, want to spawn and restart a subprocess of their
own. The stdio server is that subprocess; it holds no state, imports no
Qt, and forwards each call over a loopback socket to the running
application.

Practical consequences:

- **KherveCAD must be running** for tools to work. The host may be
  started first — `initialize` still succeeds, and the connection
  starts working the moment the app comes up. No host restart needed.
- Restarting KherveCAD does not require restarting the host: the stdio
  server reconnects on the next call.
- The tools act on the **document that is open right now**, and new
  geometry lands in the scope the user is working in: inside the
  Object they have open in the Object tab, else at the assembly root.
- Node ids come from `list_tree`. They live as long as the node does,
  but undo and open rebuild the tree from a snapshot — re-read them
  afterwards.

## Characters and organic shapes

Five node types exist for soft, symmetric, posable models — the
things a cube and a `difference()` do not give you:

| Node | What it is | In OpenSCAD |
| --- | --- | --- |
| `capsule` | a rod with round ends between two points | `kcad_capsule(a, b, r)` |
| `ellipsoid` | a sphere with three radii | `kcad_ellipsoid(c, r = [rx, ry, rz])` |
| `rounded_box` | a box with a fillet radius on every edge | `kcad_rounded_box(p, size, r, center)` |
| `loft` | a smooth tube through sections `[x, y, z, w, h]` — limbs, tails, horns | `kcad_loft(sections, sides, smooth, caps)` |
| `blend` | melts its children together with a fillet of the given radius — a head onto a neck onto a body | `kcad_blend(radius, detail, …) { … }` |
| `bend`, `twist`, `taper`, `lattice` | reshape the surface of whatever is inside — model straight, then curve a limb or squash a head | `kcad_bend(axis, toward, angle, detail, …) { … }` … |
| `subdivide` | Loop subdivision: a coarse cage (a polyhedron, a few boxes) becomes a smooth organic form | `kcad_subdivide(levels, …) { … }` |
| `human` | a realistic body — MakeHuman's base mesh with gender, age, build and proportion sliders, at any height in mm — to clothe, pose and sculpt a face on | `kcad_human(gender, age, weight, height, stature, …)` |
| `hair_cap` | a thick curly skin grown over the head's faces (a box, and not the ones looking at the face): thickness, curl height and size, seed | `kcad_hair_cap(thickness, noise, curl, seed, within, clear, clear_angle, …) { … }` |
| `paint` | colours the faces inside that look towards the camera from a picture projected onto an axis plane (placed like a reference image; a second picture on another plane blends in by facing, so a front and a side photo cover a head; `sides: "both"` paints through) — the photo's skin, eyes and lips on the sculpted head; the preview shows it, OpenSCAD keeps one colour per solid | `kcad_paint(image, plane, x, y, width, height) { … }` |
| `sculpt` | brush strokes on whatever is inside — grab, inflate, smooth, flatten, pinch, each with a radius and a falloff, mirrored across a plane if asked: the free-form surface a likeness needs | `kcad_sculpt(strokes, detail, mirror, …) { … }` |
| `symmetry` | its children **plus** their mirror image — edit one half | `kcad_symmetry(n, c) { ... }` |
| `joint` | rotates its children about a pivot, within limits | `kcad_joint(pivot, a, limits) { ... }` |

OpenSCAD's own `polyhedron` (points and faces) is a node as well —
validation names the exact edge that leaves it open or wound the
wrong way, which is otherwise the hardest polyhedron bug to find.

They compile to calls of small `kcad_*` helper modules, defined once at
the top of any program that uses them, so an exported `.scad` is still
plain OpenSCAD — and `apply_code` understands the calls directly, so a
limb is one line instead of a chain of hulls. Joints nest (a hand in a
forearm in an upper arm), which makes the tree the armature:
**`set_pose`** then bends any number of joints by name in one call,
clamped to each joint's limits.

A **blend**, a **deformer** or a **subdivide** is computed by
KherveCAD (signed distance fields and marching tetrahedra; edge
splitting and Loop subdivision) and baked into the program as one
polyhedron, so it cannot sit inside a `for` loop — put the loop
inside it. Deformers work on the preview mesh, so they refuse a
`difference()` inside (it would bake uncut). `get_code` summarises those baked arrays unless you pass
`full: true`; the summary still re-applies, because the importer
rebuilds a blend from its children.

`set_color` also takes a **material** — Metal, Glass, Rubber, Skin,
Gold, Emissive and more — which the 3D view shades per object
(Glass is see-through). OpenSCAD has no materials, so the choice
is kept in the file and survives export and import.

**`probe_surface`** casts a ray at the model and returns the surface
it hits — the world point, the outward normal, the distance and the
part — with every crossing along the ray listed nearest first. That
is how a detail goes *on* a curved surface: probe down onto a lofted
body where the eye should be, then place the sphere at the hit point
plus the normal times its inset. No geometry to derive by hand.

**`mesh_from_photo`** turns one picture into a surface with an
image-to-3D model — Tripo or Meshy with the user's API key, or a
command the user runs locally — and imports it as a mesh part, scaled
to a size and stood on the floor. It is plausible, not exact: the far
side is guessed. So: `set_reference_image` with the same photo,
`render_view overlay_reference`, and `sculpt_stroke` where they
disagree.

**`render_view` with `overlay_reference: true`** is how a likeness is
checked: the reference photo is drawn over the model from square on to
its plane, orthographic, so the outline and the picture line up or do
not. Sculpt where they do not, render again.

**`set_pose`** with a figure's `node_id` and `bones` poses the
human node's own rig — MakeHuman's 163 bones with skin weights: an arm
raised to wave, an elbow bent for a handbag, the head turned. Pose
first, then dress: clothes built round the figure do not follow it.

**`face_landmarks`** and **`fit_face`** make a human figure's face a
particular person's. The first says where the model's eye corners,
nose tip, mouth corners, chin and the rest fall as pixels on each
reference image; look at the photo, say where they really are, and
the second solves the face sliders (102 of MakeHuman's, shipped) so
the landmarks project onto the photo's, then warps the last
millimetres. One photo pins two axes, a front and a side photo pin
three.

**`sculpt_stroke`** is the brush. A blend of primitives is a cartoon
because a face lives in hundreds of small curvatures; this pushes the
surface where they belong. Probe the surface, push (grab / inflate /
smooth / flatten / pinch) with a radius and a strength, render, compare
to the photo, repeat. Strokes stay on the node as parameters, so any of
them can be edited or removed later, and `mirror` sculpts both halves
of a face from one side.

**`sample_surface`** does the same for details that come in numbers:
it scatters N evenly spread points, each with its normal, over a
part's surface — only the faces looking a given way, or inside a box
— so curls of hair go over the top and back of a head, tubercles along
a whale's jaw, rivets down a hull, one sphere per point. The same seed
gives the same points.

**`set_reference_image`** puts a photo or sketch on an axis plane
(Top, Front, Side) at a width in millimetres — the 2D view shows it
on that plane and the 3D view draws it in place behind the model —
so a character can be sculpted to its sheet or a part checked
against its photo. It is saved with the document.

## What the preview is showing

`set_render_options` also switches the looks: `smooth` (curved surfaces
shade as one skin instead of facets; sharp edges stay sharp), `cavity`,
`edges`, `stage` and `opengl`.

`render_view` **waits for the picture to be final** before taking it:
while OpenSCAD is still rendering, the call pumps the app until the
engine is idle (up to `timeout`, 30 s by default) and says so in
`render_complete`. Pass `wait_for_exact: false` for whatever is on
screen this instant.

It can also **look from anywhere without moving the user's view**:
`azimuth`/`elevation`/`distance`/`target`, `target_node` (a close-up
framed on one part), `zoom`, `projection: "Orthographic"` (true
proportions, no perspective shrink), `region` (crop a detail, rendered
at higher resolution so it comes back sharp) and `orientations` (a
labelled contact sheet of several presets in one image). Those render
an offscreen twin of the view; only `orientation`/`fit` on their own
move the user's camera. The result's `camera` reproduces the shot.

What the picture contains is worth knowing precisely:

- The **built-in tessellator** draws immediately, and it only
  *approximates* booleans — a `difference()` shows its first operand
  with the holes uncut.
- When OpenSCAD is installed, each part is then rendered **exactly**
  and swapped in as it lands, so holes really are cut. The 3D view's
  label (returned as `showing`) says which you are looking at, and
  `get_document_info` says whether the engine was found at all.
- The same split reaches `export_document`: an STL goes through
  OpenSCAD when it is installed and through the built-in tessellator
  otherwise. The result says which, and an approximated export is
  flagged loudly — it is not one to send to a printer.

## Publishing to Printables

Printables has **no public upload API**. Prusa has never shipped one,
and the reason given in their own forum is partly to keep automated
uploads out. So `publish_to_printables` does not post anything, and
its result says `"published": false` so an assistant cannot honestly
claim otherwise.

What it does instead is everything up to that point, in one call:

- **Geometry** — `.stl` and `.3mf` through OpenSCAD, exact.
- **Source** — the `.scad` program and the `.kcad` project, so the
  listing ships something editable rather than a frozen mesh. That is
  the point of publishing from a parametric tool.
- **Previews** — stills painted by the 3D view's own renderer, so they
  look like what the user sees: colours, materials, lighting, platform
  and shadow, cavity shading and edge lines, at the screen's
  proportions. The default set is three-quarter: the isometric from
  all four corners (front-right first, so it is the cover),
  three-quarter front, bird's-eye, low angle and underside. The
  square-on Front / Back / Left / Right / Top / Bottom can still be
  asked for by name. With OpenSCAD installed the bundle first waits for
  every part's exact mesh (holes cut); the pictures come from an
  offscreen twin, so the user's view does not move.
- **`description.md`** — the assistant writes the body; the bundle
  appends a credit naming KherveCAD (khervetools.com), OpenSCAD and
  Claude, and never twice. Passing no description falls back to a
  skeleton built from the model's real size and variables.
- **`printables.json`** — title, tags, licence, and what is in the
  folder.

The last step is a person: open the upload page while signed in, drag
the folder in, paste the description. `open_browser` opens that page
and reveals the folder, and is **off unless asked for** — publishing
something in the user's name is theirs to trigger.

File ▸ Publish to Printables… is the same builder behind a dialog, for
when no assistant is connected.

## Turning it on

1. **AI ▸ Connect to Claude (Simple)…**
2. Tick **Let assistants connect to this document**. The setting is
   remembered, so the bridge comes back automatically next launch.
3. Leave the access level on **Full** — the recommended setting (see
   **Access levels** below).
4. Pick your application under **Connect an application** and press
   **Connect**.
5. Restart it, then **mention KherveCAD in the chat**.

KherveCAD writes the entry into the host's own settings, so there is no
config file to edit by hand — it knows its own executable path, which
is the part a hand-edit usually gets wrong. Claude Desktop, Cursor and
Windsurf are edited directly; Claude Code goes through the `claude`
CLI, which owns the shape of `~/.claude.json`.

Every write backs the file up first (`.khervecad-<timestamp>.bak`
beside it), replaces it atomically, and leaves your other servers and
unrelated settings alone. A config file that will not parse is reported
rather than overwritten.

**Zed is the exception.** Its settings file allows comments, which
rewriting would silently discard, so KherveCAD refuses to touch it —
copy the snippet in by hand.

Restart the host afterwards: hosts read their tool list once at
startup, so a newly connected one shows no tools until it reconnects.

## Then say "KherveCAD" in the chat

This is the step with no visible cue, and the one that makes a correct
setup look broken. Claude does not go looking for a CAD document on its
own — the tools are there, but nothing points at them until the
conversation does:

> in KherveCAD, build a 40 mm bracket with two M6 holes

From that first mention it keeps working in the document you have open,
so the rest of the conversation is ordinary — *"make it 5 mm thicker"*,
*"show me the front view"*. If it answers with a code block instead of
building anything, it has not connected: check the box above is ticked
and that the host was restarted.

The dialog also shows a running log of what connected clients have
actually called.

## Access levels

| Level | A connected client can |
| --- | --- |
| **Read only** | Inspect the model, read its OpenSCAD, look at the 3D view, select nodes. No changes. |
| **Edit** | Build and edit objects, apply code, assemble parts, insert library parts — and save over the file already open. |
| **Full** (default, recommended) | Everything, including opening, saving and exporting to paths of its own choosing. |

The line between **Edit** and **Full** is the filesystem. At **Edit** a
client can do anything to the model in the window, and the worst case
is a change you undo. `save_document` with no path is the same act as
Ctrl+S, so it stays there too. Naming a path is different: it reads or
writes a file outside the open document, with your permissions.

**Full is the default**, because the levels below it break the workflow
people came for. An assistant that cannot open the file you are talking
about, or export the part it just built, sends you back to the File menu
between every step — and the trust decision has already been made by the
time a tool runs: the connection is loopback-only, token-authenticated,
off until you turn it on, and connected to one application you chose by
name. **Read only** and **Edit** stay for anyone who wants a narrower
grant — a shared machine, or a client you are still sizing up.

Tools above the current level are withheld from `tools/list` and
refused if called anyway, with an error naming the setting. Hosts cache
the tool list from startup, so *widening* access takes effect on their
next reconnect; *narrowing* it takes effect immediately.

## Which clients work

Any MCP client that runs **on your machine**, whatever model it drives.
That matters more than it sounds: the model is not the constraint, the
client is. Someone using GPT, Mistral or Grok reaches KherveCAD through
Cline, VS Code, LM Studio or any other local client with their own API
key.

Cloud assistants are the exception, and it is a hard one. ChatGPT
connectors, Mistral's custom connectors and Grok's Bring Your Own MCP
all require a **publicly reachable HTTPS URL** and cannot spawn a local
process. KherveCAD drives a live window on your desk, so there is
nothing for them to reach without tunnelling your document to the
internet. That is not supported, on purpose.

### Configuring by hand

The dialog still shows the snippet, for Zed, for a machine you are
setting up remotely, or for a host KherveCAD does not know about.
Paste it into the host's config file (`claude_desktop_config.json` for
Claude Desktop) and restart it:

```json
{
  "mcpServers": {
    "khervecad": {
      "command": "/path/to/python",
      "args": ["-m", "khervecad.mcp_server"],
      "env": {"PYTHONPATH": "/path/to/KherveCAD"}
    }
  }
}
```

`PYTHONPATH` — not `cwd` — is what makes `-m khervecad.mcp_server`
resolve. The host chooses the working directory and is free to ignore a
`cwd` key (Claude Code does), and without an importable checkout the
process exits before it can answer `initialize`, which the host reports
as *Server disconnected*.

An installed (frozen) build serves as its own MCP server, so the entry
is just the executable:

```json
{
  "mcpServers": {
    "khervecad": {
      "command": "C:\\Program Files\\KherveCAD\\KherveCAD.exe",
      "args": ["--mcp-server"]
    }
  }
}
```

`--mcp-server` is checked before any GUI work happens: the process
speaks protocol on stdout and never opens a window.

### Claude Code

```
claude mcp add khervecad -e PYTHONPATH="/path/to/KherveCAD" -- /path/to/python -m khervecad.mcp_server
```

## Security

- The listener binds to **127.0.0.1 only** — nothing on the network
  can reach it.
- Every request must carry a random per-session token, published in an
  endpoint file written user-readable only:
  - Windows: `%LOCALAPPDATA%\KherveCAD\mcp-bridge.json`
  - macOS: `~/Library/Application Support/KherveCAD/mcp-bridge.json`
  - Linux: `$XDG_CONFIG_HOME/KherveCAD/mcp-bridge.json`
- The bridge is **off until you turn it on**, and stops with the
  window (the endpoint file is removed on the way out).

Treat an enabled bridge as giving the connected assistant the same
reach over your model as the built-in chat — and, at **Full**, the same
reach over your files as you have.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| "KherveCAD is not reachable" | The app is not running, or AI ▸ Connect to Claude (Simple) is unticked. Fix and retry — no host restart needed. |
| "Invalid bridge token" | A stale endpoint file from a previous run. Toggle the checkbox off and on. |
| Host shows no tools | The host caches `tools/list` from startup; restart the host once with KherveCAD already running. |
| "Refused: … access is set to …" | The access level in AI ▸ Connect to Claude (Simple) is below what the tool needs. |
| "No node with id N" | Ids are rebuilt by undo and by opening a file. Call `list_tree` again. |
| "That program produced no objects" | `apply_code` refuses a parse that yielded nothing rather than reporting a success that changed nothing. The warnings say which statements were skipped. |
| "cube has no parameter 'widht'" | Parameter names are checked against the registry, so a typo is refused instead of being stored and ignored. `list_node_types` has the real ones. |
| "still running the previous tool call" | An STL export is driving OpenSCAD. One call runs at a time; retry when it finishes. |
| "The user has unsaved changes" | `new_document`, `open_document` and `load_example` will not bin unsaved work. Save first, or pass `discard_unsaved_changes`. |
| "Could not open a local port" | Another process is holding the port. Toggle off and on to pick a fresh one. |

Diagnostics from the stdio server go to **stderr**, which MCP hosts
capture in their own logs; stdout carries protocol only.

"""The Extrude window (2026-10-28, the user, from SolidCraft's: "very
easy, very descriptive"): whenever an extrude's arrow is up — a new
Extruded Boss / Cut, or an extrude selected — a `tool_panel.ToolPanel`
shows what it extrudes and every option the extrude really has:

- Profiles — what is extruded (the regions, the shapes);
- Direction — One side (`height`), Two sides (`height2`), Symmetric
  (`center`);
- End condition — Blind, Through all (`extent`, extent.py);
- Distance / Distance 2;
- Twist (degrees over the height) and Scale (the top's size, a taper);
- Reverse direction (`drag_feature.set_direction`).

Every change is applied at once (one undo step each, the arrow follows);
dragging the arrow updates Distance. OK keeps it, Cancel takes it back
(a new extrude goes) — the drag tool's own ok / cancel.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

ONE, TWO, SYMMETRIC = "one", "two", "symmetric"
DIRECTIONS = [(ONE, "One side"), (TWO, "Two sides"),
              (SYMMETRIC, "Symmetric")]
EXTENTS = [("", "Blind"), ("through_all", "Through all")]


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def direction_of(ext):
    p = ext.params
    if p.get("center"):
        return SYMMETRIC
    if _num(p.get("height2")) > 0:
        return TWO
    return ONE


def is_cut(ext):
    """An extrude cut: inside a difference, not its body."""
    probe, child = ext.parent, ext
    while probe is not None:
        if probe.type == "difference":
            return probe.children and probe.children[0] is not child
        child, probe = probe, probe.parent
    return False


def profiles_text(ext):
    from . import mesh
    kids = [c for c in ext.children]
    regions = [c for c in kids if c.type == "regions"]
    if regions:
        try:
            loops = mesh.collect_outlines(regions[0])
        except Exception:
            loops = []
        picks = len(regions[0].params.get("seeds") or [])
        holes = max(0, len(loops) - 1)
        text = "%d region(s) of the sketch" % max(picks, 1)
        if holes:
            text += " — %d hole(s)" % holes
        return text
    names = [c.name for c in kids]
    return ", ".join(names) if names else "Nothing — draw a 2D shape."


def set_direction(model, ext, which):
    p = ext.params
    if which == SYMMETRIC:
        model.set_param(ext, "height2", 0.0)
        model.set_param(ext, "center", True)
    elif which == TWO:
        model.set_param(ext, "center", False)
        if _num(p.get("height2")) <= 0:
            model.set_param(ext, "height2", max(_num(p.get("height"), 10),
                                                0.01))
    else:
        model.set_param(ext, "center", False)
        model.set_param(ext, "height2", 0.0)


def is_reversed(ext):
    """Going the other way: its own reverse param (a cut's) or the
    mirror the arrow wraps round it."""
    from . import drag_feature
    return bool(ext.params.get("reverse")) or \
        drag_feature.reversed_of(ext) is not None


def set_reversed(model, ext, on):
    from . import drag_feature
    if not on and ext.params.get("reverse"):
        model.set_param(ext, "reverse", False)
    drag_feature.set_direction(model, ext, bool(on))


OPERATIONS = [("join", "Boss (add)"), ("cut", "Cut (remove)")]
#: the Difference an Operation ▸ Cut made, so Boss can undo it
CUT_KEY = "cut_operation"


def operation_of(ext):
    return "cut" if is_cut(ext) else "join"


def _holder(ext):
    """The top of *ext*'s branch inside its part / scope (the sketch
    group holding it)."""
    probe = ext
    while probe.parent is not None and probe.parent.type not in (
            "component", "root") and \
            not probe.parent.params.get(CUT_KEY):
        probe = probe.parent
    return probe


def _bodies_for(holder):
    """What the cut removes from: EVERY sibling before the sketch that
    makes 3D geometry — the whole body, as SolidWorks cuts it (the
    nearest one alone left the clevis's lugs uncut when the ring was the
    feature just before the slot, 2026-10-29); else the first after it."""
    from .view2d import _produces_3d
    parent = holder.parent
    if parent is None:
        return []
    sibs = parent.children
    i = sibs.index(holder)
    before = [n for n in sibs[:i] if n.visible and _produces_3d(n)]
    if before:
        return before
    return [n for n in sibs[i + 1:]
            if n.visible and _produces_3d(n)][:1]


def _body_for(holder):
    """The first of `_bodies_for`, or None."""
    bodies = _bodies_for(holder)
    return bodies[0] if bodies else None


def set_operation(model, ext, op):
    """Boss: the extrude adds (as drawn). Cut: the part before it and
    the sketch's branch go into a Difference — the area is removed, Through
    all by default (the user: a line across the lever, the top cut)."""
    if op == operation_of(ext):
        return True
    holder = _holder(ext)
    if op == "cut":
        bodies = _bodies_for(holder)
        if not bodies:
            return False
        body = bodies[0]
        if len(bodies) > 1:
            # several features make the body: one group, cut as one
            body = model.wrap_nodes(bodies, "union")
            if body is None:
                return False
            model.rename(body, "Body")
        parent = body.parent
        if parent.children.index(body) > parent.children.index(holder):
            model.move_node(holder, parent, parent.children.index(body))
        diff = model.wrap_nodes([body, holder], "difference")
        if diff is None:
            return False
        diff.params[CUT_KEY] = True
        model.rename(diff, "Extruded Cut")
        model.set_param(ext, "extent", "through_all")
        return True
    diff = holder.parent
    if diff is not None and diff.params.get(CUT_KEY):
        model.set_param(ext, "extent", "")
        model.ungroup(diff)
        return True
    return False


#: a main plane's sketch group turn (view2d.SketchScene.SKETCH_TURNS)
PLANE_TURNS = {"Top (XY)": (0.0, 0.0, 0.0), "Front (XZ)": (90.0, 0.0, 0.0),
               "Side (YZ)": (90.0, 0.0, 90.0)}


def _plane_holder(ext):
    """The rotate that puts *ext*'s sketch on its plane — by its TURN,
    not its name (an imported "Body-Rotate" read as Top) — or None."""
    probe = ext.parent
    while probe is not None and probe.type not in ("component", "root"):
        if probe.type == "rotate":
            return probe
        probe = probe.parent
    return None


def plane_of(ext):
    """Front (XZ) / Top (XY) / Side (YZ) the sketch lies in, or ''."""
    rot = _plane_holder(ext)
    if rot is None:
        return "Top (XY)"
    turn = tuple(round(_num(rot.params.get(k)), 3) for k in "xyz")
    for name, t in PLANE_TURNS.items():
        if turn == t:
            return name
    return ""


def plane_text(ext):
    from . import plane_pick
    name = plane_of(ext)
    return plane_pick.name_of(name) if name else "A face / plane of its own"


def set_plane(model, ext, plane):
    """Put the sketch (and so its extrude) on main *plane*."""
    turn = PLANE_TURNS.get(plane)
    if turn is None:
        return False
    rot = _plane_holder(ext)
    if rot is None:
        holder = _holder(ext)
        rot = model.wrap_nodes([holder], "rotate")
        if rot is None:
            return False
    for k, v in zip("xyz", turn):
        model.set_param(rot, k, v)
    model.rename(rot, plane.split()[0] + " sketch")
    return True


def _panel(window):
    return getattr(window, "_extrude_panel", None)


def show(window, tool):
    """The window for the drag tool *tool* (its extrude)."""
    from .tool_panel import ToolPanel
    from . import drag_feature
    ext = tool.target()
    if ext is None or ext.type != "linear_extrude":
        return None
    close(window)
    model = window.model
    view = window.view3d
    # OK / Cancel find the tool when pressed: holding the drag tool (its
    # buttons, its timer) past its window crashed PyQt's clean-up at exit
    import weakref
    ref = weakref.ref(tool)

    def press(name):
        t = ref()
        if t is not None:
            getattr(t, name)()
    panel = ToolPanel(view, "Extruded Cut" if is_cut(ext) else
                      "Extrude", on_ok=lambda: press("ok"),
                      on_cancel=lambda: press("cancel"))
    panel.tool, panel.ext = ref, ext
    panel.busy = False
    panel.hint("Drag the blue arrow in the 3D view, or set the options "
               "here; every change shows at once. OK keeps it.")
    panel.selection("profiles", "Profiles", profiles_text(ext))
    panel.set_active("profiles")

    def pick_plane(_key):
        # the planes in 3D; the one clicked takes the sketch
        from . import plane_pick
        panel.set_active("plane")

        def chosen(plane):
            panel.busy = True
            try:
                set_plane(model, ext, plane)
            finally:
                panel.busy = False
            refresh(window)
            panel.set_active("profiles")
        plane_pick.start(window, on_plane=chosen)
    panel.selection("plane", "Sketch plane", plane_text(ext),
                    on_activate=pick_plane)

    def changed(fn):
        def run(value):
            # the panel's own edit (Reverse wraps the extrude in a mirror
            # and moves the selection): the arrow and this window stay
            panel.busy = True
            try:
                fn(value)
            finally:
                panel.busy = False
            tree = window.builder.active_tree()
            if ext.parent is not None and \
                    tree.selected_nodes() != [ext]:
                panel.busy = True
                try:
                    tree.select_nodes([ext])
                finally:
                    panel.busy = False
            refresh(window)
        return run
    panel.choice("operation", "Operation", OPERATIONS, operation_of(ext),
                 changed(lambda v: set_operation(model, ext, v)))
    panel.choice("direction", "Direction", DIRECTIONS, direction_of(ext),
                 changed(lambda v: set_direction(model, ext, v)))
    panel.choice("extent", "End condition", EXTENTS,
                 ext.params.get("extent") or "",
                 changed(lambda v: model.set_param(ext, "extent", v)))
    panel.number("height", "Distance", _num(ext.params.get("height"), 10),
                 changed(lambda v: model.set_param(ext, "height", v)),
                 minimum=0.01)
    panel.number("height2", "Distance 2",
                 _num(ext.params.get("height2"), 0),
                 changed(lambda v: model.set_param(ext, "height2", v)),
                 minimum=0.0)
    # the extrude's own shaping (the user): a twist turns the profile
    # as it rises, a scale tapers it to the top
    panel.number("twist", "Twist", _num(ext.params.get("twist"), 0),
                 changed(lambda v: model.set_param(ext, "twist", v)),
                 suffix="°", minimum=-100000.0, maximum=100000.0,
                 step=15.0, decimals=1)
    panel.number("scale", "Scale (top)", _num(ext.params.get("scale"), 1),
                 changed(lambda v: model.set_param(ext, "scale", v)),
                 suffix="", minimum=0.0, maximum=10000.0, step=0.1,
                 decimals=3)
    panel.section("Options")
    panel.check("reverse", "Reverse direction", is_reversed(ext),
                changed(lambda v: set_reversed(model, ext, bool(v))))
    panel.finish()

    def follow(node):
        if node is ext:
            refresh(window)
    model.node_changed.connect(follow)
    panel._follow = follow
    window._extrude_panel = panel

    refresh(window)
    panel.open()
    return panel


def refresh(window):
    """The fields show the extrude as it is now (the arrow dragged)."""
    from . import drag_feature
    panel = _panel(window)
    if panel is None:
        return
    ext = panel.ext
    if ext.parent is None:
        return
    d = direction_of(ext)
    panel.set_value("operation", operation_of(ext))
    if "plane" in panel.boxes:
        panel.boxes["plane"].set_text(
            plane_text(ext) + " — click to choose another")
    panel.title.setText("Extruded Cut" if is_cut(ext) else "Extrude")
    panel.set_value("direction", d)
    panel.set_value("extent", ext.params.get("extent") or "")
    panel.set_value("height", _num(ext.params.get("height"), 10))
    panel.set_value("height2", _num(ext.params.get("height2"), 0))
    panel.set_value("reverse", is_reversed(ext))
    panel.set_value("twist", _num(ext.params.get("twist"), 0))
    panel.set_value("scale", _num(ext.params.get("scale"), 1))
    through = (ext.params.get("extent") or "") == "through_all"
    panel.fields["height"].setEnabled(not through)
    panel.show_row("height2", d == TWO)
    panel.adjustSize()
    panel.place()


def close(window, tool=None):
    panel = _panel(window)
    if panel is None or (tool is not None and panel.tool is not None
                         and panel.tool() is not tool):
        return
    window._extrude_panel = None
    try:
        window.model.node_changed.disconnect(panel._follow)
    except (TypeError, RuntimeError):
        pass
    panel.tool = panel.ext = None
    try:
        panel.hide()
        # deleted NOW, not later: a panel waiting for an event loop that
        # never came (a window closed at exit) crashed PyQt's clean-up
        from PyQt5 import sip
        if not sip.isdeleted(panel):
            panel.setParent(None)
            sip.delete(panel)
    except RuntimeError:                       # went with its window
        pass


def busy(window):
    """True while the window applies one of its own changes."""
    panel = _panel(window)
    return panel is not None and getattr(panel, "busy", False)

# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Extruded Boss / Cut start with TOGGLES on top of the 3D view, not a
window (2026-11-13, the user: "I wanted toggles instead of the choice
window ... on the top of the 3D view").

The bar: **Faces** (every flat face numbered F1..), **Sketch regions**
(every sketch's closed areas numbered), **Planes** (Front / Top / Right,
off by default) and **2D | 3D** (2D by default). One click on the model
then decides: a face -> a new sketch on it, a region -> that sketch's
regions are picked (Boss / Cut by regions), a plane -> a new sketch on
it. The sketch opens in the 2D sketch view or in 3D as the toggle says,
and while that sketch is open the same toggle switches it back and forth
between the two (`switch`).
"""

from __future__ import annotations

KEY_WHERE = "sketch/feature_where"


def _settings():
    from PyQt5.QtCore import QSettings
    return QSettings("Kherve", "KherveCAD")


def where() -> str:
    v = str(_settings().value(KEY_WHERE, "2d"))
    return v if v in ("2d", "3d") else "2d"


def state(window):
    st = getattr(window, "_feature_toggles", None)
    if st is None:
        st = window._feature_toggles = dict(faces=True, regions=True,
                                            planes=False, where=where())
    return st


# ------------------------------------------------------------- the bar
try:
    from PyQt5.QtCore import QEvent, QObject, Qt
    from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

    class ToggleBar(QFrame):
        """The toggles, floating at the top centre of *host*."""

        def __init__(self, window, host):
            super().__init__(host)
            from . import language
            tr = language.tr
            self.window = window
            self.host = host
            self.setObjectName("featureToggleBar")
            self.setStyleSheet(
                "#featureToggleBar{background:rgba(255,255,255,235);"
                "border:1px solid #9ab;border-radius:6px;}"
                "QToolButton{padding:3px 9px;border:1px solid transparent;"
                "border-radius:4px;color:#223;}"
                "QToolButton:checked{background:#0078d7;color:white;}"
                "QToolButton:hover{border-color:#0078d7;}"
                "QLabel{color:#334;padding:0 6px;}")
            lay = QHBoxLayout(self)
            lay.setContentsMargins(6, 3, 6, 3)
            lay.setSpacing(3)
            self.title = QLabel("")
            lay.addWidget(self.title)
            self.buttons = {}
            for key, text, tip in (
                    ("faces", tr("Faces"),
                     tr("Number every flat face (F1, F2...) — click one "
                        "to sketch on it")),
                    ("regions", tr("Sketch regions"),
                     tr("Number every sketch's closed areas — click one "
                        "to use that sketch")),
                    ("planes", tr("Planes"),
                     tr("Front, Top and Right planes — click one to "
                        "sketch on it"))):
                b = self._button(text, tip, key)
                lay.addWidget(b)
            self.sep = QLabel("|")
            lay.addWidget(self.sep)
            for key, text, tip in (
                    ("2d", tr("2D"), tr("Sketch in the flat 2D sketch "
                                        "view (switches an open sketch)")),
                    ("3d", tr("3D"), tr("Sketch on the model in the 3D "
                                        "view (switches an open sketch)"))):
                lay.addWidget(self._button(text, tip, key))
            host.installEventFilter(self)
            # what to click, under the bar
            self.hint = QLabel("", host)
            self.hint.setStyleSheet(
                "background:rgba(30,40,60,190);color:white;"
                "border-radius:4px;padding:2px 8px;")
            self.hint.hide()
            self.sync()

        def _button(self, text, tip, key):
            b = QToolButton(self)
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda on, k=key: toggled(self.window, k, on))
            self.buttons[key] = b
            return b

        def sync(self):
            st = state(self.window)
            picking = bool(getattr(self.window, "_feature_pick", None))
            for key in ("faces", "regions", "planes"):
                b = self.buttons[key]
                b.setChecked(bool(st[key]))
                b.setVisible(picking)
            self.buttons["regions"].setEnabled(
                not picking or bool(self.window._feature_pick.get(
                    "regions_ok")))
            self.sep.setVisible(picking)
            self.buttons["2d"].setChecked(st["where"] == "2d")
            self.buttons["3d"].setChecked(st["where"] == "3d")
            label = ""
            if picking:
                label = self.window._feature_pick.get("label", "")
            self.title.setText("<b>%s</b>" % label if label else "Sketch")
            self.adjustSize()
            self.place()

        def place(self):
            self.adjustSize()
            self.move(max(0, (self.host.width() - self.width()) // 2), 6)
            self.raise_()
            picking = bool(getattr(self.window, "_feature_pick", None))
            self.hint.setVisible(picking and self.isVisible() and
                                 bool(self.hint.text()))
            if self.hint.isVisible():
                self.hint.adjustSize()
                self.hint.move(max(0, (self.host.width() -
                                       self.hint.width()) // 2),
                               self.y() + self.height() + 4)
                self.hint.raise_()

        def hideEvent(self, event):
            self.hint.hide()
            super().hideEvent(event)

        def eventFilter(self, obj, event):
            try:
                if obj is self.host and event.type() == QEvent.Resize:
                    self.place()
            except Exception:
                pass
            return False
except ImportError:                                  # pragma: no cover
    ToggleBar = None


def bars(window):
    out = getattr(window, "_feature_bars", None)
    if out is None:
        out = window._feature_bars = {}
    for name in ("view3d", "view2d"):
        if name not in out:
            host = getattr(window, name, None)
            host = host.viewport() if name == "view2d" and host is not None \
                else host
            if host is not None:
                out[name] = ToggleBar(window, host)
                out[name].hide()
    return out


def show_bar(window):
    """The bar over the 3D view, and over the 2D sketch while a Boss /
    Cut sketch is open there."""
    b = bars(window)
    open_sketch = sketch_group(window) is not None
    for name, bar in b.items():
        bar.sync()
        on = name == "view3d" or open_sketch
        bar.setVisible(on)
        bar.place()


def hide_bar(window):
    for bar in (getattr(window, "_feature_bars", None) or {}).values():
        bar.hide()


def refresh(window):
    """After any sketch opens or closes: the bar where it belongs."""
    if getattr(window, "_feature_pick", None) or \
            sketch_group(window) is not None:
        show_bar(window)
    else:
        hide_bar(window)


def sketch_group(window):
    """The Boss / Cut sketch open now (2D or 3D) — or one Sketch Mode
    opened from the bar — else None."""
    from . import cut_feature
    g = getattr(window, "_face_sketch", None)
    tool = getattr(window, "_sketch3d_tool", None)
    if g is None and tool is not None:
        g = getattr(tool, "group", None)
    if g is not None and g.parent is not None and (
            g.params.get(cut_feature.KEY) or
            getattr(g, "_kc_bar_sketch", False)):
        return g
    return None


def toggled(window, key, on):
    st = state(window)
    if key in ("2d", "3d"):
        st["where"] = key
        _settings().setValue(KEY_WHERE, key)
        g = sketch_group(window)
        if g is not None:
            switch(window, g, key)
    else:
        st[key] = bool(on)
        if getattr(window, "_feature_pick", None):
            _show_toggles(window)
            _arm(window)
    for bar in (getattr(window, "_feature_bars", None) or {}).values():
        bar.sync()


# ------------------------------------------------------------ the pick
#: the kinds whose region click picks REGIONS (the others take a sketch)
EXTRUDED = ("extruded_boss", "extruded_cut")
#: Sketch Mode's own kind: a face, a sketch or a plane opens a sketch
#: and nothing more is made (2026-11-13, the user)
SKETCH = "sketch"


def start(window, kind):
    """Every Boss and Cut with nothing to use selected: the bar, the
    numbers, one click."""
    from . import choice_preview, cut_feature, meshedit_ui
    st = state(window)
    st["where"] = "2d"            # every Boss / Cut starts on 2D (the user)
    label = "Sketch Mode" if kind == SKETCH else cut_feature.ALL[kind][0]
    parts = meshedit_ui._parts(window)
    regions_ok = True
    try:
        # a Regions a cancelled extrude left in a sketch hid its shapes
        # from the region finder (the user's Ø32 hole): folded back first
        from . import sketch_regions
        if window._render_scope()[0] is not window.model.root:
            sketch_regions.tidy(window)
        sketches, items = choice_preview.region_items(window)
    except Exception:
        sketches, items = [], []
    if kind not in EXTRUDED and kind != SKETCH:
        # a Revolved / Swept / Lofted Boss or Cut takes a WHOLE sketch no
        # feature uses yet (an extruded one's regions are Extrude's)
        from . import sketch_regions
        free = {ci for ci, sk in enumerate(sketches)
                if not sketch_regions.used(sk)}
        items = [it for it in items if it[0] in free]
    # planes off for a Boss / Cut (the user); on for Sketch Mode, where
    # they were the whole choice — and whenever there is nothing else
    st["planes"] = kind == SKETCH or (not parts and not items)
    window._feature_pick = dict(kind=kind, label=label, parts=parts,
                                sketches=sketches, items=items,
                                regions_ok=regions_ok)
    choice_preview.start(window, parts=parts, items=items)
    view = window.view3d
    if not getattr(window, "_feature_release_hook", False):
        # where a click lands (the pick callback has no position): a
        # click on empty space is a plane, or nothing — not Esc
        def note(pos):
            pk = getattr(window, "_feature_pick", None)
            if pk:
                pk["pos"] = pos
            return False
        view.release_hooks = list(getattr(view, "release_hooks", ())) + \
            [note]
        window._feature_release_hook = True
    _show_toggles(window)
    show_bar(window)
    _arm(window)
    return True


def _show_toggles(window):
    from . import choice_preview, plane_pick
    st = state(window)
    pick = window._feature_pick
    choice_preview.show(window, faces=st["faces"],
                        regions=st["regions"] and pick["regions_ok"],
                        planes=False)
    if st["planes"]:
        if not getattr(window, "_plane_pick", None):
            window._plane_pick = {"half": plane_pick._half(window),
                                  "hover": None, "on_plane": None,
                                  "feature": True}
    elif getattr(window, "_plane_pick", None) and \
            window._plane_pick.get("feature"):
        window._plane_pick = None
    window.view3d.update()


def _banner(window):
    st = state(window)
    pick = window._feature_pick
    what = []
    if st["faces"]:
        what.append("a numbered face")
    if st["regions"] and pick["regions_ok"] and pick["items"]:
        what.append("a sketch region" if pick["kind"] in EXTRUDED
                    else "a sketch")
    if st["planes"]:
        what.append("a plane")
    if not what:
        return "%s: switch on Faces, Sketch regions or Planes above" % \
            pick["label"]
    return "%s: click %s · sketch in %s · Esc cancels" % (
        pick["label"], " or ".join(what), st["where"].upper())


def _groups(window):
    st = state(window)
    pick = window._feature_pick
    groups = []
    if st["regions"] and pick["regions_ok"]:
        groups += [(("region", ci, k), tris)
                   for ci, k, _w, _at, _n, tris in pick["items"]]
    if st["faces"]:
        groups += [(("part", node), tris) for node, tris in pick["parts"]]
    return groups


def _arm(window):
    view = window.view3d
    pick = window._feature_pick
    if not pick:
        return
    groups = _groups(window)
    if view._pick_cb is not None and pick.get("armed"):
        # already waiting: only what it may hit changes
        view._pick_groups = groups
        _say(window)
        view.update()
        return
    pick["armed"] = True

    def labeler(desc, key):
        if key and key[0] == "region":
            n = next((n for ci, k, _w, _a, n, _t in pick["items"]
                      if (ci, k) == key[1:]), "")
            return "Region %s — use this sketch" % n
        if key and key[0] == "part":
            return "%s — sketch on this face" % getattr(key[1], "name", "")
        return ""
    # (the hint goes under the bar and in the status bar: a banner
    # across the top of the view hid behind the bar)
    view.keep_nav_in_pick = True       # the bottom bar stays (the user)
    view.start_pick(lambda desc, key: picked(window, desc, key),
                    groups=groups or [], banner="",
                    labeler=labeler, done=False)
    _say(window)


def _say(window):
    text = _banner(window)
    window.statusBar().showMessage(text, 0)
    for bar in (getattr(window, "_feature_bars", None) or {}).values():
        bar.hint.setText(text)
        bar.place()


def picked(window, desc, key):
    from . import plane_pick
    pick = getattr(window, "_feature_pick", None)
    if not pick:
        return
    pick["armed"] = False
    pps = getattr(window, "_plane_pick", None)
    if pps:
        pps.pop("pos", None)
    pos = pick.pop("pos", None)
    st = state(window)
    if desc is None and pos is None:
        stop(window)                         # Esc / Select: cancelled
        window.statusBar().showMessage("%s cancelled." % pick["label"],
                                       4000)
        return
    plane = plane_pick.hit(window, pos) if (pos is not None and
                                            st["planes"] and pps) else None
    if key and key[0] == "region" and desc is not None:
        _use_region(window, pick, key[1], key[2])
        return
    if key and key[0] == "part" and desc is not None:
        if desc.get("kind") == "face":
            _use_face(window, pick, key[1], desc["pos"], desc["dir"],
                      desc.get("tris") or [])
            return
        if plane is None:
            window.view3d.flash("Click a flat FACE (not an edge).", 3000)
            _arm(window)
            return
    if plane is not None:
        _use_plane(window, pick, plane)
        return
    _arm(window)                             # empty space: still waiting


def stop(window):
    from . import choice_preview
    pick = getattr(window, "_feature_pick", None)
    window._feature_pick = None
    window.view3d.keep_nav_in_pick = False
    if pick:
        window.statusBar().clearMessage()
    pps = getattr(window, "_plane_pick", None)
    if pps and pps.get("feature"):
        window._plane_pick = None
    choice_preview.stop(window)
    view = window.view3d
    if pick and view._pick_cb is not None:
        view._pick_cb = None
        try:
            view._end_pick_mode()
        except Exception:
            pass
    refresh(window)
    view.update()


def _in_3d(window):
    return state(window)["where"] == "3d"


def _use_face(window, pick, node, pos, normal, tris):
    from . import cut_feature, face_sketch
    kind = pick["kind"]
    stop(window)
    in_3d = _in_3d(window)
    if kind == SKETCH:
        group = face_sketch.make(window, node, pos, normal,
                                 open_2d=not in_3d)
        _sketch_opened(window, group, normal, tris, in_3d)
        return
    group = face_sketch.make(window, node, pos, normal, open_2d=not in_3d)
    cut_feature._open(window, kind, group, node, normal, tris, in_3d)
    refresh(window)


def _use_plane(window, pick, plane):
    from . import cut_feature, face_sketch, plane_pick
    kind = pick["kind"]
    parts = pick["parts"]
    stop(window)
    in_3d = _in_3d(window)
    normal = cut_feature.PLANE_NORMALS.get(plane)
    part = cut_feature._crossing(parts, normal) if parts else None
    if kind == SKETCH and not in_3d:
        # a sketch on a main plane, as SolidWorks: the view turns to it
        from . import normal_to
        normal_to.turn_to(window, plane)
        refresh(window)
        return
    group = face_sketch.make(window, part, (0.0, 0.0, 0.0), normal,
                             open_2d=not in_3d)
    window.model.rename(group, "Sketch on " + plane_pick.name_of(plane))
    if kind == SKETCH:
        _sketch_opened(window, group, normal, [], in_3d)
        return
    cut_feature._open(window, kind, group, part, normal, [], in_3d)
    refresh(window)


def _use_region(window, pick, ci, k):
    from PyQt5.QtCore import QTimer
    from . import sketch_regions
    kind = pick["kind"]
    sketch = pick["sketches"][ci]
    if kind == SKETCH:
        _edit_sketch(window, sketch)
        return
    if kind not in EXTRUDED:
        _use_sketch(window, pick, sketch)
        return
    stop(window)
    QTimer.singleShot(0, lambda: sketch_regions.start_3d(
        window, sketch, cut=kind == "extruded_cut", preselect=k))


def _use_sketch(window, pick, sketch):
    """A Revolved / Swept / Lofted Boss or Cut made from the clicked
    sketch, whole."""
    from . import cut_feature, face_sketch, sketch_regions
    kind = pick["kind"]
    label = pick["label"]
    stop(window)
    model = window.model
    made = None
    if kind == "revolved_boss":
        # revolve_feature knows a sketch with no sketch group too
        from . import revolve_feature
        try:
            made = revolve_feature.revolve(
                window, sketch_regions.shapes_of(sketch))
        except Exception:
            made = None
    if made is None and kind in cut_feature.BOSS:
        made = cut_feature.apply(model, sketch, None, kind)
    elif made is None:
        group = face_sketch.group_of(sketch) or sketch
        part = face_sketch.part_of(group) if \
            group.params.get(face_sketch.KEY) else None
        if part is None:
            window.view3d.flash(
                "%s cuts with a sketch on a face or plane of the part — "
                "click a face or a plane instead." % label, 6000)
            start(window, kind)
            return None
        made = cut_feature.apply(model, group, part, kind)
    if made is None:
        window.view3d.flash("%s: nothing made from that sketch." % label,
                            5000)
        return None
    window.builder.active_tree().select_nodes([made])
    window.statusBar().showMessage(
        "%s made from %s — set its numbers in Properties." % (
            label, sketch.name), 6000)
    if made.type in ("linear_extrude", "rotate_extrude"):
        try:
            from . import drag_feature
            drag_feature.start(window, made, quiet=True, created=True)
        except Exception:
            pass
    return made


def _sketch_opened(window, group, normal, tris, in_3d):
    """Sketch Mode's new face / plane sketch is open: in 2D it opened
    itself; in 3D the drawing tool goes on it, the view square on."""
    group._kc_bar_sketch = True         # (the 2D | 3D toggles move it)
    if in_3d:
        _draw_in_3d(window, group, normal, tris)
    refresh(window)


def _draw_in_3d(window, group, normal, tris=()):
    from . import face_sketch, sketch3d, view_anim
    window._chosen_face = list(tris or [])
    view = window.view3d
    yaw, pitch = face_sketch.camera_for(normal)
    view.user_moved = True
    view_anim.glide_3d(view, dict(yaw=yaw, pitch=pitch,
                                  target=list(view.target),
                                  distance=view.distance))
    tool = sketch3d.Sketch3DTool(window, "rect")
    tool.use_group(group)
    view.edit_tool = tool
    tool.begin()
    ribbon = getattr(window, "ribbon", None)
    if ribbon is not None:
        ribbon.show_tab("sketch")


def _edit_sketch(window, sketch):
    """Sketch Mode on a numbered sketch: open it again."""
    from . import face_sketch, normal_to, sketch_regions
    group = face_sketch.group_of(sketch)
    if group is not None:
        from . import cut_feature          # editing, never a feature
        group.params.pop(cut_feature.KEY, None)
        group._kc_bar_sketch = True
        if _in_3d(window):
            _draw_in_3d(window, group, face_sketch._normal_of(group))
        else:
            face_sketch.open_sketch(window, group)
        refresh(window)
        return
    shapes = sketch_regions.shapes_of(sketch)
    normal_to.edit(window, shapes[0] if shapes else None)
    refresh(window)


# ------------------------------------------- 2D <-> 3D while sketching
def switch(window, group, to):
    """The open Boss / Cut sketch moves to the 2D sketch view or to the
    3D view, keeping everything drawn (the user: "switch back and
    forth")."""
    from . import face_outline, face_sketch, sketch3d, sketch_mode
    tool = getattr(window, "_sketch3d_tool", None)
    if to == "2d":
        if tool is None:
            return False
        tool._end()                        # (the sketch stays as it is)
        face_sketch.open_sketch(window, group)
        refresh(window)
        return True
    if getattr(window, "_face_sketch", None) is not group:
        return False
    # out of the 2D sketch WITHOUT closing it (closing a cut's sketch
    # cuts it)
    window._face_sketch = None
    window._face_sketch_info = None
    try:
        face_outline.clear(window)
    except Exception:
        pass
    window._sketching = False
    window._sketch_edit_node = None
    sketch_mode.sync_create(window)
    if sketch_mode.active(window):
        sketch_mode._show(window, False)
    try:
        window.view2d.scene().rebuild()
    except Exception:
        pass
    view = window.view3d
    view.yaw, view.pitch = face_sketch.camera_for(
        face_sketch._normal_of(group))
    view.target = list(face_sketch.to_world(group, 0.0, 0.0))
    view.user_moved = True
    tool = sketch3d.Sketch3DTool(window, "rect")
    tool.use_group(group)
    view.edit_tool = tool
    tool.begin()
    refresh(window)
    view.update()
    return True

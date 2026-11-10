# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Display/Delete Relations (SolidWorks' PropertyManager of that name,
2026-11-10, the user): every relation and dimension of a sketch in one
list — its drawn mark, what it ties (shapes by NAME and the part of each:
"Line 2 (end)", "Rectangle 1 (side 3)") and its value — with Edit value,
Delete, Delete all and Auto constrain. A row picked selects the shapes it
ties, so they light up in both views. The sketch is the one being edited
(Sketch Mode), else the selected shape's or sketch's, else the scope's;
the list follows the model while it is open.

Replaces the plain "Sketch constraints" list of sketch_constrain_ui."""

from . import sketch_constraints as sc

#: what each entity of a shape is called in the list
PARTS = {"p1": "start", "p2": "end", "m": "middle", "c": "centre",
         "a1": "start circle", "a2": "end circle"}
SHOW = (("all", "Relations and dimensions"), ("relations", "Relations"),
        ("dimensions", "Dimensions"))


def entity_text(container, ref):
    """"Line 2 (end)" for ref "1.p2"."""
    try:
        node, name = sc.entity(container, ref)
    except (KeyError, ValueError, IndexError):
        return ref
    if name in PARTS:
        part = PARTS[name]
    elif name[:1] in "ve" and name[1:].isdigit():
        part = ("corner %d" if name[0] == "v" else "side %d") % (
            int(name[1:]) + 1)
    else:
        part = ""                         # the line / circle itself
    return "%s (%s)" % (node.name, part) if part else node.name


def describe(container, row):
    """(relation, entities, value) words of one row."""
    label = sc.KINDS.get(row.get("kind"), (row.get("kind", "?"),))[0]
    ents = ", ".join(entity_text(container, r) for r in row.get("refs", ()))
    value = ""
    if "value" in row:
        from . import dim_more
        try:
            value = dim_more.text(row)
        except Exception:
            value = str(row["value"])
    return label, ents, value


def sketch_of(win):
    """The sketch the window lists."""
    from . import sketch_constrain_ui, sketch_focus
    try:
        focus = sketch_focus.current(win)
    except Exception:
        focus = None
    if focus is not None:
        if focus.group is not None:
            # a face sketch: the container in it that holds relations
            held = [n for n in focus.group.walk() if sc.rows(n)]
            return held[0] if held else focus.group
        if focus.container is not None:
            return focus.container
    return sketch_constrain_ui.container_for(win)


def _icon(kind, dimension):
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QIcon, QPainter, QPixmap
    from . import icons, relation_marks
    if dimension:
        return icons.icon("mdi.ruler")
    s = relation_marks.SIZE + 2
    pix = QPixmap(s, s)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    relation_marks.paint(p, QRectF(1, 1, s - 2, s - 2), kind)
    p.end()
    return QIcon(pix)


def open_window(win):
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QDialog,
                                 QHBoxLayout, QInputDialog, QLabel,
                                 QMessageBox, QPushButton, QTreeWidget,
                                 QTreeWidgetItem, QVBoxLayout, QCheckBox)
    from . import language, sketch_lock
    dlg = getattr(win, "_constraints_window", None)
    if dlg is not None:
        dlg.container = sketch_of(win)
        dlg.fill()
        dlg.show()
        dlg.raise_()
        return dlg
    dlg = QDialog(win)
    dlg.setWindowTitle(language.tr("Display/Delete Relations"))
    dlg.resize(560, 420)
    lay = QVBoxLayout(dlg)
    dlg.status = QLabel()
    dlg.status.setWordWrap(True)
    lay.addWidget(dlg.status)
    top = QHBoxLayout()
    top.addWidget(QLabel(language.tr("Show")))
    dlg.filter = QComboBox()
    for key, text in SHOW:
        dlg.filter.addItem(language.tr(text), key)
    top.addWidget(dlg.filter, 1)
    lay.addLayout(top)
    dlg.list = QTreeWidget()
    dlg.list.setHeaderLabels([language.tr("Relation"),
                              language.tr("Entities"),
                              language.tr("Value")])
    dlg.list.setRootIsDecorated(False)
    dlg.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
    dlg.list.setColumnWidth(0, 150)
    dlg.list.setColumnWidth(1, 280)
    lay.addWidget(dlg.list, 1)
    from PyQt5.QtCore import QSettings
    dlg.scale_first = QCheckBox(language.tr(
        "Scale the whole sketch on its first dimension"))
    dlg.scale_first.setToolTip(language.tr(
        "SolidWorks' option: the first size you give a sketch scales "
        "every shape in it to match; later dimensions drive only their "
        "own shapes."))
    dlg.scale_first.setChecked(sc.scale_first_enabled())
    dlg.scale_first.toggled.connect(lambda on: QSettings(
        "Kherve", "KherveCAD").setValue(sc.SCALE_FIRST, bool(on)))
    lay.addWidget(dlg.scale_first)
    row = QHBoxLayout()
    lay.addLayout(row)
    buttons = {}
    for key, text in (("value", "Edit value…"), ("delete", "Delete"),
                      ("delete_all", "Delete all"),
                      ("auto", "Auto constrain"), ("close", "Close")):
        b = QPushButton(language.tr(text))
        b.setAutoDefault(False)
        row.addWidget(b)
        buttons[key] = b
    dlg.buttons = buttons
    dlg.container = sketch_of(win)
    dlg._busy = False

    def picked():
        """Row indices (into the sketch's rows) of the selected lines."""
        return sorted(it.data(0, Qt.UserRole)
                      for it in dlg.list.selectedItems())

    def fill():
        cont = dlg.container
        if cont is None or cont.parent is None and \
                cont is not win.model.root:
            cont = dlg.container = sketch_of(win)
        dlg._busy = True
        try:
            dlg.list.clear()
            show = dlg.filter.currentData()
            rs = sc.rows(cont)
            for i, r in enumerate(rs):
                dim = "value" in r
                if (show == "relations" and dim) or \
                        (show == "dimensions" and not dim):
                    continue
                label, ents, value = describe(cont, r)
                if r.get("driven"):
                    label += " " + language.tr("(driven)")
                it = QTreeWidgetItem([language.tr(label), ents, value])
                it.setIcon(0, _icon(r.get("kind"), dim))
                it.setData(0, Qt.UserRole, i)
                it.setToolTip(1, ents)
                dlg.list.addTopLevelItem(it)
        finally:
            dlg._busy = False
        try:
            info = sketch_lock.describe(win.model, cont)
            state = sketch_lock.text(info)
        except Exception:
            state = sc.status_text(sc.solve(cont, write=False))
        dlg.status.setText(language.tr("%s — %d relation(s) and dimension(s). %s")
                           % (cont.name, len(sc.rows(cont)), state))
        buttons["delete_all"].setEnabled(bool(sc.rows(cont)))

    def selected_rows():
        # the shapes a picked relation ties light up in both views
        if dlg._busy:
            return
        nodes = []
        cont = dlg.container
        rs = sc.rows(cont)
        for i in picked():
            if i >= len(rs):
                continue
            for ref in rs[i].get("refs", ()):
                try:
                    node, _n = sc.entity(cont, ref)
                except (KeyError, ValueError, IndexError):
                    continue
                if node not in nodes:
                    nodes.append(node)
        if nodes:
            try:
                win.builder.active_tree().select_nodes(nodes)
            except Exception:
                pass

    def delete():
        for i in reversed(picked()):
            if i < len(sc.rows(dlg.container)):
                sc.remove(win.model, dlg.container, i)
        fill()

    def delete_all():
        n = len(sc.rows(dlg.container))
        if not n:
            return
        if QMessageBox.question(
                dlg, language.tr("Delete all"),
                language.tr("Delete all %d relations and dimensions of %s?")
                % (n, dlg.container.name)) != QMessageBox.Yes:
            return
        for i in reversed(range(n)):
            sc.remove(win.model, dlg.container, i)
        fill()

    def edit():
        sel = picked()
        rs = sc.rows(dlg.container)
        if len(sel) != 1 or "value" not in rs[sel[0]]:
            return
        i = sel[0]
        text, ok = QInputDialog.getText(
            dlg, language.tr("Value"), language.tr("New value:"),
            text=str(rs[i]["value"]))
        if ok and text.strip():
            from .sketch_constrain_ui import _value
            try:
                sc.set_value(win.model, dlg.container, i,
                             _value(text.strip()))
            except ValueError as exc:
                QMessageBox.warning(dlg, language.tr("Relations"),
                                    str(exc))
            fill()

    def auto():
        from .sketch_constrain_ui import auto as run
        run(win)
        fill()

    # the list follows the model while open (a relation added in a view)
    timer = QTimer(dlg)
    timer.setSingleShot(True)
    timer.setInterval(150)
    timer.timeout.connect(lambda: dlg.isVisible() and fill())

    def changed(node):
        if node is dlg.container or node is win.model.root:
            timer.start()
    win.model.node_changed.connect(changed)
    win.model.structure_changed.connect(timer.start)
    dlg._follow = changed

    dlg.filter.currentIndexChanged.connect(lambda _i: fill())
    dlg.list.itemSelectionChanged.connect(selected_rows)
    dlg.list.itemDoubleClicked.connect(lambda *_a: edit())
    buttons["value"].clicked.connect(edit)
    buttons["delete"].clicked.connect(delete)
    buttons["delete_all"].clicked.connect(delete_all)
    buttons["auto"].clicked.connect(auto)
    buttons["close"].clicked.connect(dlg.close)
    dlg.fill = fill
    win._constraints_window = dlg
    fill()
    dlg.show()
    dlg.raise_()
    return dlg

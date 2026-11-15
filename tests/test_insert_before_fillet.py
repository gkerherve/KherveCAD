"""A feature added while the history is rolled back past a Fillet goes in
BEFORE it (SolidWorks' rollback bar, Exercise 59: the pad made before
Fillet1, so the fillet rounds the pad's corner too).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


def test_a_pad_made_while_rolled_back_is_rounded_by_the_fillet():
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)

        def call(tool, **a):
            r = ex.execute(tool, a)
            assert "error" not in r, r
            return r
        sk = call("reference_geometry", action="sketch", origin=[0, 0, 0],
                  normal=[0, 0, 1])["sketch_id"]
        call("add_node", type="rect", parent_id=sk,
             params=dict(x=-100, y=-106.5, width=200, height=213))
        call("sketch_feature", node_id=sk, depth=25)
        part = win.model.root.children[0]
        edges = call("list_edges", node_id=part.id)["edges"]
        pick = [e["index"] for e in edges
                if e["convex"] and abs(e["centre"][2] - 12.5) < 1]
        call("fillet_edges", node_id=part.id, chains=pick, radius=10)
        fillet = win.model.root.children[0]
        assert fillet.type == "fillet"
        boss_sketch = fillet.children[0]
        # right-click the first feature in the tree: Roll back to here
        win.builder.active_tree()._roll_back(boss_sketch)
        assert fillet.params.get("rolled_off")
        s2 = call("reference_geometry", action="sketch", origin=[0, 0, 25],
                  normal=[0, 0, 1])["sketch_id"]
        call("add_node", type="rect", parent_id=s2,
             params=dict(x=40, y=-106.5, width=60, height=60))
        call("sketch_feature", node_id=s2, depth=10)
        # the pad's sketch went in under the fillet, before it
        pad = next(n for n in win.model.root.walk() if n.id == s2)
        anc = pad
        while anc.parent is not None and anc.parent.type != "fillet":
            anc = anc.parent
        assert anc.parent is fillet
        call("suppress", action="roll_forward")
        assert not fillet.params.get("rolled_off")
    finally:
        win._dirty = False
        win.close()

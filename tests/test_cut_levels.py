"""Cut Through's levels: quarters were too coarse for a two-storey
house, so the menu offers every tenth, a storey of the document's house,
and Up/Down nudges (cut_ui.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


def test_the_menu_offers_every_tenth_and_nudges(window):
    from khervecad import cut_ui
    positions = sorted(round(a.data(), 3)
                       for a in window._cut_positions.actions())
    assert positions == [round(i / 10.0, 3) for i in range(1, 10)]
    window.set_cut(True, axis="z", position=0.5)
    cut_ui.step_cut(window, 0.02)
    assert window.view3d.cut_state()["position"] == pytest.approx(0.52)
    cut_ui.step_cut(window, -0.1)
    assert window.view3d.cut_state()["position"] == pytest.approx(0.42)
    for _ in range(60):                      # it stops at the far end
        cut_ui.step_cut(window, -0.02)
    assert window.view3d.cut_state()["position"] == 0.0


def test_a_two_storey_house_can_be_cut_by_storey(window):
    from khervecad import cut_ui
    from khervecad import house as H
    assert cut_ui.storey_positions(window) == []      # nothing built yet
    H.build_house(window, {"floors": [
        {"rooms": [{"name": "Living room", "w": 5000, "d": 4000}]},
        {"rooms": [{"name": "Bedroom", "w": 5000, "d": 4000}]}],
        "roof": {"style": "Gable"}})
    levels = cut_ui.storey_positions(window)
    assert [name for name, _z in levels] == ["Ground floor", "First floor"]
    ground, first = (z for _n, z in levels)
    assert 0.0 < ground < first < 1.0
    # they land in the rooms, not in the slabs or the roof
    window.set_cut(True, axis="z", position=first)
    assert window.view3d.cut_state()["position"] == pytest.approx(first)
    cut_ui._fill_storeys(window, window._cut_storeys)
    assert len(window._cut_storeys.actions()) == 2

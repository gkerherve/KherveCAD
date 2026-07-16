"""Tests for the per-Object mesh cache: hits on placement/colour
changes, invalidation on content changes, and identical geometry
either way.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    mesh.clear_component_cache()
    mesh.CACHE_STATS.update(hits=0, misses=0)
    return DocumentModel()


def _assembly(model):
    a = model.new_component("A")
    model.add_node("sphere", dict(radius=10.0, segments=48), parent=a)
    b = model.new_component("B")
    b.params.update(x=50.0)
    model.add_node("cube", parent=b)
    return a, b


def test_second_tessellation_hits_cache(model):
    _assembly(model)
    mesh.tessellate_colored(model.root)
    assert mesh.CACHE_STATS["misses"] == 2
    assert mesh.CACHE_STATS["hits"] == 0
    mesh.tessellate_colored(model.root)
    assert mesh.CACHE_STATS["misses"] == 2
    assert mesh.CACHE_STATS["hits"] == 2


def test_moving_an_object_stays_cached(model):
    a, b = _assembly(model)
    first = mesh.tessellate(model.root)
    b.params["x"] = 80.0
    b.params["rz"] = 45.0
    second = mesh.tessellate(model.root)
    assert mesh.CACHE_STATS["misses"] == 2      # nothing re-tessellated
    assert mesh.CACHE_STATS["hits"] == 2
    assert len(second) == len(first)
    # and the move really happened
    xs1 = max(v[0] for t in first for v in t)
    xs2 = max(v[0] for t in second for v in t)
    assert xs2 > xs1 + 20.0


def test_recolouring_stays_cached_and_applies(model):
    a, _b = _assembly(model)
    mesh.tessellate_colored(model.root)
    a.params["color"] = "#aa0000"
    colored = mesh.tessellate_colored(model.root)
    assert mesh.CACHE_STATS["misses"] == 2
    tinted = [c for _t, c in colored if c is not None]
    assert tinted and all(c[0] == "#aa0000" for c in tinted)


def test_editing_contents_invalidates(model):
    a, _b = _assembly(model)
    before = mesh.tessellate(model.root)
    a.children[0].params["radius"] = 20.0
    after = mesh.tessellate(model.root)
    assert mesh.CACHE_STATS["misses"] == 3      # only A re-tessellated
    r_before = max(v[0] for t in before for v in t if v[0] < 40)
    r_after = max(v[0] for t in after for v in t if v[0] < 40)
    assert r_after > r_before + 5.0


def test_hiding_a_child_invalidates(model):
    a, _b = _assembly(model)
    n1 = len(mesh.tessellate(model.root))
    a.children[0].visible = False
    n2 = len(mesh.tessellate(model.root))
    assert n2 < n1


def test_cached_matches_uncached_geometry(model):
    """The cached pipeline must produce exactly the same triangles as
    a cold run."""
    a, b = _assembly(model)
    b.params.update(rz=30.0, z=5.0)
    cold = mesh.tessellate(model.root)
    warm = mesh.tessellate(model.root)          # from cache
    assert len(cold) == len(warm)
    for t1, t2 in zip(cold, warm):
        for v1, v2 in zip(t1, t2):
            assert v1 == pytest.approx(v2)


def test_global_variable_change_invalidates(model):
    """Editing a document variable an Object depends on must re-mesh
    it — the walk environment is part of the cache key."""
    var = model.add_node("assign", dict(variable="r", value="10"))
    comp = model.new_component("Var")
    model.add_node("sphere", dict(radius="r"), parent=comp)
    before = mesh.tessellate(model.root)
    var.params["value"] = "20"
    after = mesh.tessellate(model.root)
    assert max(v[0] for t in after for v in t) > \
        max(v[0] for t in before for v in t) + 5.0


def test_selection_pass_bypasses_cache(model):
    a, _b = _assembly(model)
    mesh.tessellate(model.root)
    sphere = a.children[0]
    tris = mesh.selected_world_tris(model.root, {sphere.id})
    assert tris                                  # highlight still works

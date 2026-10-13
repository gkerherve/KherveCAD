"""Reaction films: atom mapping and the rx_t-driven document program."""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import chem_reaction as cr, mesh
from khervecad.model import CadNode, validate
from khervecad.scadparse import parse_scad


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_water_formation_maps_every_atom():
    film, eq = cr.animation("H2 + O2 -> H2O")
    assert eq == "2 H2 + O2 → 2 H2O"
    assert sorted(film.reac.elements) == ["H", "H", "H", "H", "O", "O"]
    assert sorted(film.pi) == list(range(6))
    # every reactant atom ends on a product atom of its own element
    for a, p in enumerate(film.pi):
        assert film.reac.elements[a] == film.prod.elements[p]
    assert film.position(0, 0.0) == pytest.approx(film.reac.spread[0])
    assert film.position(0, 1.0) == pytest.approx(
        film.prod.spread[film.pi[0]])


def test_fractional_coefficients_are_refused():
    with pytest.raises(cr.BuildError, match="whole"):
        cr.animation("1 H2 + 1/2 O2 -> 1 H2O", balance_it=False)


def test_the_film_program_moves_with_rx_t(app):
    film, eq = cr.animation("CH4 + 2 O2 -> CO2 + 2 H2O")
    code, stats = cr.animated_program(film, eq, samples=9)
    assert stats["bonds_broken"] and stats["bonds_formed"]
    root, warnings = parse_scad(code)
    assert not validate(root), warnings
    start = mesh.tessellate(root)
    var = next(n for n in root.walk() if n.type == "assign"
               and n.params["variable"] == "rx_t")
    var.params["value"] = 1.0
    end = mesh.tessellate(root)
    assert start and end and start != end

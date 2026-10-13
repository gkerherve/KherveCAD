"""Polymer chains from repeat units, and their Library parts."""

import pytest

from khervecad import library, polymers


def test_a_chain_repeats_its_unit():
    assert polymers.chain_smiles("CC(Cl)", 3) == "CC(Cl)CC(Cl)CC(Cl)"
    pe = polymers.build_chain("CC", 4)
    assert pe.formula == "C8H18"


@pytest.mark.parametrize("key", list(polymers.PRESETS))
def test_every_polymer_preset_is_a_library_part(key):
    node = library.build_part(f"polymer_{key}", {"units": 2})
    assert node.children


def test_a_bad_unit_says_why():
    with pytest.raises(polymers.PolymerError):
        polymers.chain_smiles("CC.CC", 2)

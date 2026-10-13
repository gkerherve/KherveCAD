"""CIF files -> crystals with every atom of the cell (cifread)."""

import pytest

from khervecad import cifread
from khervecad.crystal_library import LIBRARY


@pytest.fixture(scope="module")
def app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win

RUTILE = """data_rutile
_chemical_name_mineral 'Rutile'
_chemical_formula_sum 'O2 Ti'
_cell_length_a 4.5937(3)
_cell_length_b 4.5937
_cell_length_c 2.9587(2)
_cell_angle_alpha 90
_cell_angle_beta 90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 42/m n m'
loop_
_symmetry_equiv_pos_as_xyz
'x, y, z'
'-x, -y, z'
'-y+1/2, x+1/2, z+1/2'
'y+1/2, -x+1/2, z+1/2'
'-x+1/2, y+1/2, -z+1/2'
'x+1/2, -y+1/2, -z+1/2'
'y, x, -z'
'-y, -x, -z'
'-x, -y, -z'
'x, y, -z'
'y+1/2, -x+1/2, -z+1/2'
'-y+1/2, x+1/2, -z+1/2'
'x+1/2, -y+1/2, z+1/2'
'-x+1/2, y+1/2, z+1/2'
'-y, -x, z'
'y, x, z'
loop_
_atom_site_label
_atom_site_type_symbol
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
_atom_site_occupancy
Ti1 Ti4+ 0 0 0 1
O1 O2- 0.3048(2) 0.3048(2) 0 1.0
"""


def test_a_cif_expands_to_every_atom_of_the_cell():
    c = cifread.read_cif(RUTILE)
    assert c.name == "Rutile" and c.space_group == "P 42/m n m"
    assert c.composition() == {"Ti": 2, "O": 4}
    # the same structure as the library's rutile
    assert c.computed_density() == pytest.approx(
        LIBRARY["rutile"].computed_density(), rel=0.01)
    assert c.nearest("Ti", "O") == pytest.approx(1.95, abs=0.03)


def test_operators_parse_fractions_and_signs():
    op = cifread.parse_op("-y+1/2, x-1/4, -z+3/4")
    assert cifread._apply(op, [0.1, 0.2, 0.3]) == pytest.approx(
        [0.3, -0.15, 0.45])


def test_a_cif_without_operators_for_a_symmetric_group_is_refused():
    text = RUTILE.split("loop_\n_symmetry_equiv_pos_as_xyz")[0] + \
        RUTILE.split("'y, x, z'\n")[1]
    with pytest.raises(ValueError, match="symmetry operators"):
        cifread.read_cif(text)


def test_a_custom_crystal_takes_the_asymmetric_unit_and_operators():
    from khervecad import crystal as cr
    c = cr.custom({"name": "NaCl", "a": 5.64,
                   "atoms": [["Na", 0, 0, 0], ["Cl", 0.5, 0, 0]],
                   "symops": ["x,y,z", "x,y+1/2,z+1/2", "x+1/2,y,z+1/2",
                              "x+1/2,y+1/2,z"]})
    assert c.composition() == {"Na": 4, "Cl": 4}


def test_build_crystal_reads_a_cif_path(tmp_path):
    from khervecad import crystal_build
    path = tmp_path / "rutile.cif"
    path.write_text(RUTILE)
    spec = crystal_build.spec_from_params({"path": str(path),
                                           "build": "unit_cell"})
    assert spec.crystal.composition() == {"Ti": 2, "O": 4}


def test_the_crystal_builder_opens_a_cif(tmp_path, window):
    from khervecad import crystal_dialog
    path = tmp_path / "rutile.cif"
    path.write_text(RUTILE)
    panel = crystal_dialog.open_builder(window)
    panel.load_cif(str(path))
    assert panel.crystal_obj().name == "Rutile"
    assert panel.spec().crystal.composition() == {"Ti": 2, "O": 4}

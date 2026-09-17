"""use / include, children() and code kept verbatim (scadinclude.py,
scadlib.py): a program built on libraries imports as nodes where it can
and as its own code where it cannot — never losing a statement."""

import os

import pytest

from khervecad import mesh, scadinclude, scadlib
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad


def _code(root):
    model = DocumentModel()
    model.root = root
    return model


@pytest.fixture
def library(tmp_path):
    scadinclude._LIBRARY_CACHE.clear()
    lib = tmp_path / "mylib"
    lib.mkdir()
    (lib / "parts.scad").write_text('''
        plate_t = 3;
        function double(x) = 2 * x;
        module plate(w = 10) { cube([w, w, plate_t]); }
        module framed(gap = 2) {
            children(0);
            translate([0, 0, gap]) children();
        }
        module odd() { weird_builtin_from_elsewhere(3); }
        cube(99);        // top-level geometry of a library: not imported
    ''')
    return tmp_path


def test_use_imports_modules_and_functions_not_variables(library):
    root, warnings = parse_scad(
        "use <mylib/parts.scad>\nplate(double(5));", str(library))
    assert [c.type for c in root.children] == ["scad_use", "union"]
    use = root.children[0]
    assert use.params == {"kind": "use", "path": "mylib/parts.scad"}
    cube = next(n for n in root.walk() if n.type == "cube")
    # the argument stays linked to its variable node; the library's own
    # variable (not a node) is folded to its value from the file's scope
    assert (cube.params["width"], cube.params["height"]) == ("w", 3.0)
    arg = next(n for n in root.walk() if n.type == "assign")
    # a library function is not in the tree: its result is folded in
    assert arg.params["value"] in (10.0, "10")
    assert not warnings


def test_include_brings_the_variables_too(library):
    root, _ = parse_scad("include <mylib/parts.scad>\ncube(plate_t);",
                         str(library))
    cube = root.children[-1]
    assert cube.params["width"] == 3.0


def test_directive_round_trips(library):
    root, _ = parse_scad("include <mylib/parts.scad>\nplate();",
                         str(library))
    code = _code(root).to_scad()
    assert "include <mylib/parts.scad>" in code
    again = _code(parse_scad(code, str(library))[0])
    assert again.to_scad() == code


def test_children_stand_for_the_calls_children(library):
    root, warnings = parse_scad(
        "use <mylib/parts.scad>\nframed(5) { cube(4); sphere(1); }",
        str(library))
    assert not warnings
    call = root.children[1]
    types = [n.type for n in call.walk()]
    assert types.count("cube") == 2          # children(0) + children()
    assert types.count("sphere") == 1
    assert validate(root) == {}
    assert mesh.tessellate(root)


def test_local_module_with_children():
    root, warnings = parse_scad('''
        module twice() { children(); translate([10, 0, 0]) children(); }
        twice() cylinder(h = 2, r = 1);
    ''')
    assert not warnings
    assert [n.type for n in root.walk()].count("cylinder") == 2


def test_a_library_module_that_does_not_import_cleanly_stays_code(library):
    root, warnings = parse_scad("use <mylib/parts.scad>\nodd();",
                                str(library))
    raw = root.children[1]
    assert raw.type == "scad_raw" and raw.params["code"] == "odd();"
    assert warnings == ["odd() kept as OpenSCAD code (rendered by OpenSCAD)"]


def test_unknown_calls_keep_their_block_and_indentation_stays_stable():
    source = "union() {\n    frob(1) {\n        cube(2);\n    }\n}\n"
    root, _ = parse_scad(source)
    raw = next(n for n in root.walk() if n.type == "scad_raw")
    assert raw.params["code"] == "frob(1) {\n    cube(2);\n}"
    code = _code(root).to_scad()
    assert _code(parse_scad(code)[0]).to_scad() == code


def test_missing_library_is_kept_and_flagged(tmp_path):
    root, warnings = parse_scad("include <nowhere/lib.scad>\ncube(1);",
                                str(tmp_path))
    use = root.children[0]
    assert use.type == "scad_use"
    assert any("file not found" in w for w in warnings)
    assert "library not found" in validate(root)[use.id]


def test_raw_code_asks_for_an_exact_render():
    root, _ = parse_scad("frob(1);")
    assert mesh.uses_booleans(root)


def test_a_parts_program_carries_the_documents_libraries(library):
    root, _ = parse_scad("use <mylib/parts.scad>\nodd();", str(library))
    model = _code(root)
    part = model.enclose_import_as_part("Imported")
    assert root.children[0].type == "scad_use"   # stays at the top level
    program = model.subtree_scad(part)
    assert "use <mylib/parts.scad>" in program
    assert "odd();" in program


def test_search_dirs_and_process_path(library, monkeypatch):
    monkeypatch.setattr(scadlib, "DOCUMENT_DIR", str(library))
    assert scadlib.resolve("mylib/parts.scad") == \
        os.path.join(str(library), "mylib", "parts.scad")
    assert str(library) in scadlib.search_dirs()


def test_install_unpacks_an_archive(tmp_path, monkeypatch):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("BOSL2-master/std.scad", "module x() {}")
        z.writestr("BOSL2-master/sub/a.scad", "a = 1;")
    monkeypatch.setattr(scadlib, "user_library_dir",
                        lambda: str(tmp_path / "libs"))
    lib = next(lib for lib in scadlib.KNOWN if lib.key == "BOSL2")
    urls = []
    folder = scadlib.install(lib, opener=lambda u: urls.append(u)
                             or buf.getvalue())
    assert urls == ["https://codeload.github.com/BelfrySCAD/BOSL2/zip/"
                    "refs/heads/master"]
    assert os.path.isfile(os.path.join(folder, "std.scad"))
    assert os.path.isfile(os.path.join(folder, "sub", "a.scad"))
    assert scadlib.installed(lib)


@pytest.mark.skipif(scadlib.resolve("MCAD/involute_gears.scad") is None,
                    reason="OpenSCAD's MCAD is not installed")
def test_mcad_gear_is_kept_as_its_call():
    root, _ = parse_scad("use <MCAD/involute_gears.scad>\n"
                         "gear(number_of_teeth = 17, circular_pitch = 200);")
    assert [c.type for c in root.children] == ["scad_use", "scad_raw"]

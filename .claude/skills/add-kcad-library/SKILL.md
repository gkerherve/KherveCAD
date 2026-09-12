---
name: add-kcad-library
description: Add the user's .kcad documents to KherveCAD's "KCAD files" library — scans the KCAD folder, lists the files not yet in khervecad/parts/, lets the user pick, copies them, checks each loads, runs the tests and commits. Use when the user says to add their kcad files / projects / models to the library, or to sync the KCAD folder.
---

# Add KCAD files to the library

The "KCAD files" library category (`khervecad/library_kcad.py`) offers
every `.kcad` in `khervecad/parts/` as a part. This skill brings new
documents in from the user's KCAD folder.

Arguments: an optional folder. Default: `~/Documents/KCAD Projects`
**and** `~/Documents` (top level only, where saved files also land).

## Steps

1. **Find candidates.** Run, from the repo root:

   ```bash
   .venv/bin/python -m khervecad.tools.kcad_sync --list [folder ...]
   ```

   It prints every `.kcad` in the folders that is NOT already in
   `khervecad/parts/` (matched by `library_kcad.part_id` of the stem,
   so `Door Stopper.kcad` and `door_stopper.kcad` count as the same),
   with its size, object count and validation errors. Files that fail
   to load are listed as such and never copied.

2. **Ask the user which to add.** Show the list and use
   AskUserQuestion (multi-select, or "all of them"). Never copy a file
   unasked: some documents are personal (a family member's likeness)
   and must not ship in the app. If a name looks personal ("Mon fils",
   a person's name, "Portrait"), point it out.

3. **Copy and verify.** For the chosen files:

   ```bash
   .venv/bin/python -m khervecad.tools.kcad_sync --add "<path>" ["<path>" ...]
   ```

   The tool copies each file into `khervecad/parts/`, copies any
   mesh (`.stl/.obj/.off/.3mf`) the document references from beside
   it, then loads the result through `library_kcad.load_part` and
   removes anything that fails. It prints the final list.

4. **Test and commit.** Run `python -m pytest tests/test_library_kcad.py
   -q` (offscreen). Then commit only `khervecad/parts/` with a subject
   like `feat: N more KCAD parts in the library` and push, per the
   repo's commit policy.

5. **Report** what was added, what was skipped and why, and remind the
   user that the running app needs a restart to show the new parts
   (Library ▸ KCAD files, and Insert ▸ Part Library).

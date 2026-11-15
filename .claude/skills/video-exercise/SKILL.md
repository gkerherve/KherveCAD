---
name: video-exercise
description: Rebuild a CAD tutorial video (SolidWorks, Fusion, Onshape...) in KherveCAD — turn a YouTube link, a video file, or a folder holding them into frames + captions with KherveFrames, read the steps, reproduce each in the live KherveCAD window, compare with the video, fix every KherveCAD problem it shows in a test-first loop, and only then write a KherveTeX report (PDF) of how the part is made. Use whenever the user gives a YouTube link or a video (or a folder with one) of a CAD exercise, or asks to reproduce / follow / copy a tutorial or exercise from a video.
---

# Rebuild a CAD exercise from a video

The point is twofold: get the part right, AND find out where KherveCAD
makes the exercise hard. The second matters as much as the first.

## 1. Find the source

The user may give:
- a YouTube link in the message;
- a video file (.mp4, .mov, .mkv, .webm);
- a FOLDER. Look inside it for a video file, and for links in any `.txt`,
  `.md`, `.url` (`URL=` line) or `.webloc` (`<string>` in the plist).
  Several links = several exercises: do them one at a time, asking which
  first if the order is not obvious.

Use the folder as the exercise's home: frames, notes and the `.kcad` go
there. With a bare link, make `~/Documents/KherveCAD Exercises/<video
title>/`.

## 2. Extract frames and captions

KherveFrames lives in `~/Documents/PycharmProjects/KherveFrames`
(its `./frames` launcher sets up certificates; never call frames.py with
the system Python).

```bash
~/Documents/PycharmProjects/KherveFrames/frames "<url or file>" --seconds 2 --subs --sheets --width 1280 --out "<exercise folder>/frames"
```

- One frame every 2 seconds is the DEFAULT (the user: ~50 frames for a
  10-minute video was not enough to see how each step is done — about
  30 a minute is). Go to `--seconds 1` over a fast passage
  (`--start/--end`, another `--out`). `--changes` alone misses clicks.
- `--sheets` tiles them 2x2 into `frames_sheets/`: read the SHEETS in
  order to follow every click (4 frames per picture), then open single
  frames at full size where a dimension, dialog or value must be read.
- `--subs` writes the caption on each image and `captions.txt` (what was
  said from one frame to the next). Add a language (`--subs fr`) if the
  video is not in English. "no captions found" is fine — go on without.
- Downloads are cached; re-running with other settings is cheap.
- If yt-dlp fails on a URL that used to work, run
  `.venv/bin/pip install -U yt-dlp` in that folder and retry.

## 3. Read the exercise before building

Read `captions.txt` whole, then look at the frames (Read the PNGs —
skim quickly, look closely at frames with dimensions, dialogs or a new
feature). Write `<exercise folder>/steps.md`: one numbered line per
feature — sketch plane, sketch shapes with EVERY dimension and relation
shown, then the feature (Extruded Boss 20 mm, Cut-Extrude Through All,
Fillet R5...) with the frame names it comes from. Note values you could
not read. The final part often shows in a drawing or the last frames:
take its overall size to check against at the end.

## 4. Build it in KherveCAD, the way the video does

Use the live window through the `mcp__khervecad__*` tools (and
get_document_info first). Follow the video's ORDER and its features —
sketch on the same plane or face, the same relations and Smart
Dimensions (`sketch_constraint`), the same extrudes / cuts / fillets /
patterns / mirrors (hole_wizard, fillet_edges, suppress, reference_geometry...)
— not a shortcut program that only ends up the same shape. The test is
whether a SolidWorks user could do it in KherveCAD the same way.
Name each feature as in the video. After each feature, `render_view`
from the angle of the matching frame and compare; fix before moving on.

When the user asks to watch, prefer real mouse work (computer use) over
MCP for the steps they want to see.

## 5. Check and save

Compare the finished part with the last frames: `render_view` from the
same views, `mass_properties` / `get_node_bounds` against any given
size or mass. Save as `<exercise folder>/<title>.kcad`; put a
`compare/` folder of KherveCAD renders beside matching frames if useful.

## 6. Problems → fix KherveCAD in a loop

Keep `<exercise folder>/problems.md` as you go: for each step that was
hard, impossible, wrong or needed a workaround — what the video did,
what KherveCAD did instead, how bad (blocker / workaround / cosmetic),
which module or tool it concerns, and a status (open / fixed in vN).

Then FIX THEM, without waiting to be asked, worst first, in a loop:

1. Reproduce the problem in a unit test under `tests/` first (offscreen,
   real mouse events where the user would use the mouse — see the
   `*_by_mouse` / `test_*_mouse` tests); it must FAIL before the fix.
2. Fix KherveCAD so it works BY MOUSE for a human, not only through MCP
   (the user, 2026-11-14): a ribbon button and a ToolPanel window like
   Extruded Boss's (feature_pick toggles, boxes filled by clicking
   regions / faces / planes / edges in 3D, OK / Cancel); an MCP-only fix
   is not a fix. Test the mouse path with real mouse events. (Follow CLAUDE.md: file size, MCP reach, help /
   tooltips, CLAUDE.md notes for anything non-obvious).
3. Run the new test and the related test files; then the whole suite
   before the commit if the change is broad.
4. SHOW IT (the user, 2026-11-14: "put pictures of what you've done,
   like the new ribbon, what you've added — in the chat"): after each
   fix, take pictures of what changed — the new or changed ribbon /
   button / window (a screenshot of the running app or an offscreen
   `QWidget.grab()` of the ribbon or panel), and the model result
   (`render_view`) — save them in `<exercise folder>/fixes/`, and send
   them in the chat with SendUserFile, each with a one-line caption
   saying what it shows. The report reuses them.
5. Commit and push each fix on its own (`v<N>: fix: ...`, CLAUDE.md
   rules; stage only your own files). Mark it fixed in problems.md.
6. Redo the exercise's affected steps — from scratch, the video's way —
   in a fresh document. New problems go back into the list.

Repeat until the WHOLE exercise goes through the video's way with no
open blocker or workaround. Cosmetic leftovers may stay open, listed.
A missing tool that is a big feature of its own (days of work): build it
if the exercise cannot be done without it, but tell the user it is
coming first; anything else, ask before starting.
If the loop stalls (the same problem three times), stop and ask.

## 7. The report — a TUTORIAL, only once it works

Only when step 6 is done and a final clean run of the exercise worked,
write the report in **KherveTeX** (the `mcp__khervetex__*` tools drive
the user's live KherveTeX window; get_document_info first, new_document
— never discard unsaved work: save it first).

The report is a **step-by-step tutorial for recreating the exercise in
KherveCAD**, written for a person at the mouse — NOT an account of the
problems met or the fixes made (those stay in problems.md and in your
chat summary; the report never mentions them, nor MCP calls, scripts or
versions beyond the author line). The user, 2026-11-14: "put a circle,
go into Sketch, put the circles at 47, another one at 30, then trim this
and trim that — exactly what you need to do".

Title = the video's title; author line "Recreated in KherveCAD vN".
Contents:

- **The part**: what it is, overall size, the video link, the drawing /
  final frame from the video and a picture of the finished KherveCAD part.
- **Step by step**, one subsection per feature in the video's order, each
  split into numbered actions, exactly as the user does them in KherveCAD:
  which tab and button ("Features ▸ Extruded Boss/Base"), which plane or
  face to click, which sketch tool, where to click, every Smart Dimension
  and relation with its value ("Smart Dimension the circle: 47"), each
  Trim / Mirror / Offset, leaving the sketch, the feature window's
  settings (Direction, End condition, Distance), OK.
- **The video's own ORDER, one action at a time** (the user, same day:
  "how did you get this half circle? did you trim it? ... first the
  rectangle, then the circles, then the line, then trimming"). Read the
  captions AND the frames between features: every sketch tool he uses,
  in his order — Center Rectangle, Circle, dimension, Line, Trim (what is
  clicked away), Centerline, Mirror Entities, dimension, Trim, Exit,
  Extrude — each its own numbered step with its own picture showing the
  sketch exactly as it stands after that action (dimensions so far).
  Never jump to the finished outline, never reorder, never replace his
  construction by an easier one.
- **Few words: clicks and icons** (the user: "not a crazy number of
  text ... click here, click there, and show the icon I need to click
  on"). Each step is one or two short lines — the tool's ribbon ICON
  (`icons_cad.pixmap(key, 64, "SolidWorks")`, every icons_cad* module
  imported, saved to report/icons/, inline at 1.4em) + its name in bold
  + the clicks joined by arrows + the values in bold: "[icon] **Center
  Rectangle** → click the origin → drag. [icon] **Smart Dimension** →
  **75**, **9**." No explanations, no section of prose; the picture says
  the rest. Keep the generator as report/make_tutorial.py.
- **Every Smart Dimension he places** (the user: "he was using the
  smart dimension all the way"): its own click line — "[icon] **Smart
  Dimension** → click this → click that → **40**" — and DRAWN in the
  sketch pictures as KherveCAD draws it (extension lines, arrows, Ø
  leaders: `sketchpic` dims "h" / "v" / "d" / "a"), kept in every later
  picture of that sketch. Grep the captions for "smart" / "dimension" /
  "give" and look at the frames to list them all before writing.
- **The tool windows too** (the user, 2026-11-14: "show images of the
  tools / icon / window, like Extrude Boss or Cut"): under the step that
  opens one, a picture of KherveCAD's own window — the Boss / Cut toggle
  bar, the Extrude / Extruded Cut window, Mirror Entities, Trim, Offset,
  Circular / Linear Pattern, Plane, Mirror, Hole Wizard, Full Round.
  `~/Documents/KherveCAD Exercises/toolwins.py windows` pictures them all
  offscreen (add a new tool's window there); after make_tutorial.py run
  `python3 add_windows.py "<exercise folder>"`, which copies them into
  report/windows/ and puts each under the first step naming its tool
  (re-runnable: it drops the windows it added before).
- **Into KherveTeX**: `python3 ~/Documents/KherveCAD\ Exercises/full_tex.py
  "<folder>" "<name>" "<title>" <version>` writes a whole .tex (figures as
  centred pictures — KherveTeX makes a figure a float and the pictures
  drifted pages away from their steps); open_document it, compile, look,
  save as .ktex and export the PDF. Never `\input` the body: KherveTeX
  caches the file and the blocks are not editable.
- **A picture for every stage**: the SKETCH finished and dimensioned
  (the 2D sketch view: render_view view "2d", or a 3D view square on),
  then the part after the feature (render_view 3D). Save each into
  `<exercise folder>/report/NN_name.png` as you build (the build script
  shoots after every step), so the report shows the part growing image
  by image. Put the matching video frame beside it where it helps.
- **Check**: the finished part against the video's, sizes / mass.

compile_document, look at EVERY page with render_page (pictures present,
nothing running off the page — one image per figure, `[H]`, widths
≤ 0.8\linewidth; tables in p{} columns; plain spaces in numbers, no
\,), then save as `<exercise folder>/<title>.ktex` and export_pdf
`<title>.pdf` beside it. If KherveTeX is not connected, say so and ask
the user to open it rather than writing LaTeX by hand. End by giving the
user the PDF path; summarise the fixes in the chat, not in the report.

## 8. Working rules learnt the hard way (read before starting)

- **Git safety.** Other sessions and the user have uncommitted work in
  this checkout. Stage only your own files (`git add <path>`). NEVER run
  `git checkout -- <dir>`, `git checkout HEAD -- khervecad`, `git reset
  --hard` on main, `git stash` or `git clean`: one `git checkout HEAD --
  khervecad` destroyed the user's unsaved `library_home_more.py` work for
  good. To drop your own change to one file, edit it back by hand.
- **Commit subject** `v<N>: fix: ...` with N = `git rev-list --count HEAD`
  + 1, body ends `Co-Authored-By: Claude <model> <noreply@anthropic.com>`;
  push each commit at once.
- **Several videos = parallel agents**, one exercise each (the user asks
  for this). Agent tool, `isolation: "worktree"`, **model "sonnet" by default**
  (the user, 2026-11-15: Sonnet agents, not Opus). Sonnet follows a brief
  literally, so the brief must spell out everything below plus: read this
  SKILL.md and CLAUDE.md first; write steps.md before building; test-first
  for every fix; stop and report after 3 failed tries at one problem
  instead of guessing; never claim a fix works without its test run.
  The coordinating session reviews each agent's diff before merging. Brief each one with: the video link, its
  exercise folder (a new name if it would clash with an existing one —
  e.g. "Exercise 57 - Bearing bracket 2"), this skill, and these rules:
  - first `git reset --hard main` IN ITS WORKTREE (worktrees start from an
    old commit);
  - build OFFSCREEN (`QT_QPA_PLATFORM=offscreen`, a `MainWindow` + 
    `mcp_tools.McpToolExecutor`), never the user's live KherveCAD window
    — several agents on one window wreck each other's documents;
  - commit its fixes in its worktree, do not push; report the commit
    shas, the tests it added, and the report pictures' folder.
  - The usage quota is limited: at most ~4 agents at once; if the limit
    is hit, stop them and resume after the reset (SendMessage to the
    same agent keeps its context).
- **Merging an agent's fixes**: on main, `git cherry-pick <sha>` one by
  one, then `git commit --amend` the subject to the right `v<N>` (the
  count changes with each pick), run the agent's tests + the related
  ones, push. Conflicts are usually both sides adding entries to
  `mcp_schema.py` enums / tables: keep both. Skip a commit whose change
  main already has.
- **Known failing tests that are NOT yours** (failing before this work):
  `tests/test_tool_panels.py` (4), `tests/test_whole_face.py::
  test_a_corner_a_cut_eats_leaves_the_point_where_it_was`,
  `tests/test_sketch_tools.py` (3). Don't chase them; do not let new ones
  join them.
- **Real-mouse tests** need the window SHOWN (`win.show()`,
  `QTest.qWaitForWindowExposed`) or clicks never land; drag with the
  button held (see `_drag` helpers in existing `*_by_mouse` tests). A
  modal dialog in an offscreen test hangs it silently — answer through
  the module's `ask_hook` / conftest.
- **A fix's test must fail without the fix.** If it passes on the old
  code too, say so to the user instead of claiming it proves the fix.
- **Helper scripts** in `~/Documents/KherveCAD Exercises/`:
  `sketchpic.py` (sketch pictures with Smart Dimensions drawn),
  `toolwins.py windows` (tool-window pictures, offscreen),
  `add_windows.py "<folder>"` (puts them under their steps),
  `full_tex.py "<folder>" "<name>" "<title>" <version>` (the whole .tex
  for KherveTeX). Each exercise keeps its own `report/make_tutorial.py`
  — copy the latest exercise's as the starting point.
- **Finish** with: the PDF sent by SendUserFile, the exercise list with
  page counts, the fix versions, and the cosmetic leftovers still open
  (e.g. Exercise 49: a sliver beside the ring in the exact render, fake
  chord edges inside the ring offered to list_edges, the 156 dimension
  from the origin not placed).

Done so far (all in `~/Documents/KherveCAD Exercises/`, .ktex + .pdf):
Exercises 6 (Rib), 7, Linear & Circular Pattern, 49, 50, 51, 52, 53, 54,
55, 57, 58 — fixes v1075–v1109. Copy the closest one when a new video
uses the same tools.

---
name: tutorial-video
description: Make a narrated tutorial VIDEO (MP4) of a part being built in KherveCAD by real mouse clicks — no YouTube needed. Starts with the finished part turning and its full professional 2D drawing, then before each feature shows the drawing zoomed on that feature with the pointer resting on every size it uses, then films the mouse building it in the KherveCAD window, voiced by a natural macOS voice. Use when the user asks to make / film / record a video or tutorial of an exercise or part, gives an exercise folder and asks for its video, or says "reproduce with video".
---

# Film an exercise as a tutorial video

Everything runs OFFSCREEN (`QT_QPA_PLATFORM=offscreen`) from the KherveCAD
repo with the project venv: `PYTHONPATH=. .venv/bin/python <script>` (only
it has manifold3d — without it cuts silently do not draw). Never drive the
user's live window. The recorder is `khervecad/tutorial_video.py`
(`Recorder`); read its docstrings once.

## 0. What the folder must hold

An exercise folder (e.g. `~/Documents/KherveCAD Exercises/<name>/`) with
`steps.md` (every feature, every dimension) and the FINISHED part as a
`.kcad` or a build script that makes it through MCP calls (usually
`build/part.py`). No finished part yet? Rebuild the exercise first with the
**video-exercise** skill, then come back. Look at the finished part from 3
angles (`render_view`) before anything else: a broken feature (notches,
slivers, stray faces) shows on the drawing too — fix the MODEL first (e.g.
draw rounds as arcs in the sketch when a 3D fillet misbehaves) and say so.

Work in `<folder>/video/`.

## 1. The drawing — professional, every dimension

Write `video/make_drawing.py` (copy Exercise 7's:
`~/Documents/KherveCAD Exercises/SolidWorks Exercise 7 - Base block
(KwnAr5AAgCI)/video/make_drawing.py`): open the finished `.kcad`, MCP
`blueprint` new_sheet → sheet (A3 for most parts; fields title, number,
material, drawn) → auto_dimension → **add every size the part needs**:
overall sizes, hole / boss Ø, hole positions, thicknesses, offsets, and
EVERY radius (`kind radius`, centre + r). Remove an auto label that is
wrong (an open arc read as R40 that is really Ø80). Name the views
(`set_view show_label`), give the views room (`set_view` x, y = the view's
BOTTOM-left in sheet mm). Export the PNG and write `<drawing>.json` (sheet
size + each view's sheet_rect_mm, model_bounds, scale) — the video maps
model points onto the sheet with it. LOOK at the PNG: no overlapping
numbers, no dimension crossing a view, nothing missing compared with
steps.md. Iterate; show the user the drawing before filming if it is new.

## 2. The film script

`video/make_video.py` (copy Exercise 7's). Shape:

1. Open the finished `.kcad`, `rec = Recorder(win, "<name>.mp4")` (no side
   panel), `rec.answer_values()`, `at(view, u, v, label)` from the json.
2. `rec.say(...)` + `rec.showcase(win.view3d, DRAWING, title=...)`: the
   finished part turning beside its drawing.
3. `new_document(discard_unsaved_changes=True)`, `win.force_refresh()`,
   `rec.title("Let's build it", ...)`.
4. For EACH feature, in the video's / steps.md's order:
   - `rec.say("Step n, <feature>. <the sizes, spelt as spoken>.")`
   - `rec.explain_drawing(DRAWING, [at(...), ...])` — stops ON the
     dimension NUMBERS (look at the PNG to place them), one per size used.
   - `rec.chapter = "n  <Feature name>"`
   - the real mouse actions, one short `rec.say` per action:
     `click_tab`, `click_action(<action data key>)`, `click_sketch(x, y)`,
     `drag_sketch(a, b)`, `click_world((x, y, z))`, Smart Dimension with
     `rec.values = [...]` then clicks, Extrude window via
     `extrude_panel._panel(win)` + `type_into` / `choose` / `click(ok)`,
     region picks + `region_panel.ok_button(win)`.
     Copy techniques from the `tests/*_by_mouse.py` tests.
   - print `analysis.mass_properties(mesh.tessellate(win.model.root))`
     size / volume and compare with the reference part.
5. A closing line and `rec.finish()`.

A step that will not go by mouse after 3 honest tries is a KherveCAD bug:
fix it test-first (video-exercise skill section 6), then film. NEVER do a
step through MCP and never change the construction to dodge a broken click
(the user, 2026-11-20: "everything must be doable manually with the mouse;
if something cannot be done by mouse, the app must be updated"). Build the
film on `~/Documents/KherveCAD Exercises/mousefilm.py` (DRY=1 rehearses
with real-time waits; STOP=<tag> dumps the tree), and make the tutorial
PDF FROM the film with `film_pdf.py "<mp4>" "<Title>" "<url>"` so the PDF
shows the same mouse steps.

## 3. Check before handing over

- The final size and volume match the reference within 1 %.
- Contact sheet: `ffmpeg -i <mp4> -vf "fps=1/5,scale=480:-1,tile=6x6"
  -frames:v 1 sheet.png`, then READ it: pointer on the right things, no
  stuck dialog, old model gone after new_document, captions sensible.
  Open single frames where a drawing stop or a dimension must be checked.
- Send the MP4 with SendUserFile.

## Naming (the user, 2026-11-16)

Never call or name the video from the exercise number: not the file
(`Exercise 1.mp4`), not the on-screen title, chapter tags, captions or the
narration ("Exercise 1"). Name it after WHAT THE PART IS ("Base plate with
two holes.mp4", title card "Let's build a base plate"). Say "this part" or
its name, never "exercise N". The exercise folders and the publish copies keep
the number (three digits, below), but nothing filmed shows it.

## Exercise folders: one per exercise, uniform names (the user, 2026-11-20)

`~/Documents/KherveCAD Exercises/Exercise NNN - <Part name>/` (three digits, the part's name, no
"SolidWorks", no video id; the source link lives in `steps.md`). Examples:
`Exercise 002 - Bearing bracket`, `Exercise 135 - Sheet metal bracket`. Keep the video's own number;
a video with no number, or one that clashes with an existing number, takes the next free number
after the highest (155, 156...). Everything for the exercise lives in that folder; the files to
publish go in its `web/` subfolder:
`Exercise-NNN-video.mp4`, `Exercise-NNN-video.srt`, `Exercise-NNN-drawing.png`,
`Exercise-NNN-tutorial.pdf` and `Exercise-NNN-<part-name>.kcad`.
Every step in the film is done with the mouse in kCAD (no MCP shortcuts; the user rejected films
that used them). When `web/` is complete, hand it to the khervetools-web session: its
`publish-kcad-exercise` skill puts it on YouTube and the site.

## Settings the user chose (2026-11-15)

- Voice **Jamie (Premium)**, 165 words a minute (`tutorial_video.VOICE`,
  `RATE`); any installed macOS voice works by name. A Premium voice is
  added in System Settings ▸ Accessibility ▸ Spoken Content ▸ Manage
  Voices.
- NO drawing on the side during the build; the drawing comes full screen
  BEFORE each step (`explain_drawing`, glide 0.9 s, rest 1.3 s, zoom 0.9 s
  — the user found slower too slow).
- Captions burnt in; `.srt` and a narration `.txt` written beside the MP4.
- Cheap runs: one Sonnet agent per exercise is fine for filming
  (`model: "sonnet"`), with this skill and the folder in its brief; it must
  not edit `khervecad/` while other sessions work there unless told.

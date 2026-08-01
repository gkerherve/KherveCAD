# Building and running KherveCAD on macOS

PyInstaller cannot cross-compile, so a macOS build has to happen on a
Mac. Either run the steps below locally or let
`.github/workflows/macos-build.yml` do it on a GitHub runner, which also
publishes the release.

## Build

```bash
pip install -r requirements.txt
pip install pyinstaller
python packaging/build_macos.py
```

Output, in `dist/`:

| Artifact | What it is |
|---|---|
| `KherveCAD-<ver>-macOS-arm64.dmg` | drag-to-install disk image |
| `KherveCAD-macOS-arm64.dmg` | stable-name copy, for a "latest" link |
| `openscad-<osver>.src.tar.gz` | OpenSCAD's source — attach it to the release |

`build_macos.py` is the macOS counterpart of `build_installer.py` and
runs the same first step: write `khervecad/VERSION` from git, because a
frozen bundle ships no `.git` and would otherwise report the `0.1.0`
placeholder. There is no installer to compile — on macOS a drag-install
replaces the whole bundle atomically, so the upgrade problems
`packaging/khervecad.iss` works around cannot happen here.

## Apple Silicon only

The DMG is arm64, and there is no Intel build. The reason is the engine,
not the app: KherveCAD bundles OpenSCAD so no user lands silently in
approximate-boolean preview mode, and the last *stable* OpenSCAD
(2021.01) predates Apple Silicon — only the snapshot builds ship an
arm64 binary. An Intel KherveCAD would have to carry an Intel OpenSCAD
and then run the whole thing under Rosetta on the machines most people
now have. `build_macos.py` verifies the bundled binary's architecture
with `file` and refuses to build a mismatched pair.

Which OpenSCAD snapshot gets bundled is **discovered at build time** from
`https://files.openscad.org/snapshots/` (newest arm64 disk image), not
hard-coded, because the snapshot filenames carry a build date and
revision. The chosen URLs are printed in the build log; feed them back
through `KHERVECAD_OPENSCAD_DMG` and `KHERVECAD_OPENSCAD_SRC` to
reproduce an exact earlier release. The engine lands in
`KherveCAD.app/Contents/Resources/openscad/OpenSCAD.app`, where
`engine.bundled_openscad()` looks for it.

## Gatekeeper

The DMG is **ad-hoc signed, not notarized.** The ad-hoc signature is what
lets the binary execute at all on Apple Silicon; it does nothing for
Gatekeeper. It is also why signing happens *last*: dropping OpenSCAD into
the bundle invalidates whatever PyInstaller signed. macOS quarantines
anything downloaded from a browser, so on first launch users see
*"KherveCAD is damaged and can't be opened"* — which is misleading.
Nothing is damaged; the app simply has no Developer ID.

Either:

```bash
xattr -dr com.apple.quarantine /Applications/KherveCAD.app
```

or right-click the app → **Open** → **Open** in the dialog. A DMG copied
over by AirDrop or a USB stick is not quarantined and just opens.

Removing this friction requires an Apple Developer Program membership
(99 USD/yr) to sign with a Developer ID and notarize through Apple. Once
you have one, add `codesign --options runtime` with the identity plus
`xcrun notarytool submit --wait` and `xcrun stapler staple` to
`build_macos.py`'s `sign()` step.

## Licensing

Shipping OpenSCAD's binary makes the DMG a redistribution, exactly as on
Windows: its licence installs beside it as
`Contents/Resources/openscad/COPYING.txt`, `README-OpenSCAD.txt` names
the build and where it came from, and the **matching source archive must
be attached to the release**. The workflow uploads the `.src.tar.gz`
alongside the DMG for that reason. See `docs/INSTALLER.md`.

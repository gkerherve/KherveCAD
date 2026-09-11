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

The DMG is arm64, and the engine decides that, not the app. KherveCAD
bundles OpenSCAD so no user lands silently in approximate-boolean preview
mode, and the last *stable* OpenSCAD (2021.01) predates Apple Silicon: it
is x86_64 only, so bundling it would mean Rosetta on the machines most
people now have. The nightly snapshots ship a **universal** binary that
runs natively on Apple Silicon, so the engine comes from there.
`build_macos.py` reads the extracted binary with `file` and refuses to
build a pair that is not native — the filename is never taken as proof.

Which snapshot gets bundled is **discovered at build time** from
`https://files.openscad.org/snapshots/`, not hard-coded, because the
filenames carry a build date. Only *dated* names are eligible: that index
also holds branch builds (`OpenSCAD-tests2.dmg`) which would otherwise
sort newest. The chosen URLs are printed in the build log; feed them back
through `KHERVECAD_OPENSCAD_DMG` and `KHERVECAD_OPENSCAD_SRC` to
reproduce an exact earlier release. The engine lands in
`KherveCAD.app/Contents/Resources/openscad/OpenSCAD.app`, where
`engine.bundled_openscad()` looks for it.

**Where the source comes from.** files.openscad.org publishes an
`openscad-<ver>.src.tar.gz` only for stable releases — there is no source
archive beside the nightlies. Since the GPL obligation is the source
corresponding to the binary we ship, the build resolves the snapshot's
build date to the last commit on `openscad/openscad` master that day and
attaches that commit's tarball. That names one exact tree rather than a
moving branch.

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

Only the first install needs this. Later versions arrive through
**Help > Check for Updates...** (or the daily automatic check): the app
downloads the new DMG itself, and a file fetched that way carries no
quarantine flag; the updater strips it anyway after swapping the bundle.
See "Updates" in `docs/INSTALLER.md`.

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

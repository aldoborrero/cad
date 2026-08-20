# FreeCAD's development line, beside the release rather than instead of it.
#
# The two answer different questions. `freecad` is what nixpkgs packages and what this
# repo's preferences, addons and patches are written against; `freecad-unstable` is
# where you go to see whether something you want is already upstream — the Sketcher's
# auto-constraint hint lines, say, which landed in main in July and are the reason this
# exists.
#
# Pinned to a *weekly tag*, not to main: upstream cuts those as snapshots it considers
# buildable, so moving forward is a deliberate edit here rather than catching the tree
# mid-refactor. There is no flake input for it on purpose — `fetchFromGitHub` with
# `fetchSubmodules` takes the commit's tree and its submodules and nothing else, where
# a `git+https` flake input clones the repository (596k objects and 5 GB of git cache,
# measured) to build one tag.
#
# Carries the same patches as the release build, and all four apply against this tag.
# That they do is not luck: they anchor on small, stable places — MainWindow's
# constructor, ToolBarManager::setupMenuBar, the overlay rect arithmetic — and those
# have barely moved. Measured with `patch -p1` against the fetched tree: offsets of up
# to 415 lines, no failed hunk.
#
# One hunk is placed with **fuzz 2**, meaning two context lines did not match and patch
# positioned it by approximation — which is how code ends up in the wrong place, and has
# cost a full build here before. It is custom-titlebar.patch's first hunk on
# `src/Gui/MainWindow.h`; upstream added <QByteArray> and <QString> around the include
# block it anchors on. Checked by hand: the include still lands between <QMainWindow>
# and <QMdiArea>, where it belongs. Re-check it when bumping the tag — nothing else will.
#
# hide-start-tab has its own copy for this tree because the release one costs a second
# fuzzed hunk here; the weekly copy applies with a plain offset. The day the two
# converge they can go back to being one file.
{ pkgs, ... }:
let
  tag = "weekly-2026.08.20";
in
pkgs.freecad-wayland.overrideAttrs (old: {
  pname = "freecad-unstable";
  version = tag;

  # Submodules are not optional here: main moved Coin, Pivy and OndselSolver out of the
  # tree into them, and without them CMake stops at "the OndselSolver git submodule is
  # not available". nixpkgs does not need this because 1.1.1 still shipped them inline.
  src = pkgs.fetchFromGitHub {
    owner = "FreeCAD";
    repo = "FreeCAD";
    rev = tag;
    fetchSubmodules = true;
    hash = "sha256-lXcHg86qkDAZcC5xv013gEvY+mfAtz+v9NadWU3/7SA=";
  };

  # nixpkgs carries two patches: its own PYTHONPATH fix, and a cherry-picked upstream
  # commit that is already in this tree. Only the first is kept, matched by name so a
  # nixpkgs rename fails loudly here instead of silently dropping one that still
  # matters. This repo's own follow.
  patches =
    builtins.filter (p: builtins.match ".*NIXOS-don-t-ignore-PYTHONPATH.*" (toString p) != null) (
      old.patches or [ ]
    )
    ++ [
      ../patches/astocad-titlebar/custom-titlebar.patch
      ../patches/freecad-start-tab/hide-start-tab-weekly.patch
      ../patches/freecad-tabs-north/tabs-north.patch
      ../patches/astocad-home-icon/home-icon.patch
    ];

  postPatch = (old.postPatch or "") + ''
    cp -r ${../patches/astocad-titlebar/customtitlebarkit} src/3rdParty/customtitlebarkit
    chmod -R u+w src/3rdParty/customtitlebarkit
  '';

  # Two things main's build wants that the 1.1.1 derivation does not provide: gtest,
  # and defusedxml, which the Addon Manager now checks for at configure time and stops
  # without.
  nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.gtest ];

  buildInputs = (old.buildInputs or [ ]) ++ [ pkgs.python3Packages.defusedxml ];

  # blueprint exposes every `passthru.tests` entry as a flake check, and nixpkgs' set is
  # not all derivations: `callPackage` adds `override` (a set) and `overrideDerivation`
  # (a lambda) beside the real `modules` and `python-path`. Without this, `nix flake
  # check` stops at "flake attribute 'checks.x86_64-linux.pkgs-freecad-unstable-override'
  # is not a derivation" — an error about this flake, produced entirely by upstream's
  # plumbing, and invisible to `nix build` of any individual attribute.
  passthru = (old.passthru or { }) // {
    tests = pkgs.lib.filterAttrs (_: pkgs.lib.isDerivation) (old.passthru.tests or { });
  };

  meta = old.meta // {
    description = "${old.meta.description}, built from an upstream weekly snapshot";
  };
})

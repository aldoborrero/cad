# The Timeline addon: a Fusion-shaped feature timeline docked under the 3D view.
#
# Brought over from aldoborrero/inresearch, where it was developed. Two things about
# the layout are load-bearing:
#
# The directory *name* becomes the module name — `DirMod.name` is `path.name` in
# FreeCADInit.py — so this installs to `$out/Mod/Timeline` rather than straight into
# `$out`, which would have FreeCAD calling the addon
# "xxxxxxxx-freecad-timeline-1.0.0". nix/packages/freecad.nix therefore hands
# `--module-path` the `Mod/Timeline` path, not the store root.
#
# And the install is by *exclusion*. A hardcoded include-list silently drops any new
# top-level file, and an addon that ships without one of its own modules fails at
# import time in the GUI, which is the worst place to find out.
{ pkgs, ... }:
let
  inherit (pkgs) lib;

  # package.xml is the Addon Manager's canonical metadata, so it is the one place the
  # version lives rather than a copy kept in step by hand. tests/test_packaging.py
  # asserts it matches `__init__.__version__`.
  version = lib.head (lib.match ".*<version>([0-9.]+)</version>.*" (builtins.readFile ./package.xml));

  notShipped = [
    "tests"
    "tools"
    "conftest.py"
    "pytest.ini"
    "pyproject.toml"
    "default.nix"
    "__pycache__"
    ".pytest_cache"
    ".ruff_cache"
    ".mypy_cache"
  ];
in
pkgs.stdenvNoCC.mkDerivation {
  pname = "freecad-timeline";
  inherit version;

  src = ./.;

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall

    mod=$out/Mod/Timeline
    mkdir -p "$mod"
    cp -r . "$mod/"
    ${lib.concatMapStringsSep "\n    " (p: ''rm -rf "$mod/${p}"'') notShipped}

    test -f "$mod/InitGui.py"
    test -f "$mod/package.xml"

    runHook postInstall
  '';

  meta = {
    description = "FreeCAD addon: a Fusion-style feature timeline docked under the 3D view";
    longDescription = ''
      A dock along the bottom of the FreeCAD window showing the active PartDesign
      body's features in Group order, with a draggable rollback marker, suppression,
      rename and delete, drag-and-drop reordering and recompute-status badges.
    '';
    license = lib.licenses.lgpl21Plus;
    platforms = lib.platforms.all;
  };
}

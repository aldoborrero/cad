# Every flake input, classified, so the licence table can be generated rather than kept
# by hand — and so adding an input without saying what it is fails `nix flake check`.
#
# A package's licence is read off its `meta`. That only works for inputs that become
# derivations; the FreeCAD addons and OpenSCAD libraries are consumed as plain source
# trees handed to `--module-path` or `OPENSCADPATH`, so they have no `meta` to read and
# have to be declared. Keep the declaration honest: read it off the input's own LICENSE
# or manifest, not from memory.
#
# `nix/lib` is a blueprint directory: it imports this as a *function*, applied to its
# special args, and exposes the result as `flake.lib`. Hence the ignored argument — the
# consumers in nix/packages and nix/checks call it with `{ }`.
_: {
  # Builds the repo, ends up in no output of it.
  infrastructure = [
    "nixpkgs"
    "blueprint"
    "treefmt-nix"
    # Pulled in transitively by blueprint; nothing of it reaches an output.
    "systems"
  ];

  # Inputs that nix/packages/ turns into derivations. Their licence comes from the
  # package's `meta.license`, so listing them here only says "already covered".
  packaged = [
    "freecad-mcp"
    "konnect"
  ];

  # Inputs used as source. Nothing can derive these, so they are declared.
  sources = {
    bosl2 = {
      description = "OpenSCAD library: rounded solids, attachments, threads, gears";
      license = "BSD-2-Clause";
      homepage = "https://github.com/BelfrySCAD/BOSL2";
    };
    round-anything = {
      description = "OpenSCAD library: 2D/3D rounding (polyRound)";
      license = "MIT";
      homepage = "https://github.com/Irev-Dev/Round-Anything";
    };
    gridfinity = {
      description = "FreeCAD workbench: Gridfinity storage bins";
      license = "LGPL-2.0";
      homepage = "https://github.com/Stu142/FreeCAD-Gridfinity-Workbench";
    };
    curves = {
      description = "FreeCAD workbench: NURBS curve and surface tools";
      license = "LGPL-2.0";
      homepage = "https://github.com/tomate44/CurvesWB";
    };
    kicad-stepup = {
      # Declared in its package.xml as "AGPLv3.0"; it ships no LICENSE file, so the
      # full text is not in the tree — the manifest is the only statement of it.
      description = "FreeCAD workbench: bidirectional KiCad <-> FreeCAD (ECAD/MCAD)";
      license = "AGPL-3.0";
      homepage = "https://github.com/easyw/kicadStepUpMod";
    };
  };
}

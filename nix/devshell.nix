{ pkgs, inputs, ... }:
let
  # Named symlinks so `include <BOSL2/std.scad>` etc. resolve via OPENSCADPATH.
  openscadLibs = pkgs.linkFarm "openscad-libs" [
    {
      name = "BOSL2";
      path = inputs.bosl2;
    }
    {
      name = "Round-Anything";
      path = inputs.round-anything;
    }
  ];

  # sca2d pins lark 0.10.0, whose installed metadata is still named `lark-parser`
  # (the old PyPI name). Current nixpkgs runs pythonMetadataCheckPhase, which does
  # `version("lark")` and fails with PackageNotFoundError. Skip that one check for
  # this old lark. `pythonPackagesExtensions` composes with sca2d's own internal
  # packageOverrides, whereas a plain `python3.override` would be replaced by it.
  # This shadows `pkgs.sca2d` in the `with pkgs;` package list below.
  inherit
    (
      (pkgs.extend (
        _: prev: {
          pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
            (_: pyprev: {
              lark = pyprev.lark.overridePythonAttrs (_: {
                dontCheckPythonMetadata = true;
              });
            })
          ];
        }
      ))
    )
    sca2d
    ;
in
pkgs.mkShellNoCC {
  name = "cad";
  packages = with pkgs; [
    # `openscad` in nixpkgs is still 2021.01, which predates the Manifold CSG backend.
    # marble-run's accelerator is a swept solid of a few hundred slabs: seconds under
    # Manifold, minutes under the old CGAL backend. Hence the unstable snapshot.
    openscad-unstable
    freecad-wayland # native Wayland; provides `freecadcmd` for `cad export`
    xvfb-run # headless rendering for `cad render/export`
    openscad-lsp # LSP: editor formatting + completion for .scad (no reliable CLI formatter exists)
    sca2d # static analyser / linter for .scad
    shellcheck # bin/cad is bash, and CLAUDE.md asks for it before every commit

    # marble-run's Python side: tools/check.py builds every part and asserts mesh
    # properties (trimesh + numpy + scipy for the hulls, networkx for mesh splitting),
    # and sim/ drops marbles through the mechanisms under pybullet.
    (python3.withPackages (
      ps: with ps; [
        numpy
        scipy
        networkx
        trimesh
        # trimesh's proximity queries (check.py's port/floor probes call
        # signed_distance) build an R-tree over the faces, and trimesh does not
        # depend on rtree itself — without it every port check dies on
        # ModuleNotFoundError rather than on anything about the geometry.
        rtree
        pybullet
      ]
    ))
  ];
  shellHook = ''
    export PRJ_ROOT="$PWD"
    export OPENSCADPATH="${openscadLibs}"
    echo "cad devshell — 'cad' (from ./bin) for project commands (new/render/export/step/gui/ls)"
    echo "OpenSCAD libs on OPENSCADPATH: BOSL2, Round-Anything"
  '';
}

{
  pkgs,
  inputs,
  perSystem,
  ...
}:
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
    # freecad-wayland plus addons and preferences; still `freecad` and `freecadcmd`.
    perSystem.self.freecad
    # No bambu-studio here on purpose: it is unfree, so Hydra never built it, and
    # putting it in the shell makes every `direnv allow` compile it from source.
    # The bambucad workbench finds it by preference or on PATH instead.
    perSystem.self.freecad-mcp # the MCP server; talks to the workbench above over XML-RPC
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
        pytest # nix/packages/bambucad/tests, which run without FreeCAD
      ]
    ))
  ];
  shellHook = ''
    export PRJ_ROOT="$PWD"
    export OPENSCADPATH="${openscadLibs}"
    echo "cad devshell — 'cad' (from ./bin) for project commands (new/render/export/step/gui/ls)"
    echo "OpenSCAD libs on OPENSCADPATH: BOSL2, Round-Anything"
    echo "FreeCAD carries the MCP workbench: start it from the 'FreeCAD MCP' toolbar, then 'freecad-mcp'"

    # Under WSLg every GL app in here — openscad's preview, freecad's viewport, sim/play.py's
    # bench — otherwise lands on Mesa's llvmpipe, which is pure software. The GPU is reachable
    # through Mesa's d3d12 Gallium driver on top of the D3D12 that /usr/lib/wsl/lib provides;
    # there is no NVIDIA Vulkan ICD installed, so zink is not an alternative here.
    #
    # MESA_D3D12_DEFAULT_ADAPTER_NAME is the one that is not obvious. Without it the driver
    # loads, takes the default adapter, finds nothing usable and dies with
    # "glx: failed to create drisw screen" — which reads like d3d12 being missing rather than
    # like the wrong GPU having been picked, and sends you looking in the wrong place.
    #
    # Guarded on the directory so the shell still opens on a machine that is not WSL. To go
    # back to software for a comparison: `GALLIUM_DRIVER= <cmd>`.
    if [ -d /usr/lib/wsl/lib ]; then
      export LD_LIBRARY_PATH="/usr/lib/wsl/lib''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      export GALLIUM_DRIVER=d3d12
      export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
      echo "GL on the GPU: Mesa d3d12 -> $MESA_D3D12_DEFAULT_ADAPTER_NAME (WSLg)"
    fi
  '';
}

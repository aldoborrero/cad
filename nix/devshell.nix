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
    # OrcaSlicer, which the slicercad workbench sends to when Bambu Studio is not
    # around. It is a fork of it, free software and substitutable, so unlike
    # bambu-studio — unfree, never built by Hydra, and a source build for anyone
    # running `direnv allow` — it can just be here.
    orca-slicer
    # The full `kicad`, not `kicad-small`: the difference is the packages3d library, and
    # that library is the whole point of the kicadStepUp workbench above — it is what an
    # imported .kicad_pcb resolves its component models against. Free software and cached,
    # so it substitutes rather than building.
    kicad
    # The KiCad MCP server, next to the FreeCAD one. Register it with an MCP client
    # yourself — do NOT run `konnect` bare in a terminal: with a TTY it takes that as
    # "install" and writes skills, agents and a PreToolUse hook into ~/.claude, and the
    # hook it writes hardcodes this package's /nix/store path, which dies on the next
    # rebuild. `konnect uninstall` reverts it. With stdin piped it starts the server,
    # which is how an MCP client invokes it.
    perSystem.self.konnect
    perSystem.self.freecad-mcp # the MCP server; talks to the workbench above over XML-RPC
    # LCSC/JLCPCB parts search, pricing and BOM checks over MCP. API-backed tools need
    # JLCPCB_APP_ID / JLCPCB_API_KEY / JLCPCB_API_SECRET exported by the user; the
    # server starts and lists tools without them.
    perSystem.self.jlcpcb-mcp
    # The keyless counterpart (Eyalm321/jlcpcb-mcp, binary renamed to avoid the PATH
    # collision): parametric parts search over a local jlcparts catalog — a ~1.9 GB
    # SQLite it builds under ~/.local/share/jlcpcb-mcp on first use — plus live LCSC
    # stock/pricing from an unofficial endpoint; its own official-API tools (quoting,
    # ordering) want JLCPCB_APP_ID / JLCPCB_ACCESS_KEY / JLCPCB_SECRET_KEY.
    perSystem.self.jlcpcb-parts-mcp
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
        pytest # nix/packages/slicercad/tests, which run without FreeCAD
      ]
    ))
  ];
  shellHook = ''
    export PRJ_ROOT="$PWD"
    # The repo's own lib/openscad joins the bundled libraries on the search path rather
    # than being reached with `use <../../../lib/openscad/common.scad>`. A relative path
    # would depend on how deep a project sits — projects/<name>/<tool>/ is three levels,
    # but a nested piece like marble-run's ramps/ is more — so it would be wrong for
    # exactly the projects that grow. It is $PRJ_ROOT and not a store path so that an
    # edit to common.scad takes effect without re-entering the shell.
    export OPENSCADPATH="${openscadLibs}:$PWD/lib/openscad"
    # KiCad's wrapper exports KICAD10_*_DIR only for its own binaries; anything else that
    # needs the bundled libraries — konnect above all, which otherwise falls back to
    # probing FHS paths (/usr/share/kicad ...) that do not exist under Nix — must get
    # them from the shell. Konnect reads them per call but inherits them at MCP-server
    # launch, so the Claude session (and thus the server) must start inside this shell.
    # No KICAD10_TEMPLATE_DIR: the wrapper builds that dir out of an internal derivation
    # the package does not expose, and konnect's library discovery never asks for it.
    export KICAD10_SYMBOL_DIR="${pkgs.kicad.libraries.symbols}/share/kicad/symbols"
    export KICAD10_FOOTPRINT_DIR="${pkgs.kicad.libraries.footprints}/share/kicad/footprints"
    export KICAD10_3DMODEL_DIR="${pkgs.kicad.libraries.packages3d}/share/kicad/3dmodels"
    echo "cad devshell — 'cad' (from ./bin) for project commands (new/render/export/step/gui/ls)"
    echo "OpenSCAD libs on OPENSCADPATH: BOSL2, Round-Anything, and this repo's lib/openscad"
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

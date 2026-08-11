# The addon's Python, checked the same three ways as slicercad's: ruff for the lint
# rules in pyproject.toml, mypy in strict mode, and the tests that run without
# FreeCAD.
#
# With one addition. Two of the theme tests read the *installed* FreeCAD's
# stylesheet directory through FREECAD_STYLESHEETS, so that "this theme defines
# every token FreeCAD.qss asks for" is a claim about the FreeCAD in this flake
# rather than about a copy of its token list pasted in here. It costs nothing —
# freecad is in the devshell already — and it is the only way this check can notice
# upstream adding a token.
{ pkgs, ... }:
pkgs.runCommand "fusionlook-python"
  {
    nativeBuildInputs = [
      pkgs.ruff
      pkgs.mypy
      (pkgs.python3.withPackages (ps: [
        ps.pytest
        # FreeCAD embeds PyYAML and the addon reads theme files with it, for the
        # same reason FreeCAD does: YAML::Load is what StyleParameters uses.
        ps.pyyaml
      ]))
    ];
    FREECAD_STYLESHEETS = "${pkgs.freecad-wayland}/share/Gui/Stylesheets";
  }
  ''
    cp -r ${../packages/fusionlook} source
    chmod -R u+w source
    cd source

    ruff check .
    ruff format --check .
    # HOME so mypy's cache does not try to write into a read-only /homeless-shelter.
    HOME=$TMPDIR mypy .
    python -m pytest -q tests

    touch $out
  ''

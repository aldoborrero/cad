# The addon's Python, checked three ways by `nix flake check`: ruff for the lint
# rules in pyproject.toml, mypy in strict mode, and the tests that run without
# FreeCAD. Scoped to nix/packages/slicercad on purpose — the rest of the repo's
# Python (marble-run's sim and tools) has never been held to this.
{ pkgs, ... }:
pkgs.runCommand "slicercad-python"
  {
    nativeBuildInputs = [
      pkgs.ruff
      pkgs.mypy
      (pkgs.python3.withPackages (ps: [ ps.pytest ]))
    ];
  }
  ''
    cp -r ${../packages/slicercad} source
    chmod -R u+w source
    cd source

    ruff check .
    ruff format --check .
    # HOME so mypy's cache does not try to write into a read-only /homeless-shelter.
    HOME=$TMPDIR mypy .
    python -m pytest -q tests

    touch $out
  ''

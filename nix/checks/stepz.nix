# The stepZ module's Python, checked the same three ways as slicercad's: ruff for the
# lint rules in pyproject.toml, mypy in strict mode, and the tests, which stand in for
# ImportGui and so run without FreeCAD.
{ pkgs, ... }:
pkgs.runCommand "stepz-python"
  {
    nativeBuildInputs = [
      pkgs.ruff
      pkgs.mypy
      (pkgs.python3.withPackages (ps: [ ps.pytest ]))
    ];
  }
  ''
    cp -r ${../packages/stepz} source
    chmod -R u+w source
    cd source

    ruff check .
    ruff format --check .
    # Init.py is a startup script FreeCAD runs, not a module: it is checked by ruff but
    # not by mypy, which would have to model the FreeCAD-injected environment to help.
    HOME=$TMPDIR mypy module/stepZ.py tests
    python -m pytest -q tests

    touch $out
  ''

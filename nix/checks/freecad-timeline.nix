# The Timeline addon's Python, checked the same three ways as slicercad's and
# fusionlook's: ruff for the rules in its pyproject.toml, mypy strict, and pytest.
#
# Two differences, both recorded rather than hidden.
#
# ruff and mypy run over the addon's own source only. It arrived from another repo
# without a typing gate, and the tests are unannotated — 846 of the 918 errors that
# first pass reported were `no-untyped-def` and the `no-untyped-call` each one
# causes. The exclusion list lives in pyproject.toml and names every module still
# outside the gate, so the debt shrinks visibly instead of being waved through.
#
# And the suite has three tiers: Qt-free logic, the widget layer under PySide6
# offscreen, and a tier that imports the real FreeCAD. Each skips itself through
# `pytest.importorskip` when its dependency is absent, so handing it both freecad and
# pyside6 is what turns the whole thing on — FreeCAD's Python module is a plain .so
# in $out/lib, and putting that on PYTHONPATH is enough to import it with no display.
{ pkgs, ... }:
let
  python = pkgs.python3.withPackages (ps: [
    ps.pytest
    ps.pyside6
  ]);
in
pkgs.runCommand "freecad-timeline-python"
  {
    nativeBuildInputs = [
      pkgs.ruff
      pkgs.mypy
      python
    ];
  }
  ''
    cp -r ${../packages/freecad-timeline} source
    chmod -R u+w source
    cd source

    ruff check .
    ruff format --check freecad_timeline InitGui.py
    HOME=$TMPDIR mypy .

    export QT_QPA_PLATFORM=offscreen
    # FreeCAD writes its user config on import, and a builder has no $HOME.
    export HOME=$TMPDIR
    export PYTHONPATH="${pkgs.freecad}/lib''${PYTHONPATH:+:$PYTHONPATH}"
    python -m pytest -q -p no:cacheprovider

    touch $out
  ''

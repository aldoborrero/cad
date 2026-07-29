"""Read lib.scad's own parameters, instead of copying them into Python.

Every number a simulation compares against is a CAD dimension, and copying them by hand is
how the two catcher scripts quietly stopped measuring the catcher: their block stand-in was
still pinned to a Ø112 pedestal with a 26 mm dock, from a generation of the part that no
longer ships. Run either of them today against the shipped wedge and the marble is released
outside the bowl, so every case reads "escapes" and the part looks broken when it is not.

OpenSCAD will dump an `echo()` to a file with `-o something.echo`, so the numbers can just
be asked for:

    from params import params
    P = params(dock="catch_dock_h()", exit_z="catch_exit_z()", d="CATCH_D")
    P["dock"]  ->  12.0

Names on the left are what you want to call them in Python; the right-hand side is any
OpenSCAD expression valid after `include <lib.scad>` -- a parameter, a function call, a
vector. Overrides go in as `-D` flags, so a variant can be measured without editing
anything:

    params(dock="catch_dock_h()", _overrides={"CATCH_DOCK_H": 26})
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIB = ROOT / "lib.scad"

_LINE = re.compile(r'ECHO:\s*"@@(?P<k>[^=]+)=(?P<v>.*)"\s*$')


def openscad():
    exe = os.environ.get("OPENSCAD") or shutil.which("openscad")
    if not exe:
        raise RuntimeError("no openscad on PATH -- run inside `nix develop`, or set $OPENSCAD")
    return exe


def params(_overrides=None, _source=None, **exprs):
    """Evaluate OpenSCAD expressions against lib.scad and return them as Python values.

    `_source` includes a different file instead. A piece that overrides library parameters
    does so by `include`-ing lib.scad and then reassigning -- catchers/catcher_hape.scad is
    the example -- so including *that* file is how you read the values the piece actually
    uses, rather than copying its override list into Python and letting the two drift.
    """
    if not exprs:
        return {}
    body = [f'include <{_source or LIB}>']
    for name, expr in exprs.items():
        # str() around the value so vectors survive as one token, and a marker so the
        # parse cannot be confused by anything else OpenSCAD decides to print
        body.append(f'echo(str("@@{name}=", {expr}));')

    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "params.scad"
        out = pathlib.Path(tmp) / "params.echo"
        src.write_text("\n".join(body) + "\n")
        cmd = [openscad()]
        for k, v in (_overrides or {}).items():
            cmd += ["-D", f"{k}={json.dumps(v)}"]
        cmd += ["-o", str(out), str(src)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if not out.exists():
            raise RuntimeError("openscad produced no echo output:\n"
                               + (r.stderr or r.stdout)[-800:])
        text = out.read_text()

    got = {}
    for line in text.splitlines():
        m = _LINE.match(line.strip())
        if not m:
            continue
        raw = m.group("v").strip()
        try:
            got[m.group("k")] = json.loads(raw)
        except ValueError:
            got[m.group("k")] = raw

    missing = set(exprs) - set(got)
    if missing:
        raise RuntimeError(f"lib.scad did not echo: {', '.join(sorted(missing))}")
    return got


if __name__ == "__main__":
    import pprint
    pprint.pp(params(
        marble="MARBLE_D", side="SIDE", height="HEIGHT", mini="MINI_H",
        catch_d="CATCH_D", catch_h="CATCH_H", catch_dock="catch_dock_h()",
        catch_exit_z="catch_exit_z()", catch_shape="CATCH_SHAPE",
        see_pivot="see_pivot()", see_cup="[SEE_CUP_C, SEE_CUP_L, SEE_CUP_W, SEE_CUP_T]",
        see_cw="SEE_CW", see_up="SEE_UP", see_down="SEE_DOWN",
    ))

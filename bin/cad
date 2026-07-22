#!/usr/bin/env bash
# cad — manage CAD projects in this monorepo (OpenSCAD + FreeCAD)
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || echo "${PRJ_ROOT:-$PWD}")"

die() {
  echo "cad: $*" >&2
  exit 1
}

usage() {
  cat >&2 <<'EOF'
cad — manage CAD projects

  cad ls                          list all projects
  cad new openscad|freecad NAME   scaffold a new project from the template
  cad render NAME [VIEW]          OpenSCAD PNG preview (VIEW: iso|fit|top|front|side)
  cad export NAME                 export STL (+3MF) into the project's exports/
  cad step NAME                   export STEP via FreeCAD (best-effort, OpenSCAD projects)
  cad gui NAME                    open the project (OpenSCAD GUI / FreeCAD)
EOF
}

tool_of() {
  local name="$1" t
  for t in openscad freecad; do
    [ -d "$root/$t/$name" ] && {
      echo "$t"
      return 0
    }
  done
  return 1
}

scad_file() { echo "$root/openscad/$1/$1.scad"; }

view_args() {
  case "$1" in
  iso) echo "--projection=p --camera=0,0,0,58,0,215,0" ;;
  fit) echo "--projection=p --camera=0,0,0,60,0,25,0" ;;
  top) echo "--projection=o --camera=0,0,0,0,0,0,0" ;;
  front) echo "--projection=o --camera=0,0,0,90,0,0,0" ;;
  side) echo "--projection=o --camera=0,0,0,90,0,90,0" ;;
  *) die "unknown view: $1 (iso|fit|top|front|side)" ;;
  esac
}

cmd_ls() {
  local t d b
  for t in openscad freecad; do
    [ -d "$root/$t" ] || continue
    for d in "$root/$t"/*/; do
      [ -d "$d" ] || continue
      b="$(basename "$d")"
      case "$b" in _template | lib) continue ;; esac
      echo "$t/$b"
    done
  done
}

cmd_new() {
  local tool="${1:-}" name="${2:-}"
  { [ -n "$tool" ] && [ -n "$name" ]; } || die "usage: cad new openscad|freecad NAME"
  case "$tool" in openscad | freecad) ;; *) die "tool must be openscad or freecad" ;; esac
  local dest="$root/$tool/$name"
  [ -e "$dest" ] && die "$tool/$name already exists"
  cp -r "$root/$tool/_template" "$dest"
  if [ "$tool" = openscad ] && [ -f "$dest/model.scad" ]; then
    mv "$dest/model.scad" "$dest/$name.scad"
  fi
  mkdir -p "$dest/exports"
  echo "created $tool/$name"
}

cmd_render() {
  local name="${1:-}" view="${2:-iso}" f out
  [ -n "$name" ] || die "usage: cad render NAME [VIEW]"
  f="$(scad_file "$name")"
  [ -f "$f" ] || die "no OpenSCAD project: openscad/$name/$name.scad"
  out="$root/openscad/$name/exports"
  mkdir -p "$out"
  # shellcheck disable=SC2046
  xvfb-run -a openscad -o "$out/$name-$view.png" \
    --imgsize=1200,1000 --colorscheme=Tomorrow --viewall --autocenter \
    $(view_args "$view") "$f"
  echo "wrote $out/$name-$view.png"
}

cmd_export() {
  local name="${1:-}" f out
  [ -n "$name" ] || die "usage: cad export NAME"
  f="$(scad_file "$name")"
  [ -f "$f" ] || die "no OpenSCAD project: openscad/$name/$name.scad"
  out="$root/openscad/$name/exports"
  mkdir -p "$out"
  xvfb-run -a openscad -o "$out/$name.stl" "$f"
  echo "wrote $out/$name.stl"
  if xvfb-run -a openscad -o "$out/$name.3mf" "$f" 2>/dev/null; then
    echo "wrote $out/$name.3mf"
  else
    echo "cad: 3MF export not supported by this OpenSCAD build (skipped)" >&2
  fi
}

cmd_step() {
  local name="${1:-}" f out csg py
  [ -n "$name" ] || die "usage: cad step NAME"
  f="$(scad_file "$name")"
  [ -f "$f" ] || die "no OpenSCAD project: openscad/$name/$name.scad"
  out="$root/openscad/$name/exports"
  mkdir -p "$out"
  csg="$out/$name.csg"
  xvfb-run -a openscad -o "$csg" "$f"
  py="$(mktemp --suffix=.py)"
  cat >"$py" <<PY
import os, importCSG, FreeCAD, Import
importCSG.open(os.environ["CAD_CSG"])
doc = FreeCAD.ActiveDocument
Import.export(list(doc.Objects), os.environ["CAD_STEP"])
PY
  CAD_CSG="$csg" CAD_STEP="$out/$name.step" freecadcmd "$py" ||
    die "FreeCAD STEP conversion failed (hull()/minkowski() may not convert cleanly)"
  rm -f "$py"
  echo "wrote $out/$name.step"
}

cmd_gui() {
  local name="${1:-}" t file
  [ -n "$name" ] || die "usage: cad gui NAME"
  t="$(tool_of "$name")" || die "no such project: $name"
  case "$t" in
  openscad) openscad "$(scad_file "$name")" & ;;
  freecad)
    file="$(find "$root/freecad/$name" -maxdepth 1 -name '*.FCStd' | head -1)"
    [ -n "$file" ] || die "no .FCStd in freecad/$name"
    freecad "$file" &
    ;;
  esac
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
  ls) cmd_ls ;;
  new) cmd_new "$@" ;;
  render) cmd_render "$@" ;;
  export) cmd_export "$@" ;;
  step) cmd_step "$@" ;;
  gui) cmd_gui "$@" ;;
  "" | -h | --help | help) usage ;;
  *)
    usage
    exit 1
    ;;
  esac
}

main "$@"

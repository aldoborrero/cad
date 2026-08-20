#!/usr/bin/env python3
"""Merge a declared set of preferences into FreeCAD's user.cfg, in place.

Only the given keys are touched; everything else in the file is left alone. A
missing file is created, which is the first-run seeding case.

  --pack FILE       a FreeCAD preference pack (share/Gui/PreferencePacks/*/*.cfg)
  --set FILE        JSON, {"Group/Sub/Group": {"Key": {"type": t, "value": v}}},
                    t one of bool/int/uint/float/text/color
  --exclusive GROUP a group this repo owns outright: after the declared keys are
                    written, every other key sitting directly in it is deleted

Packs are merged first, so --set always wins. `color` takes "#RRGGBB" or
"#RRGGBBAA" and packs it as FreeCAD stores colours: one uint, 0xRRGGBBAA.

Why --exclusive exists. Merging alone cannot express "this key should not be
here", so anything ever written into a group outlives whatever put it there: a
key this repo used to declare and dropped, or a key an addon wrote and did not
clean up. That is not hypothetical — removing the Ribbon addon left 56 toolbars
switched off in `BaseApp/MainWindow/Toolbars`, and FreeCAD came up with no
toolbar row at all and nothing on screen to explain why. The same shape bit
twice more with placement keys in MenuBarLeft/MenuBarRight, where a stale entry
silently won because ToolBarManager reads the left area before the right one.

An exclusive group is therefore declarative in the full sense: what the repo says
is what is there. Do not mark a group exclusive when the user is expected to keep
their own keys in it — `BaseApp/Preferences/View` holds this repo's colours *and*
a pile of personal settings, and pruning it would throw the second away.
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

SKELETON = '<FCParameters>\n  <FCParamGroup Name="Root"/>\n</FCParameters>\n'
PROLOGUE = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'

TAGS = {
    "bool": "FCBool",
    "int": "FCInt",
    "uint": "FCUInt",
    "float": "FCFloat",
    "text": "FCText",
    "color": "FCUInt",
}


def encode(kind, value):
    if kind == "bool":
        return "1" if value else "0"
    if kind in ("int", "uint"):
        return str(int(value))
    if kind == "float":
        return f"{float(value):.12f}"  # FreeCAD's own precision, so no spurious diffs
    if kind == "text":
        return str(value)
    if kind == "color":
        digits = str(value).lstrip("#")
        if len(digits) == 6:
            digits += "FF"
        if len(digits) != 8:
            raise ValueError(f"colour must be #RRGGBB or #RRGGBBAA, got {value!r}")
        r, g, b, a = (int(digits[i : i + 2], 16) for i in (0, 2, 4, 6))
        return str((r << 24) | (g << 16) | (b << 8) | a)
    raise ValueError(f"unknown type {kind!r}")


def group(node, names):
    """Walk down to a parameter group, creating missing ones."""
    for name in names:
        child = node.find(f"FCParamGroup[@Name='{name}']")
        if child is None:
            child = ET.SubElement(node, "FCParamGroup", {"Name": name})
        node = child
    return node


def put(node, tag, name, encoded):
    # Drop a same-named key of another type, or FreeCAD reads the stale first one.
    for other in list(node):
        if (
            other.tag != "FCParamGroup"
            and other.get("Name") == name
            and other.tag != tag
        ):
            node.remove(other)
    el = node.find(f"{tag}[@Name='{name}']")
    if el is None:
        el = ET.SubElement(node, tag, {"Name": name})
    if tag == "FCText":
        el.attrib.pop("Value", None)
        el.text = encoded
    else:
        el.text = None
        el.set("Value", encoded)


def prune(node, keep):
    """Delete every key sitting directly in `node` that is not in `keep`.

    Subgroups are left alone: a group is claimed for its own keys, not for
    everything underneath it, so marking `BaseApp/MainWindow/Toolbars` exclusive
    says nothing about a `Toolbars/Something` group that may appear later.
    """
    removed = []
    for child in list(node):
        if child.tag != "FCParamGroup" and child.get("Name") not in keep:
            node.remove(child)
            removed.append(child.get("Name"))
    return removed


def leaves(node, path=()):
    """Yield (group path, tag, name, raw value) for every non-group element."""
    for child in node:
        if child.tag == "FCParamGroup":
            yield from leaves(child, path + (child.get("Name"),))
        else:
            raw = child.text if child.tag == "FCText" else child.get("Value")
            yield path, child.tag, child.get("Name"), raw or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="append", default=[], metavar="FILE")
    ap.add_argument("--set", dest="sets", action="append", default=[], metavar="FILE")
    ap.add_argument(
        "--exclusive",
        action="append",
        default=[],
        metavar="GROUP",
        help="group this repo owns outright; undeclared keys in it are removed",
    )
    ap.add_argument("target", metavar="USER_CFG")
    args = ap.parse_args()

    try:
        root = ET.parse(args.target).getroot()
    except (FileNotFoundError, ET.ParseError):
        root = ET.fromstring(SKELETON)
    target_root = group(root, ["Root"])

    # Every key any source of ours writes, by group path, so that --exclusive prunes
    # what nobody declared rather than what merely came from the other flag.
    owned = {}

    for path in args.pack:
        pack = ET.parse(path).getroot()
        pack_root = pack.find("FCParamGroup[@Name='Root']")
        if pack_root is None:
            print(f"{sys.argv[0]}: {path} has no Root group, skipped", file=sys.stderr)
            continue
        for groups, tag, name, raw in leaves(pack_root):
            put(group(target_root, groups), tag, name, raw)
            owned.setdefault("/".join(groups), set()).add(name)

    for path in args.sets:
        with open(path) as fh:
            declared = json.load(fh)
        for group_path, keys in declared.items():
            node = group(target_root, group_path.split("/"))
            for name, spec in keys.items():
                kind = spec["type"]
                put(node, TAGS[kind], name, encode(kind, spec["value"]))
            owned.setdefault(group_path, set()).update(keys)

    # After every source has had its say, so that a key declared by a pack and not
    # by --set still counts as ours rather than being pruned as a leftover.
    for group_path in args.exclusive:
        node = group(target_root, group_path.split("/"))
        gone = prune(node, owned.get(group_path, set()))
        if gone:
            print(
                f"{os.path.basename(sys.argv[0])}: {group_path}: dropped "
                f"{len(gone)} undeclared key(s): {', '.join(sorted(gone))}",
                file=sys.stderr,
            )

    ET.indent(root, space="  ")
    tmp = args.target + ".new"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(PROLOGUE)
        fh.write(ET.tostring(root, encoding="unicode"))
        fh.write("\n")
    os.replace(tmp, args.target)


if __name__ == "__main__":
    main()

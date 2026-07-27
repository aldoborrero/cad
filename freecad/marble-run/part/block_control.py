"""block-control (White) — green channels + an orange control knob on a side face
(quadri-plot ControlBlock = ExitGreen + knobs)."""

import FreeCAD as App
import Part

import lib

NAME = "block-control"


def build():
    s = lib.carve(
        lib.HEIGHT, lib.ch_top(), lib.ex_side(60, 0), lib.ex_bottom(), lib.ex_across()
    )
    # control knob: axle + disc, built +Z then oriented onto the +Y face
    knob = Part.makeCylinder(4, 3).fuse(Part.makeCylinder(13, 4, App.Vector(0, 0, 3)))
    knob.rotate(lib._O, lib._Y, 90)  # -> +X
    knob.translate(App.Vector(lib.SIDE / 2, 0, lib.HEIGHT * 2 / 3))
    knob.rotate(lib._O, lib._Z, 90)  # -> +Y face
    return s.fuse(knob).removeSplitter()

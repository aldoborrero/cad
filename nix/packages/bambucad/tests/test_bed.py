from freecad.bambucad import bed, fit


def test_the_plate_is_drawn_around_the_model_origin():
    # Not around Bambu's own (0,0) corner: parts are modelled around the origin, and
    # moving them to suit the slicer would mean writing print layout into the model.
    assert bed.rectangle(fit.profile("A1 mini")) == [
        (-90, -90, bed.GROUND_Z),
        (90, -90, bed.GROUND_Z),
        (90, 90, bed.GROUND_Z),
        (-90, 90, bed.GROUND_Z),
    ]


def test_the_plate_sits_just_below_zero_like_bambu_s():
    # PartPlate.cpp: static const float GROUND_Z = -0.03f, to avoid z-fighting
    # with anything resting on the plate.
    assert bed.GROUND_Z == -0.03


def test_excluded_zones_move_with_the_plate():
    zones = bed.zones(fit.profile("256"))

    assert len(zones) == 2
    assert zones[0] == [
        (-128, -128, bed.GROUND_Z),
        (-100, -128, bed.GROUND_Z),
        (-100, -100, bed.GROUND_Z),
        (-128, -100, bed.GROUND_Z),
    ]


def test_a_clean_bed_has_no_zones_to_draw():
    assert bed.zones(fit.profile("A1 mini")) == []


def test_the_grid_steps_every_ten_millimetres_like_bambu_s():
    # PartPlate.cpp calc_gridlines: 10 mm steps, every fifth line bolder.
    thin, bold = bed.grid(fit.profile("A1 mini"))

    vertical_bold = sorted({a[0] for a, b in bold if a[0] == b[0]})
    assert vertical_bold == [-90, -40, 10, 60]
    assert len(thin) + len(bold) == 19 * 2


def test_a_colour_reads_as_the_floats_coin_wants():
    assert bed.parse_colour("#444747") == (
        0.26666666666666666,
        0.2784313725490196,
        0.2784313725490196,
    )


def test_colours_fall_back_to_the_defaults_and_can_be_overridden():
    assert bed.colours({})["plate"] == bed.DEFAULT_COLOURS["plate"]
    assert bed.colours({"plate": "#102030"})["plate"] == "#102030"
    assert bed.colours({"plate": "nonsense"})["plate"] == bed.DEFAULT_COLOURS["plate"]


def test_a_colour_button_value_becomes_a_hex_string():
    # Gui::PrefColorButton stores one unsigned int packed as 0xRRGGBBAA.
    assert bed.colour_from_uint(0x444747FF) == "#444747"
    assert bed.colour_from_uint(0) == "#000000"

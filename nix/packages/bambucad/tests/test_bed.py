from freecad.bambucad import bed, fit


def test_the_plate_outline_runs_from_the_origin_corner():
    # Bambu's own profiles put (0,0) at the front-left corner of the plate.
    assert bed.rectangle(fit.profile("A1 mini")) == [
        (0, 0, 0),
        (180, 0, 0),
        (180, 180, 0),
        (0, 180, 0),
    ]


def test_each_excluded_zone_becomes_its_own_rectangle():
    zones = bed.zones(fit.profile("256"))

    assert len(zones) == 2
    assert zones[0] == [(0, 0, 0), (28, 0, 0), (28, 28, 0), (0, 28, 0)]


def test_a_clean_bed_has_no_zones_to_draw():
    assert bed.zones(fit.profile("A1 mini")) == []

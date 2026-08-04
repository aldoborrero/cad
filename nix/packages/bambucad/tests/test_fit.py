from freecad.bambucad import fit


def test_a_part_well_inside_the_bed_raises_nothing():
    bed = fit.Bed(width=180, depth=180, exclusions=[])
    parts = [fit.Part(name="cradle", xmin=20, ymin=20, xmax=60, ymax=50)]

    assert fit.check(bed, parts) == []


def test_a_part_hanging_over_the_edge_is_reported():
    bed = fit.Bed(width=180, depth=180, exclusions=[])
    parts = [fit.Part(name="ramp", xmin=150, ymin=20, xmax=195, ymax=60)]

    [issue] = fit.check(bed, parts)

    assert issue.kind == "outside"
    assert issue.part == "ramp"


def test_a_part_over_an_excluded_zone_is_reported():
    # The 28x28 corner every 256 mm Bambu bed loses to the purge cutout.
    bed = fit.Bed(
        width=256, depth=256, exclusions=[fit.Box(xmin=0, ymin=0, xmax=28, ymax=28)]
    )
    parts = [fit.Part(name="clip", xmin=10, ymin=10, xmax=40, ymax=40)]

    [issue] = fit.check(bed, parts)

    assert issue.kind == "excluded"
    assert issue.part == "clip"


def test_two_parts_sharing_ground_are_reported_once():
    bed = fit.Bed(width=180, depth=180, exclusions=[])
    parts = [
        fit.Part(name="cradle", xmin=10, ymin=10, xmax=50, ymax=50),
        fit.Part(name="clip", xmin=40, ymin=40, xmax=80, ymax=80),
    ]

    [issue] = fit.check(bed, parts)

    assert issue.kind == "overlap"
    assert {issue.part, issue.other} == {"cradle", "clip"}


def test_a_256_machine_carries_bambu_s_own_excluded_zone():
    # From fdm_bbl_3dp_001_common.json: a 28x28 corner and an 8 mm left strip.
    bed = fit.profile("X1 Carbon")

    assert (bed.width, bed.depth) == (256, 256)
    # Each machine overrides the common profile's zones with its own smaller one.
    assert bed.exclusions == [fit.Box(xmin=0, ymin=0, xmax=18, ymax=28)]


def test_the_a1_mini_profile_has_no_excluded_zones():
    bed = fit.profile("A1 mini")

    assert (bed.width, bed.depth) == (180, 180)
    assert bed.exclusions == []


# The two below guard the strict-inequality choice in _overlap and check. They pass
# as written; they exist so a later refactor cannot quietly turn < into <=.


def test_a_part_flush_with_the_bed_edge_is_inside():
    bed = fit.Bed(width=180, depth=180, exclusions=[])
    parts = [fit.Part(name="edge", xmin=0, ymin=0, xmax=180, ymax=180)]

    assert fit.check(bed, parts) == []


def test_parts_touching_edge_to_edge_do_not_overlap():
    bed = fit.Bed(width=180, depth=180, exclusions=[])
    parts = [
        fit.Part(name="left", xmin=10, ymin=10, xmax=50, ymax=50),
        fit.Part(name="right", xmin=50, ymin=10, xmax=90, ymax=50),
    ]

    assert fit.check(bed, parts) == []


def test_each_kind_of_issue_reads_as_a_sentence():
    assert (
        fit.describe(fit.Issue(kind="outside", part="ramp"))
        == "ramp lies outside the bed"
    )
    assert (
        fit.describe(fit.Issue(kind="excluded", part="clip"))
        == "clip sits on an excluded zone"
    )
    assert (
        fit.describe(fit.Issue(kind="overlap", part="cradle", other="clip"))
        == "cradle overlaps clip"
    )


def test_the_offset_moves_the_model_origin_to_the_middle_of_the_plate():
    # Everything — bed drawing, fit check, export — uses this one vector, so the
    # document never has to be touched to lay parts out.
    assert fit.offset(fit.profile("X1 Carbon")) == (128, 128)
    assert fit.offset(fit.profile("A1 mini")) == (90, 90)


def test_a_part_around_the_model_origin_lands_mid_plate():
    part = fit.Part(name="mount", xmin=-10, ymin=-20, xmax=10, ymax=20)

    moved = fit.to_plate(part, fit.profile("X1 Carbon"))

    assert (moved.xmin, moved.xmax) == (118, 138)
    assert (moved.ymin, moved.ymax) == (108, 148)
    assert moved.name == "mount"


def test_every_printer_bambu_ships_is_in_the_table():
    names = fit.profile_names()

    assert len(names) == 14
    assert names[:2] == ["A1", "A1 mini"]
    assert "P1S" in names


def test_profiles_carry_the_printable_height():
    # A1 mini and A1 state their own; P1S and X1C inherit 250 from
    # fdm_machine_common. The 256 profile covers all three, so it takes the
    # smallest: claiming a part fits when it does not costs a failed print.
    assert fit.profile("A1 mini").height == 180
    assert fit.profile("X1 Carbon").height == 250
    assert fit.profile("A1").height == 256


def test_a_part_taller_than_the_printer_is_reported():
    # The P1S reaches 250 mm. Saying "all fit" about a 300 mm tower is the kind of
    # reassurance you only discover is wrong hours into a print.
    bed = fit.profile("P1S")
    parts = [fit.Part(name="torre", xmin=50, ymin=50, xmax=100, ymax=100, zmax=300)]

    [issue] = fit.check(bed, parts)

    assert issue.kind == "too tall"
    assert fit.describe(issue) == "torre is 300 mm tall, the printer reaches 250"


def test_a_part_within_the_height_is_quiet():
    bed = fit.profile("P1S")
    parts = [fit.Part(name="baja", xmin=50, ymin=50, xmax=100, ymax=100, zmax=249)]

    assert fit.check(bed, parts) == []

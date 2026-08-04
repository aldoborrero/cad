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


def test_the_256_profile_carries_bambu_s_two_excluded_zones():
    # From fdm_bbl_3dp_001_common.json: a 28x28 corner and an 8 mm left strip.
    bed = fit.profile("256")

    assert (bed.width, bed.depth) == (256, 256)
    assert fit.Box(xmin=0, ymin=0, xmax=28, ymax=28) in bed.exclusions
    assert fit.Box(xmin=0, ymin=28, xmax=8, ymax=256) in bed.exclusions


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

import math

from freecad.slicercad import orient

# A stress tensor as FreeCAD's result object stores it, component by component:
# (xx, yy, zz, xy, xz, yz). 10 MPa of pure tension along X.
PULL_ALONG_X = (10.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_layers_lying_across_the_pull_take_all_of_it() -> None:
    # Printed upright, so the layer planes are perpendicular to the load: every bit
    # of that tension is trying to peel one layer off the next.
    assert orient.normal_stress(PULL_ALONG_X, build=(1.0, 0.0, 0.0)) == 10.0


def test_layers_lying_along_the_pull_take_none_of_it() -> None:
    # Printed flat: the load runs within the layers, the interlayer welds see nothing.
    assert orient.normal_stress(PULL_ALONG_X, build=(0.0, 0.0, 1.0)) == 0.0


def test_a_forty_five_degree_build_takes_half() -> None:
    # n^T sigma n with n at 45 degrees to the pull is sigma cos^2(45) = sigma / 2.
    root = math.sqrt(0.5)

    assert math.isclose(
        orient.normal_stress(PULL_ALONG_X, build=(root, 0.0, root)), 5.0
    )


def test_the_build_vector_need_not_be_a_unit_vector() -> None:
    # It arrives from a face normal or from the slicer, and neither promises a length.
    assert orient.normal_stress(PULL_ALONG_X, build=(7.0, 0.0, 0.0)) == 10.0


def test_shear_contributes_through_its_two_directions() -> None:
    # Pure shear in XY, built along the diagonal of that plane: n^T sigma n picks up
    # 2 * n_x * n_y * sigma_xy, which for a 45 degree diagonal is the shear itself.
    shear = (0.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    root = math.sqrt(0.5)

    assert math.isclose(orient.normal_stress(shear, build=(root, root, 0.0)), 4.0)


def test_a_build_direction_of_zero_length_is_refused() -> None:
    # Rather than divide by zero and report a plausible number.
    try:
        orient.normal_stress(PULL_ALONG_X, build=(0.0, 0.0, 0.0))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# Three nodes: pulled along X, pulled along Z, and squeezed along X.
FIELD = [
    (10.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.0, 4.0, 0.0, 0.0, 0.0),
    (-30.0, 0.0, 0.0, 0.0, 0.0, 0.0),
]


def test_the_peak_is_the_worst_node_not_the_average() -> None:
    # Printed upright: node 1 puts 10 across the welds, node 2 nothing, node 3 is
    # in compression. A part fails where it is worst, so 10 is the answer.
    assert orient.peak_normal_stress(FIELD, build=(1.0, 0.0, 0.0)) == 10.0


def test_compression_does_not_count_as_a_peak() -> None:
    # Squeezing layers together does not separate them. With every node in
    # compression the interlayer welds are simply not loaded.
    squeezed = [(-30.0, 0.0, 0.0, 0.0, 0.0, 0.0)]

    assert orient.peak_normal_stress(squeezed, build=(1.0, 0.0, 0.0)) == 0.0


def test_ranking_puts_the_kindest_orientation_first() -> None:
    # Flat leaves the welds carrying 4 (node 2), upright leaves them carrying 10.
    flat = (0.0, 0.0, 1.0)
    upright = (1.0, 0.0, 0.0)

    ranked = orient.rank(FIELD, [upright, flat])

    assert [r.build for r in ranked] == [flat, upright]
    assert [r.peak for r in ranked] == [4.0, 10.0]


def test_ranking_nothing_gives_nothing() -> None:
    assert orient.rank(FIELD, []) == []

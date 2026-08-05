import math

import pytest

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
    with pytest.raises(ValueError, match="no length"):
        orient.normal_stress(PULL_ALONG_X, build=(0.0, 0.0, 0.0))


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


def test_a_field_with_a_broken_node_is_refused_not_quietly_skipped() -> None:
    # A solve that did not converge leaves NaN in the result. max() discards it
    # silently, because every comparison with NaN is false, so the peak comes back
    # a plausible number computed from the nodes that happened to survive.
    nan = float("nan")
    field = [(10.0, 0.0, 0.0, 0.0, 0.0, 0.0), (nan, 0.0, 0.0, 0.0, 0.0, 0.0)]

    with pytest.raises(ValueError, match="1 of 2"):
        orient.peak_normal_stress(field, build=(1.0, 0.0, 0.0))


def test_the_six_lists_zip_into_nodes_in_the_declared_order() -> None:
    # FreeCAD keeps NodeStressXX .. NodeStressYZ as six separate lists. Getting
    # this order wrong is silent: every number is real, just on the wrong axis.
    field = orient.field_from_lists(
        xx=[1.0, 10.0],
        yy=[2.0, 20.0],
        zz=[3.0, 30.0],
        xy=[4.0, 40.0],
        xz=[5.0, 50.0],
        yz=[6.0, 60.0],
    )

    assert field == [
        (1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        (10.0, 20.0, 30.0, 40.0, 50.0, 60.0),
    ]


def test_lists_of_different_lengths_are_refused() -> None:
    # One short list would silently truncate the field to its length, quietly
    # dropping the rest of the part from the assessment.
    with pytest.raises(ValueError, match="same length"):
        orient.field_from_lists(
            xx=[1.0, 2.0],
            yy=[1.0],
            zz=[1.0, 2.0],
            xy=[1.0, 2.0],
            xz=[1.0, 2.0],
            yz=[1.0, 2.0],
        )


def test_an_empty_result_gives_an_empty_field() -> None:
    assert orient.field_from_lists([], [], [], [], [], []) == []

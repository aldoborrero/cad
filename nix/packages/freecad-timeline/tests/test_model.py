# SPDX-License-Identifier: LGPL-2.1-or-later
"""Data-layer tests: classification, ordering, tip semantics, move planning."""

from __future__ import annotations

import pytest

from freecad_timeline import model

from .fakes import (
    FakeBody,
    FakeDocument,
    FakeFeature,
    FakeObject,
    make_simple_body,
    make_three_pads,
)

# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("type_id", "expected"),
    [
        ("PartDesign::Pad", model.KIND_SOLID),
        ("PartDesign::Pocket", model.KIND_SOLID),
        ("PartDesign::Fillet", model.KIND_SOLID),
        ("Sketcher::SketchObject", model.KIND_SKETCH),
        ("PartDesign::Plane", model.KIND_DATUM),
        ("App::Plane", model.KIND_DATUM),
        ("PartDesign::ShapeBinder", model.KIND_OTHER),
        ("Part::Box", model.KIND_OTHER),
    ],
)
def test_classify(type_id, expected):
    assert model.classify(FakeObject("X", type_id)) == expected


def test_datums_are_never_solid():
    """Part::Datum derives from Part::Feature, not PartDesign::Feature, and
    PartDesign::Feature::isDatum excludes it explicitly."""
    plane = FakeObject("DatumPlane", "PartDesign::Plane")
    assert model.is_datum(plane)
    assert not model.is_solid_feature(plane)


def test_multi_transform_child_is_not_solid():
    """Transformed::isMultiTransformChild: TransformMode index 0 with empty
    Originals means the feature lives inside a MultiTransform."""
    child = FakeFeature(
        "LinearPattern",
        "PartDesign::LinearPattern",
        TransformMode="Features",
        Originals=[],
    )
    assert model.is_multi_transform_child(child)
    assert not model.is_solid_feature(child)


def test_standalone_transformed_is_solid():
    pad = FakeFeature("Pad")
    pattern = FakeFeature(
        "LinearPattern",
        "PartDesign::LinearPattern",
        TransformMode="Features",
        Originals=[pad],
    )
    assert not model.is_multi_transform_child(pattern)
    assert model.is_solid_feature(pattern)


def test_whole_shape_transformed_is_solid():
    pattern = FakeFeature(
        "LinearPattern",
        "PartDesign::LinearPattern",
        TransformMode="Whole shape",
        Originals=[],
    )
    assert not model.is_multi_transform_child(pattern)
    assert model.is_solid_feature(pattern)


def test_transform_mode_uses_the_objects_own_enumeration():
    """FreeCAD renamed these labels between 1.0 and 1.1, so the index is read
    from the object rather than matched against a baked-in spelling."""
    child = FakeFeature(
        "P",
        "PartDesign::LinearPattern",
        TransformMode="Transform tool shapes",
        Originals=[],
        Enumerations={"TransformMode": ["Transform tool shapes", "Transform body"]},
    )
    assert model._transform_mode_index(child) == 0
    assert model.is_multi_transform_child(child)

    whole = FakeFeature(
        "Q",
        "PartDesign::LinearPattern",
        TransformMode="Transform body",
        Originals=[],
        Enumerations={"TransformMode": ["Transform tool shapes", "Transform body"]},
    )
    assert model._transform_mode_index(whole) == 1
    assert not model.is_multi_transform_child(whole)


@pytest.mark.parametrize("mode", ["Features", "Transform tool shapes"])
def test_transform_mode_falls_back_to_known_spellings(mode):
    """Objects that cannot report an enumeration still resolve, on either the
    FreeCAD 1.0 or the 1.1 naming."""
    child = FakeFeature(
        "P", "PartDesign::LinearPattern", TransformMode=mode, Originals=[]
    )
    assert model.is_multi_transform_child(child)


def test_unknown_transform_mode_spelling_is_not_a_child():
    child = FakeFeature(
        "P", "PartDesign::LinearPattern", TransformMode="???", Originals=[]
    )
    assert model._transform_mode_index(child) is None
    assert not model.is_multi_transform_child(child)


def test_transform_mode_accepts_integer_enum():
    """PropertyEnumeration reads back as a string from Python, but tolerate an
    int in case a caller passes the raw index."""
    child = FakeFeature("P", "PartDesign::LinearPattern", TransformMode=0, Originals=[])
    assert model.is_multi_transform_child(child)


# --------------------------------------------------------------------------
# full model / ordering
# --------------------------------------------------------------------------


def test_full_model_puts_base_feature_first():
    doc, body, parts = make_simple_body()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base

    assert model.full_model(body) == [
        base,
        parts["sketch"],
        parts["pad"],
        parts["fillet"],
    ]


def test_full_model_of_none_is_empty():
    assert model.full_model(None) == []


def test_is_after_matches_group_order():
    _doc, body, parts = make_simple_body()
    assert model.is_after(body, parts["fillet"], parts["pad"])
    assert not model.is_after(body, parts["pad"], parts["fillet"])
    assert not model.is_after(body, parts["pad"], parts["pad"])


def test_is_after_with_no_tip_treats_everything_as_after():
    """BodyBase::isAfter with a null target returns hasObject(feature)."""
    _doc, body, parts = make_simple_body()
    assert model.is_after(body, parts["pad"], None)
    assert model.is_after(body, parts["fillet"], None)


def test_is_after_base_feature_target():
    doc, body, parts = make_simple_body()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    assert model.is_after(body, parts["pad"], base)
    assert not model.is_after(body, base, base)


# --------------------------------------------------------------------------
# timeline construction
# --------------------------------------------------------------------------


def test_build_timeline_hides_non_solids_by_default():
    _doc, body, _parts = make_simple_body()
    entries = model.build_timeline(body)
    assert [e.name for e in entries] == ["Pad", "Fillet"]


def test_build_timeline_can_show_non_solids():
    _doc, body, _parts = make_simple_body()
    entries = model.build_timeline(body, show_non_solid=True)
    assert [e.name for e in entries] == ["Sketch", "Pad", "Fillet"]
    assert entries[0].kind == model.KIND_SKETCH


def test_model_index_is_stable_when_filtering():
    """Hiding sketches must not renumber the underlying full-model positions."""
    _doc, body, _parts = make_simple_body()
    shown = model.build_timeline(body, show_non_solid=True)
    hidden = model.build_timeline(body, show_non_solid=False)
    by_name = {e.name: e.model_index for e in shown}
    for entry in hidden:
        assert entry.model_index == by_name[entry.name]


def test_entries_after_tip_are_dimmed():
    _doc, body, parts = make_simple_body()
    body.Tip = parts["pad"]

    entries = model.build_timeline(body)
    pad, fillet = entries
    assert pad.is_tip
    assert not pad.dimmed
    assert not fillet.is_tip
    assert fillet.dimmed


def test_no_tip_dims_everything():
    _doc, body, _parts = make_simple_body()
    body.Tip = None
    assert all(e.dimmed for e in model.build_timeline(body))


def test_suppressed_is_reported():
    _doc, body, parts = make_simple_body()
    parts["fillet"].Suppressed = True
    entries = model.build_timeline(body)
    assert entries[1].suppressed
    assert not entries[0].suppressed


def test_build_timeline_of_none_body():
    assert model.build_timeline(None) == []


def test_tip_slot():
    _doc, body, parts = make_simple_body()
    body.Tip = parts["pad"]
    entries = model.build_timeline(body)
    assert model.tip_slot(entries) == 1

    body.Tip = parts["fillet"]
    assert model.tip_slot(model.build_timeline(body)) == 2

    body.Tip = None
    assert model.tip_slot(model.build_timeline(body)) == 0


def test_entry_at_slot():
    _doc, body, _parts = make_simple_body()
    entries = model.build_timeline(body)
    assert model.entry_at_slot(entries, 0) is None
    assert model.entry_at_slot(entries, 1).name == "Pad"
    assert model.entry_at_slot(entries, 2).name == "Fillet"
    assert model.entry_at_slot(entries, 3) is None


# --------------------------------------------------------------------------
# tip validation
# --------------------------------------------------------------------------


def test_can_be_tip_rules():
    doc, body, parts = make_simple_body()
    assert model.can_be_tip(body, parts["pad"])
    assert not model.can_be_tip(body, parts["sketch"])
    assert model.can_be_tip(body, None)

    outsider = FakeFeature("Other", document=doc)
    assert not model.can_be_tip(body, outsider)


def test_base_feature_can_be_tip():
    doc, body, _parts = make_simple_body()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    assert model.can_be_tip(body, base)


# --------------------------------------------------------------------------
# move planning
# --------------------------------------------------------------------------


def test_plan_move_to_front():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move(entries, 2, 0) == (None, True)


def test_plan_move_to_end():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)
    target, after = model.plan_move(entries, 0, 3)
    assert target is pads[2]
    assert after is True


def test_plan_move_middle():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)
    target, after = model.plan_move(entries, 0, 2)
    assert target is pads[1]
    assert after is True


def test_plan_move_noop_on_own_slots():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move(entries, 1, 1) is None
    assert model.plan_move(entries, 1, 2) is None


def test_plan_move_rejects_base_feature():
    doc, body, _pads = make_three_pads()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    entries = model.build_timeline(body, show_non_solid=True)
    assert entries[0].is_base
    assert model.plan_move(entries, 0, 2) is None


def test_plan_move_after_base_feature_targets_beginning():
    """The base feature is not in Group, so it can never be an insertObject
    target; dropping right after it means the start of the body."""
    doc, body, _pads = make_three_pads()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    entries = model.build_timeline(body, show_non_solid=True)
    assert model.plan_move(entries, 3, 1) == (None, True)


def test_plan_move_many_block_to_front():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move_many(entries, [1, 2], 0) == (None, True)


def test_plan_move_many_block_to_end():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)
    target, after = model.plan_move_many(entries, [0, 1], 3)
    assert target is pads[2]
    assert after is True


def test_plan_move_many_non_contiguous_sources():
    """Dragging the first and last of three between them lands after the
    middle one, which is the only feature left."""
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)
    target, after = model.plan_move_many(entries, [0, 2], 2)
    assert target is pads[1]
    assert after is True


def test_plan_move_many_noop_when_block_already_there():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move_many(entries, [0, 1], 0) is None
    assert model.plan_move_many(entries, [0, 1], 2) is None
    assert model.plan_move_many(entries, [1, 2], 1) is None
    assert model.plan_move_many(entries, [0, 1, 2], 0) is None


def test_plan_move_many_ignores_duplicates_and_out_of_range():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move_many(entries, [2, 2, 99, -1], 0) == (None, True)
    assert model.plan_move_many(entries, [], 0) is None


def test_plan_move_many_rejects_a_block_containing_the_base():
    doc, body, _pads = make_three_pads()
    base = FakeObject("Box", "Part::Box", document=doc)
    body.BaseFeature = base
    entries = model.build_timeline(body, show_non_solid=True)
    assert model.plan_move_many(entries, [0, 1], 3) is None


def test_plan_move_out_of_range():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.plan_move(entries, 99, 0) is None
    assert model.plan_move(entries, -1, 0) is None


def test_plan_move_clamps_slot():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)
    target, after = model.plan_move(entries, 0, 99)
    assert target is pads[2]
    assert after is True


# --------------------------------------------------------------------------
# dependency ordering
# --------------------------------------------------------------------------


def test_no_dependency_violations_in_sane_body():
    _doc, body, _parts = make_simple_body()
    assert model.dependency_violations(body) == []


def test_dependency_violation_detected_through_sketch():
    """A Pad whose sketch is attached to a later Pocket's face is illegal."""
    doc = FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)

    pocket = FakeFeature("Pocket", "PartDesign::Pocket", document=doc)
    sketch = FakeObject("Sketch", "Sketcher::SketchObject", document=doc)
    pad = FakeFeature("Pad", document=doc)

    for obj in (pad, sketch, pocket):
        doc.add(obj)

    # Group order: Pad first, Pocket later ...
    body.addObject(pad)
    body.addObject(sketch)
    body.addObject(pocket)

    # ... but Pad's profile sketch is attached to the later Pocket.
    pad.OutList = [sketch]
    sketch.OutList = [pocket]

    violations = model.dependency_violations(body)
    assert violations
    feature, via, dependency = violations[0]
    assert feature is pad
    assert via is sketch
    assert dependency is pocket


def test_feature_to_feature_links_are_not_violations():
    """BaseFeature chaining links each solid to its predecessor; that is the
    body's normal structure, not a violation."""
    _doc, body, parts = make_simple_body()
    parts["fillet"].OutList = [parts["pad"]]
    assert model.dependency_violations(body) == []


# --------------------------------------------------------------------------
# exclusive children
# --------------------------------------------------------------------------


def test_exclusive_children_finds_profile_sketch():
    _doc, body, parts = make_simple_body()
    children = model.exclusive_children(body, parts["pad"])
    assert children == [parts["sketch"]]


def test_shared_sketch_is_not_exclusive():
    doc, body, parts = make_simple_body()
    other = FakeFeature("Pocket", "PartDesign::Pocket", document=doc)
    doc.add(other)
    body.addObject(other)
    parts["sketch"].InList = [parts["pad"], other]

    assert model.exclusive_children(body, parts["pad"]) == []


def test_exclusive_children_never_includes_solids():
    _doc, body, parts = make_simple_body()
    assert parts["pad"] not in model.exclusive_children(body, parts["fillet"])


# --------------------------------------------------------------------------
# recompute status
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (["Up-to-date"], model.STATUS_OK),
        (["Touched"], model.STATUS_TOUCHED),
        (["Invalid"], model.STATUS_ERROR),
        # Both flags set: the error is what matters.
        (["Touched", "Invalid"], model.STATUS_ERROR),
        ([], model.STATUS_OK),
        (["Expanded"], model.STATUS_OK),
    ],
)
def test_feature_status(state, expected):
    assert model.feature_status(FakeFeature("Pad", State=state)) == expected


def test_feature_status_of_a_non_object():
    class NoState:
        State = None

    assert model.feature_status(NoState()) == model.STATUS_OK


def test_status_message_only_for_unhealthy_features():
    healthy = FakeFeature("Pad")
    assert model.status_message(healthy) == ""

    broken = FakeFeature(
        "Pocket", State=["Invalid"], StatusString="Pocket: Resulting shape is empty"
    )
    assert model.status_message(broken) == "Pocket: Resulting shape is empty"


def test_status_message_survives_a_raising_accessor():
    class Angry:
        def getStatusString(self):
            raise ReferenceError("deleted")

    assert model.status_message(Angry()) == ""


def test_timeline_entries_carry_status():
    _doc, body, parts = make_simple_body()
    parts["fillet"].State = ["Invalid"]
    parts["fillet"]._status_string = "Fillet: failed on Edge1"

    entries = model.build_timeline(body)
    pad, fillet = entries

    assert pad.status == model.STATUS_OK
    assert not pad.failed
    assert not pad.out_of_date

    assert fillet.failed
    assert fillet.status_message == "Fillet: failed on Edge1"


def test_touched_entry_is_out_of_date_but_not_failed():
    _doc, body, parts = make_simple_body()
    parts["pad"].State = ["Touched"]

    entry = model.build_timeline(body)[0]
    assert entry.out_of_date
    assert not entry.failed


# --------------------------------------------------------------------------
# tip transport
# --------------------------------------------------------------------------


def test_navigation_slots_skip_non_solids():
    """Stepping must never park the tip on a sketch."""
    _doc, body, _parts = make_simple_body()
    entries = model.build_timeline(body, show_non_solid=True)
    assert [e.name for e in entries] == ["Sketch", "Pad", "Fillet"]
    # Slot 0 (start) plus one after each of Pad and Fillet — not the sketch.
    assert model.tip_navigation_slots(entries) == [0, 2, 3]


def test_step_tip_forward_and_back():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)

    assert model.step_tip_slot(entries, 0, +1) == 1
    assert model.step_tip_slot(entries, 1, +1) == 2
    assert model.step_tip_slot(entries, 2, -1) == 1
    assert model.step_tip_slot(entries, 1, -1) == 0


def test_step_tip_stops_at_the_ends():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)

    assert model.step_tip_slot(entries, 0, -1) is None
    assert model.step_tip_slot(entries, 3, +1) is None


def test_step_tip_skips_over_a_sketch():
    _doc, body, _parts = make_simple_body()
    entries = model.build_timeline(body, show_non_solid=True)
    # From the start, forward lands on the Pad's slot (2), skipping the sketch.
    assert model.step_tip_slot(entries, 0, +1) == 2


def test_last_tip_slot():
    _doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert model.last_tip_slot(entries) == 3

    _doc2, body2, _parts = make_simple_body()
    shown = model.build_timeline(body2, show_non_solid=True)
    assert model.last_tip_slot(shown) == 3  # the Fillet, not the sketch


def test_navigation_slots_with_no_features():
    assert model.tip_navigation_slots([]) == [0]
    assert model.last_tip_slot([]) == 0

# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tests against the real FreeCAD Python module, skipped when it is absent.

``import FreeCAD`` works headlessly (no GUI, no display) when FreeCAD's Python
module is on ``sys.path`` — e.g. inside ``nix develop`` with the ``freecad``
package, or by running ``freecadcmd -c "import pytest; pytest.main([...])"``.

These tests pin down the assumptions the addon is built on, so a future FreeCAD
release that changes them fails here loudly instead of misbehaving in the GUI:

* ``Body.insertObject`` is positional-only and *insert only*
* ``Suppressed`` exists on PartDesign features and round-trips
* ``Tip`` accepts any solid feature and drives ``isAfter`` ordering
* ``Body.removeObject`` reassigns ``Tip`` when the tip itself is removed
"""

from __future__ import annotations

import pytest

FreeCAD = pytest.importorskip("FreeCAD", reason="FreeCAD Python module not available")

from freecad_timeline import commands, model  # noqa: E402


@pytest.fixture
def document():
    doc = FreeCAD.newDocument("TimelineAddonTest")
    yield doc
    FreeCAD.closeDocument(doc.Name)


def _rectangle(sketch, width=10.0, height=10.0):
    """Add a closed rectangle so the pad produces a real solid."""
    import Part

    corners = [
        FreeCAD.Vector(0, 0, 0),
        FreeCAD.Vector(width, 0, 0),
        FreeCAD.Vector(width, height, 0),
        FreeCAD.Vector(0, height, 0),
    ]
    for index in range(4):
        sketch.addGeometry(
            Part.LineSegment(corners[index], corners[(index + 1) % 4]), False
        )
    for index in range(4):
        # Coincident constraints close the wire.
        sketch.addConstraint(
            __import__("Sketcher").Constraint(
                "Coincident", index, 2, (index + 1) % 4, 1
            )
        )


@pytest.fixture
def body_with_features(document):
    """Body containing Sketch -> Pad -> Fillet, tip on the fillet."""
    body = document.addObject("PartDesign::Body", "Body")

    sketch = document.addObject("Sketcher::SketchObject", "Sketch")
    body.addObject(sketch)
    _rectangle(sketch)
    document.recompute()

    pad = document.addObject("PartDesign::Pad", "Pad")
    body.addObject(pad)
    pad.Profile = sketch
    pad.Length = 10
    document.recompute()

    fillet = document.addObject("PartDesign::Fillet", "Fillet")
    body.addObject(fillet)
    fillet.Base = (pad, ["Edge1"])
    fillet.Radius = 1.0
    document.recompute()

    return document, body, sketch, pad, fillet


# --------------------------------------------------------------------------
# assumptions about the FreeCAD API
# --------------------------------------------------------------------------


def test_features_have_the_suppressible_extension(body_with_features):
    _, _, _, pad, fillet = body_with_features
    assert pad.hasExtension("App::SuppressibleExtension")
    assert fillet.hasExtension("App::SuppressibleExtension")
    assert hasattr(pad, "Suppressed")


def test_insert_object_is_positional_only(body_with_features):
    """BodyPyImp.cpp parses with PyArg_ParseTuple, so `after=` is not a keyword.

    The addon passes it positionally; this test is what guarantees that stays
    correct.
    """
    _document, body, _sketch, pad, fillet = body_with_features
    body.removeObject(fillet)
    with pytest.raises(TypeError):
        body.insertObject(fillet, pad, after=True)
    # Positional works.
    body.insertObject(fillet, pad, True)
    assert fillet in body.Group


def test_insert_object_does_not_remove(body_with_features):
    """The trap `move_feature` exists to avoid: insertObject alone duplicates."""
    _document, body, _sketch, pad, fillet = body_with_features
    before = len(body.Group)

    body.insertObject(fillet, pad, False)
    assert len(body.Group) == before + 1
    assert body.Group.count(fillet) == 2

    # Put it back the way it was.
    body.removeObject(fillet)


def test_insert_object_rejects_a_foreign_target(body_with_features):
    document, body, _sketch, _pad, fillet = body_with_features
    other_body = document.addObject("PartDesign::Body", "Body2")
    other_pad = document.addObject("PartDesign::Pad", "Pad2")
    other_body.addObject(other_pad)

    body.removeObject(fillet)
    with pytest.raises(Exception):  # noqa: B017, PT011 — FreeCAD raises bare Exception
        body.insertObject(fillet, other_pad, True)


def test_tip_and_group_ordering(body_with_features):
    _document, body, sketch, pad, fillet = body_with_features
    assert body.Tip is fillet
    assert list(body.Group) == [sketch, pad, fillet]

    assert model.is_after(body, fillet, pad)
    assert not model.is_after(body, pad, fillet)


def test_visible_feature_property_exists(body_with_features):
    _document, body, _sketch, _pad, _fillet = body_with_features
    # Read-only property added by BodyPy; may be None headlessly (no view
    # providers), but it must exist.
    assert hasattr(body, "VisibleFeature")


def test_remove_object_pulls_the_tip_back(body_with_features):
    _document, body, _sketch, pad, fillet = body_with_features
    assert body.Tip is fillet
    body.removeObject(fillet)
    assert body.Tip is pad


# --------------------------------------------------------------------------
# the addon's own layers, against real objects
# --------------------------------------------------------------------------


def test_classification_of_real_objects(body_with_features):
    _document, _body, sketch, pad, fillet = body_with_features
    assert model.classify(pad) == model.KIND_SOLID
    assert model.classify(fillet) == model.KIND_SOLID
    assert model.classify(sketch) == model.KIND_SKETCH
    assert not model.is_solid_feature(sketch)


def test_datum_plane_is_classified_as_datum(document):
    body = document.addObject("PartDesign::Body", "Body")
    plane = document.addObject("PartDesign::Plane", "DatumPlane")
    body.addObject(plane)
    document.recompute()

    assert model.is_datum(plane)
    assert model.classify(plane) == model.KIND_DATUM
    assert not model.can_be_tip(body, plane)


def test_build_timeline_filters_the_sketch(body_with_features):
    _document, body, _sketch, _pad, _fillet = body_with_features

    solids = model.build_timeline(body)
    assert [entry.name for entry in solids] == ["Pad", "Fillet"]

    everything = model.build_timeline(body, show_non_solid=True)
    assert [entry.name for entry in everything] == ["Sketch", "Pad", "Fillet"]


def test_set_tip_rolls_back_and_dims(body_with_features):
    _document, body, _sketch, pad, _fillet = body_with_features

    commands.set_tip(body, pad)
    assert body.Tip is pad

    entries = model.build_timeline(body)
    by_name = {entry.name: entry for entry in entries}
    assert by_name["Pad"].is_tip
    assert by_name["Fillet"].after_tip
    assert model.tip_slot(entries) == 1


def test_set_tip_is_undoable(body_with_features):
    document, body, _sketch, pad, fillet = body_with_features
    document.UndoMode = 1

    commands.set_tip(body, pad)
    assert body.Tip is pad

    document.undo()
    assert body.Tip is fillet


def test_suppress_round_trip_changes_the_shape(body_with_features):
    document, body, _sketch, _pad, fillet = body_with_features
    document.recompute()
    with_fillet = body.Shape.Volume

    commands.set_suppressed(fillet, True)
    assert fillet.Suppressed is True
    without_fillet = body.Shape.Volume
    assert abs(with_fillet - without_fillet) > 1e-6

    commands.set_suppressed(fillet, False)
    assert fillet.Suppressed is False
    assert body.Shape.Volume == pytest.approx(with_fillet, rel=1e-6)


def test_rename_feature(body_with_features):
    _document, _body, _sketch, pad, _fillet = body_with_features
    commands.rename_feature(pad, "Base plate")
    assert pad.Label == "Base plate"


def test_move_feature_reorders_without_duplicating(document):
    body = document.addObject("PartDesign::Body", "Body")
    planes = []
    for index in range(3):
        plane = document.addObject("PartDesign::Plane", f"Plane{index}")
        body.addObject(plane)
        planes.append(plane)
    document.recompute()

    commands.move_feature(body, planes[2], None, True)

    assert list(body.Group) == [planes[2], planes[0], planes[1]]
    assert len(body.Group) == 3


def test_move_feature_preserves_the_tip(body_with_features):
    _document, body, sketch, pad, fillet = body_with_features
    assert body.Tip is fillet

    commands.move_feature(body, fillet, sketch, True)

    assert body.Tip is fillet, "reordering the tip feature must not move the tip"
    assert list(body.Group) == [sketch, fillet, pad]


def test_delete_feature_detaches_and_reroutes(body_with_features):
    document, body, _sketch, pad, fillet = body_with_features

    removed = commands.delete_features(body, [fillet])

    assert removed == ["Fillet"]
    assert document.getObject("Fillet") is None
    assert body.Tip is pad


def test_exclusive_children_finds_the_profile_sketch(body_with_features):
    _document, body, sketch, pad, _fillet = body_with_features
    children = model.exclusive_children(body, pad)
    assert sketch in children


def test_dependency_violations_clean_on_a_sane_body(body_with_features):
    _document, body, _sketch, _pad, _fillet = body_with_features
    assert model.dependency_violations(body) == []


# --------------------------------------------------------------------------
# the hardcoded strings the addon keys on
# --------------------------------------------------------------------------


def test_state_strings_for_a_failed_feature(document):
    """`feature_status` keys on the literals "Invalid" and "Touched" from
    DocumentObjectPy::getState; pin them against a really broken feature."""
    body = document.addObject("PartDesign::Body", "Body")
    pad = document.addObject("PartDesign::Pad", "Pad")  # no Profile -> fails
    body.addObject(pad)
    document.recompute()

    assert "Invalid" in pad.State
    assert model.feature_status(pad) == model.STATUS_ERROR
    # And the real error description reaches the tooltip.
    assert model.status_message(pad)
    assert model.status_message(pad) != "Valid"


def test_status_of_a_healthy_feature(body_with_features):
    document, _body, _sketch, pad, _fillet = body_with_features
    document.recompute()
    assert model.feature_status(pad) == model.STATUS_OK
    assert model.status_message(pad) == ""


def test_transform_mode_index_not_spelling(document):
    """The labels differ across versions — FreeCAD 1.0 says "Transform tool
    shapes"/"Transform body", 1.1 says "Features"/"Whole shape" — so only the
    index is meaningful. This asserts the semantics that survive the rename."""
    body = document.addObject("PartDesign::Body", "Body")
    pattern = document.addObject("PartDesign::LinearPattern", "LinearPattern")
    body.addObject(pattern)

    enums = list(pattern.getEnumerationsOfProperty("TransformMode"))
    assert len(enums) >= 2, enums
    # A fresh Transformed defaults to index 0, the per-feature mode.
    assert pattern.TransformMode == enums[0]
    assert model._transform_mode_index(pattern) == 0


def test_bare_transformed_is_treated_as_a_multitransform_child(document):
    """Faithful mirror of a FreeCAD quirk: with TransformMode at index 0 and
    an empty Originals, isMultiTransformChild() returns true even for a
    standalone feature. FreeCAD's own comment says it "will mislabel standalone
    features during the initialization phase"; a GUI-created pattern has
    Originals populated, so this only bites freshly scripted ones."""
    body = document.addObject("PartDesign::Body", "Body")
    pattern = document.addObject("PartDesign::LinearPattern", "LinearPattern")
    body.addObject(pattern)

    assert list(pattern.Originals) == []
    assert model.is_multi_transform_child(pattern)
    assert not model.is_solid_feature(pattern)


def test_parameter_path_round_trips_through_freecad(document):
    """settings.PARAMETER_PATH is a hardcoded ParamGet path; the unit tests use
    a fake, so this is the only place it is exercised for real."""
    from freecad_timeline import settings

    group = FreeCAD.ParamGet(settings.PARAMETER_PATH)
    assert group is not None

    settings.set_bool(settings.VISIBLE, False)
    assert settings.get_bool(settings.VISIBLE, True) is False
    assert group.GetBool(settings.VISIBLE, True) is False

    settings.set_bool(settings.VISIBLE, True)
    assert group.GetBool(settings.VISIBLE, False) is True


def test_pdbody_key_is_the_one_partdesign_uses(document):
    """PDBODY_KEY mirrors ActiveObjectList.h. Without a GUI we cannot set an
    active object, but the key must at least be accepted by the API shape the
    addon relies on."""
    from freecad_timeline import integration

    assert integration.PDBODY_KEY == "pdbody"

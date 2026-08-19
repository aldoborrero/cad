# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mutation tests: transaction discipline, tip, suppression, reordering."""

from __future__ import annotations

import pytest

from freecad_timeline import commands, model

from .fakes import (
    FakeBody,
    FakeDocument,
    FakeFeature,
    FakeObject,
    make_simple_body,
    make_three_pads,
)

# --------------------------------------------------------------------------
# transaction plumbing
# --------------------------------------------------------------------------


def test_transaction_commits_and_recomputes():
    doc = FakeDocument()
    with commands.transaction(doc, "Do a thing"):
        pass
    assert doc.transactions == ["Do a thing"]
    assert doc.committed == ["Do a thing"]
    assert doc.aborted == []
    assert doc.recomputes == 1
    assert doc.open_transactions == []


def test_transaction_aborts_on_exception():
    doc = FakeDocument()
    with pytest.raises(ValueError, match="boom"), commands.transaction(doc, "Boom"):
        raise ValueError("boom")
    assert doc.aborted == ["Boom"]
    assert doc.committed == []
    assert doc.recomputes == 0
    assert doc.open_transactions == []


def test_transaction_can_skip_recompute():
    doc = FakeDocument()
    with commands.transaction(doc, "Quiet", recompute=False):
        pass
    assert doc.recomputes == 0


def test_document_of_requires_a_document():
    with pytest.raises(commands.TimelineError):
        commands.document_of(FakeFeature("Orphan"))


# --------------------------------------------------------------------------
# tip
# --------------------------------------------------------------------------


def test_set_tip_moves_tip_in_one_transaction():
    doc, body, parts = make_simple_body()
    body.Tip = parts["fillet"]

    commands.set_tip(body, parts["pad"])

    assert body.Tip is parts["pad"]
    assert doc.committed == ["Move tip to selected feature"]
    assert doc.recomputes == 1


def test_set_tip_shows_the_new_tip():
    _doc, body, parts = make_simple_body()
    parts["pad"].Visibility = False
    commands.set_tip(body, parts["pad"])
    assert parts["pad"].Visibility is True


def test_set_tip_rejects_non_solid():
    doc, body, parts = make_simple_body()
    with pytest.raises(commands.TimelineError):
        commands.set_tip(body, parts["sketch"])
    assert doc.transactions == []


def test_set_tip_is_a_noop_when_unchanged():
    doc, body, parts = make_simple_body()
    body.Tip = parts["fillet"]
    commands.set_tip(body, parts["fillet"])
    assert doc.transactions == []


def test_clear_tip():
    doc, body, _parts = make_simple_body()
    commands.clear_tip(body)
    assert body.Tip is None
    assert doc.committed == ["Move tip to selected feature"]


# --------------------------------------------------------------------------
# suppression
# --------------------------------------------------------------------------


def test_toggle_suppressed_roundtrip():
    doc, _body, parts = make_simple_body()
    fillet = parts["fillet"]

    assert commands.toggle_suppressed(fillet) is True
    assert fillet.Suppressed is True
    assert doc.committed == ["Suppress Fillet"]

    assert commands.toggle_suppressed(fillet) is False
    assert fillet.Suppressed is False
    assert doc.committed[-1] == "Unsuppress Fillet"
    assert doc.recomputes == 2


def test_set_suppressed_noop_when_unchanged():
    doc, _body, parts = make_simple_body()
    commands.set_suppressed(parts["pad"], False)
    assert doc.transactions == []


def test_suppress_rejects_objects_without_the_extension():
    _doc, _body, parts = make_simple_body()
    with pytest.raises(commands.TimelineError):
        commands.set_suppressed(parts["sketch"], True)


# --------------------------------------------------------------------------
# rename
# --------------------------------------------------------------------------


def test_rename_feature():
    doc, _body, parts = make_simple_body()
    commands.rename_feature(parts["pad"], "  Base plate  ")
    assert parts["pad"].Label == "Base plate"
    assert doc.committed == ["Rename feature"]


def test_rename_rejects_empty_label():
    doc, _body, parts = make_simple_body()
    with pytest.raises(commands.TimelineError):
        commands.rename_feature(parts["pad"], "   ")
    assert doc.transactions == []


def test_rename_noop_when_unchanged():
    doc, _body, parts = make_simple_body()
    commands.rename_feature(parts["pad"], "Pad")
    assert doc.transactions == []


# --------------------------------------------------------------------------
# delete
# --------------------------------------------------------------------------


def test_delete_detaches_from_body_before_document():
    """Body::removeObject must run first so Tip and BaseFeature are rerouted."""
    doc, body, parts = make_simple_body()
    body.Tip = parts["fillet"]

    removed = commands.delete_features(body, [parts["fillet"]])

    assert removed == ["Fillet"]
    assert parts["fillet"] not in body.Group
    assert doc.getObject("Fillet") is None
    assert body.Tip is parts["pad"], "tip should fall back to the previous solid"
    assert doc.committed == ["Delete feature"]


def test_delete_reroutes_base_feature_of_the_next_solid():
    doc, body, parts = make_simple_body()
    pocket = FakeFeature("Pocket", "PartDesign::Pocket", document=doc)
    doc.add(pocket)
    body.addObject(pocket)
    pocket.BaseFeature = parts["fillet"]

    commands.delete_features(body, [parts["fillet"]])

    assert pocket.BaseFeature is parts["pad"]


def test_delete_feature_and_its_exclusive_sketch():
    doc, body, parts = make_simple_body()
    children = model.exclusive_children(body, parts["pad"])

    removed = commands.delete_features(body, [parts["pad"], *children])

    assert sorted(removed) == ["Pad", "Sketch"]
    assert doc.getObject("Sketch") is None


def test_delete_skips_already_removed_objects():
    doc, body, parts = make_simple_body()
    doc.removeObject("Sketch")
    removed = commands.delete_features(body, [parts["pad"], parts["sketch"]])
    assert removed == ["Pad"]


def test_delete_nothing_opens_no_transaction():
    doc, body, _parts = make_simple_body()
    assert commands.delete_features(body, []) == []
    assert doc.transactions == []


# --------------------------------------------------------------------------
# reordering — the risky part
# --------------------------------------------------------------------------


def test_move_does_not_duplicate_the_feature():
    """insertObject only inserts; without the preceding removeObject the
    feature would appear in Group twice."""
    doc, body, pads = make_three_pads()

    commands.move_feature(body, pads[2], None, True)

    assert body.Group == [pads[2], pads[0], pads[1]]
    assert len(body.Group) == 3
    assert doc.committed == ["Move a feature inside body"]


def test_move_to_end():
    _doc, body, pads = make_three_pads()
    commands.move_feature(body, pads[0], pads[2], True)
    assert body.Group == [pads[1], pads[2], pads[0]]


def test_move_preserves_the_tip():
    """Body::removeObject reassigns Tip when the tip itself is moved; the
    command restores it so a reorder never silently rolls the body back."""
    _doc, body, pads = make_three_pads()
    body.Tip = pads[2]

    commands.move_feature(body, pads[2], None, True)

    assert body.Tip is pads[2]


def test_move_leaves_an_unrelated_tip_alone():
    _doc, body, pads = make_three_pads()
    body.Tip = pads[1]
    commands.move_feature(body, pads[0], pads[2], True)
    assert body.Tip is pads[1]


def test_move_rejects_foreign_feature():
    doc, body, pads = make_three_pads()
    outsider = FakeFeature("Outsider", document=doc)
    with pytest.raises(commands.TimelineError):
        commands.move_feature(body, outsider, pads[0], True)
    assert doc.transactions == []


def test_move_rejects_foreign_target():
    doc, body, pads = make_three_pads()
    outsider = FakeFeature("Outsider", document=doc)
    with pytest.raises(commands.TimelineError):
        commands.move_feature(body, pads[0], outsider, True)
    assert doc.transactions == []


def test_move_onto_itself_is_a_noop():
    doc, body, pads = make_three_pads()
    commands.move_feature(body, pads[0], pads[0], True)
    assert doc.transactions == []


def test_move_rolls_back_on_dependency_violation():
    """Moving a Pad after the Pocket its sketch is attached to must abort and
    leave Group exactly as it was."""
    doc = FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)

    pad = FakeFeature("Pad", document=doc)
    sketch = FakeObject("Sketch", "Sketcher::SketchObject", document=doc)
    pocket = FakeFeature("Pocket", "PartDesign::Pocket", document=doc)
    for obj in (pad, sketch, pocket):
        doc.add(obj)
        body.addObject(obj)

    # Pocket's profile sketch is attached to a face of Pad.
    pocket.OutList = [sketch]
    sketch.OutList = [pad]

    before = list(body.Group)
    with pytest.raises(commands.DependencyViolation) as excinfo:
        commands.move_feature(body, pocket, None, True)

    assert "must not depend on later feature" in str(excinfo.value)
    assert doc.aborted == ["Move a feature inside body"]
    assert doc.committed == []
    assert doc.recomputes == 0
    # The fake mutates in place, so the abort is what the real document would
    # undo; what matters is that we never committed the bad order.
    assert set(body.Group) == set(before)


# --------------------------------------------------------------------------
# batch operations
# --------------------------------------------------------------------------


def test_suppress_many_is_one_transaction():
    doc, _body, pads = make_three_pads()

    changed = commands.set_suppressed_many(pads, True)

    assert len(changed) == 3
    assert all(p.Suppressed for p in pads)
    assert doc.committed == ["Suppress 3 features"]
    assert doc.recomputes == 1


def test_suppress_many_skips_features_already_in_state():
    doc, _body, pads = make_three_pads()
    pads[0].Suppressed = True

    changed = commands.set_suppressed_many(pads, True)

    assert [p.Name for p in changed] == ["PadB", "PadC"]
    assert doc.committed == ["Suppress 2 features"]


def test_suppress_many_with_nothing_to_do_opens_no_transaction():
    doc, _body, pads = make_three_pads()
    assert commands.set_suppressed_many(pads, False) == []
    assert doc.transactions == []


def test_suppress_many_of_one_uses_the_singular_label():
    doc, _body, pads = make_three_pads()
    commands.set_suppressed_many([pads[0]], True)
    assert doc.committed == ["Suppress PadA"]


def test_toggle_many_suppresses_a_mixed_selection():
    """Anything still enabled means the whole set gets suppressed."""
    _doc, _body, pads = make_three_pads()
    pads[0].Suppressed = True

    assert commands.toggle_suppressed_many(pads) is True
    assert all(p.Suppressed for p in pads)


def test_toggle_many_unsuppresses_only_when_all_are_suppressed():
    _doc, _body, pads = make_three_pads()
    for pad in pads:
        pad.Suppressed = True

    assert commands.toggle_suppressed_many(pads) is False
    assert not any(p.Suppressed for p in pads)


def test_toggle_many_ignores_features_without_the_extension():
    doc, _body, parts = make_simple_body()
    assert commands.toggle_suppressed_many([parts["sketch"]]) is False
    assert doc.transactions == []


def test_move_features_keeps_relative_order():
    doc, body, pads = make_three_pads()

    commands.move_features(body, [pads[0], pads[1]], pads[2], True)

    assert body.Group == [pads[2], pads[0], pads[1]]
    assert doc.committed == ["Move features inside body"]


def test_move_features_accepts_sources_out_of_order():
    _doc, body, pads = make_three_pads()

    commands.move_features(body, [pads[1], pads[0]], pads[2], True)

    assert body.Group == [pads[2], pads[0], pads[1]]


def test_move_features_to_the_front():
    _doc, body, pads = make_three_pads()

    commands.move_features(body, [pads[1], pads[2]], None, True)

    assert body.Group == [pads[1], pads[2], pads[0]]


def test_move_features_never_duplicates():
    _doc, body, pads = make_three_pads()
    commands.move_features(body, [pads[0], pads[2]], pads[1], True)
    assert sorted(p.Name for p in body.Group) == ["PadA", "PadB", "PadC"]
    assert body.Group == [pads[1], pads[0], pads[2]]


def test_move_features_skips_the_target_itself():
    _doc, body, pads = make_three_pads()
    commands.move_features(body, [pads[0], pads[2]], pads[2], True)
    assert body.Group == [pads[1], pads[2], pads[0]]


def test_move_features_preserves_the_tip():
    _doc, body, pads = make_three_pads()
    body.Tip = pads[0]

    commands.move_features(body, [pads[0], pads[1]], pads[2], True)

    assert body.Tip is pads[0]


def test_move_features_of_nothing_is_a_noop():
    doc, body, pads = make_three_pads()
    commands.move_features(body, [], pads[0], True)
    assert doc.transactions == []


def test_move_selection_to_slot():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)

    assert commands.move_selection_to_slot(body, entries, [1, 2], 0) is True
    assert body.Group == [pads[1], pads[2], pads[0]]


def test_move_selection_to_slot_noop():
    doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert commands.move_selection_to_slot(body, entries, [0, 1], 2) is False
    assert doc.transactions == []


def test_move_single_via_slot_plans_and_executes():
    _doc, body, pads = make_three_pads()
    entries = model.build_timeline(body)

    assert commands.move_selection_to_slot(body, entries, [2], 0) is True
    assert body.Group == [pads[2], pads[0], pads[1]]


def test_move_single_via_slot_noop_returns_false():
    doc, body, _pads = make_three_pads()
    entries = model.build_timeline(body)
    assert commands.move_selection_to_slot(body, entries, [1], 1) is False
    assert doc.transactions == []

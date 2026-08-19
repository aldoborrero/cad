# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mutations the timeline performs on a body.

Every public function here wraps its work in an
``openTransaction`` / ``commitTransaction`` pair so each timeline gesture is a
single undo step, aborts the transaction if anything raises, and recomputes
afterwards.  Like :mod:`.model` this module imports no Qt, so it can be
exercised headlessly.

The sequences follow FreeCAD's own commands (``CmdPartDesignMoveTip``,
``CmdPartDesignMoveFeatureInTree`` in ``src/Mod/PartDesign/Gui/CommandBody.cpp``).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any

from . import model

__all__ = [
    "DependencyViolation",
    "TimelineError",
    "clear_tip",
    "delete_features",
    "move_feature",
    "move_features",
    "move_selection_to_slot",
    "rename_feature",
    "set_suppressed",
    "set_suppressed_many",
    "set_tip",
    "toggle_suppressed",
    "toggle_suppressed_many",
    "transaction",
]


class TimelineError(RuntimeError):
    """A timeline mutation was rejected before touching the document."""


class DependencyViolation(TimelineError):
    """A reorder would place a feature before something it depends on.

    ``violations`` holds the ``(feature, via, dependency)`` triples reported by
    :func:`~freecad_timeline.model.dependency_violations`.
    """

    def __init__(self, violations: Iterable[Any]) -> None:
        self.violations = list(violations)
        super().__init__(self.describe())

    def describe(self) -> str:
        lines = [
            "{}, {} -> {}".format(
                getattr(feature, "Label", "?"),
                getattr(via, "Label", "?"),
                getattr(dependency, "Label", "?"),
            )
            for feature, via, dependency in self.violations
        ]
        return "Early feature must not depend on later feature.\n\n" + "\n".join(lines)


def document_of(obj: Any) -> Any:
    """The document owning ``obj``.  Raises rather than guessing."""
    doc = getattr(obj, "Document", None)
    if doc is None:
        raise TimelineError(f"Object {obj!r} is not attached to a document")
    return doc


@contextmanager
def transaction(doc: Any, name: str, recompute: bool = True) -> Iterator[None]:
    """Run a block as one undo step.

    On success the transaction is committed and the document recomputed; on any
    exception it is rolled back and the exception re-raised, so a failed
    gesture never leaves the document half-modified.
    """
    doc.openTransaction(name)
    try:
        yield doc
    except Exception:
        with suppress(Exception):
            doc.abortTransaction()
        raise
    doc.commitTransaction()
    if recompute:
        doc.recompute()


# --------------------------------------------------------------------------
# tip / rollback
# --------------------------------------------------------------------------


def set_tip(body: Any, feature: Any) -> None:
    """Roll the body back (or forward) to ``feature``.

    ``feature`` may be ``None`` to clear the tip, which is the C++ command's
    "the body itself is selected" case.
    """
    if not model.can_be_tip(body, feature):
        raise TimelineError(
            "Only a solid feature can be the tip of a body ({})".format(
                getattr(feature, "Label", feature)
            )
        )
    if getattr(body, "Tip", None) is feature:
        return

    with transaction(document_of(body), "Move tip to selected feature"):
        body.Tip = feature
        if feature is not None:
            # CmdPartDesignMoveTip shows the new tip so the 3D view follows.
            with suppress(Exception):
                feature.Visibility = True


def clear_tip(body: Any) -> None:
    """Set ``Tip`` to ``None`` (body shows nothing)."""
    set_tip(body, None)


# --------------------------------------------------------------------------
# suppression
# --------------------------------------------------------------------------


def set_suppressed(feature: Any, value: bool) -> None:
    """Toggle ``App::SuppressibleExtension::Suppressed``.

    PartDesign keeps ``SuppressedShape``/``SuppressedPlacement`` alongside, so
    this is reversible without data loss.
    """
    if not hasattr(feature, "Suppressed"):
        raise TimelineError(
            "{} cannot be suppressed".format(getattr(feature, "Label", feature))
        )
    value = bool(value)
    if bool(feature.Suppressed) == value:
        return

    label = getattr(feature, "Label", "feature")
    name = f"Suppress {label}" if value else f"Unsuppress {label}"
    with transaction(document_of(feature), name):
        feature.Suppressed = value


def toggle_suppressed(feature: Any) -> bool:
    """Flip suppression and return the new state."""
    new_value = not bool(getattr(feature, "Suppressed", False))
    set_suppressed(feature, new_value)
    return new_value


def set_suppressed_many(features: Sequence[Any], value: bool) -> list[Any]:
    """Suppress or unsuppress several features as **one** undo step.

    Features lacking the extension, or already in the requested state, are
    skipped.  Returns those actually changed.
    """
    value = bool(value)
    targets = [
        feature
        for feature in features
        if feature is not None
        and hasattr(feature, "Suppressed")
        and bool(feature.Suppressed) != value
    ]
    if not targets:
        return []

    if len(targets) == 1:
        name = ("Suppress %s" if value else "Unsuppress %s") % getattr(
            targets[0], "Label", "feature"
        )
    else:
        name = ("Suppress %d features" if value else "Unsuppress %d features") % len(
            targets
        )

    with transaction(document_of(targets[0]), name):
        for feature in targets:
            feature.Suppressed = value
    return targets


def toggle_suppressed_many(features: Sequence[Any]) -> bool:
    """Flip suppression for a selection and return the state applied.

    If anything in the selection is still enabled the whole set is suppressed;
    only when every one is already suppressed does it unsuppress. That keeps a
    mixed selection moving in one predictable direction.
    """
    candidates = [f for f in features if f is not None and hasattr(f, "Suppressed")]
    if not candidates:
        return False
    value = not all(bool(f.Suppressed) for f in candidates)
    set_suppressed_many(candidates, value)
    return value


# --------------------------------------------------------------------------
# rename / delete
# --------------------------------------------------------------------------


def rename_feature(feature: Any, label: str) -> None:
    """Change a feature's ``Label``."""
    label = (label or "").strip()
    if not label:
        raise TimelineError("A feature label cannot be empty")
    if getattr(feature, "Label", None) == label:
        return

    with transaction(document_of(feature), "Rename feature"):
        feature.Label = label


def delete_features(body: Any, features: Sequence[Any]) -> list[str]:
    """Delete ``features`` from ``body`` and its document.

    ``Body::removeObject`` must run *before* the object leaves the document —
    it is what reroutes the next feature's ``BaseFeature`` and pulls ``Tip``
    back to the previous solid.  Skipping it leaves a body with a dangling tip.

    Returns the names of the objects actually removed.
    """
    features = [f for f in features if f is not None]
    if not features:
        return []

    doc = document_of(features[0])
    removed: list[str] = []
    with transaction(doc, "Delete feature"):
        for feature in features:
            name = getattr(feature, "Name", None)
            if not name or doc.getObject(name) is None:
                continue  # already gone, e.g. removed as another feature's child
            if body is not None:
                # Not a member (already detached) — deleting is still fine.
                with suppress(Exception):
                    body.removeObject(feature)
            doc.removeObject(name)
            removed.append(name)
    return removed


# --------------------------------------------------------------------------
# reordering
# --------------------------------------------------------------------------


def move_feature(body: Any, feature: Any, target: Any, after: bool = True) -> None:
    """Move ``feature`` next to ``target`` inside ``body``.

    ``Body::insertObject`` only *inserts* — it never removes — so reordering an
    existing member requires the remove/insert pair FreeCAD's own
    ``PartDesign_MoveFeatureInTree`` uses.  Calling ``insertObject`` alone on a
    feature already in ``Group`` would list it twice.

    ``target=None`` with ``after=True`` means "the beginning of the body".

    ``Tip`` is captured and restored across the move: ``Body::removeObject``
    reassigns it to a neighbouring solid whenever the tip itself is the object
    being pulled out, which would silently roll the body back.

    Raises :class:`DependencyViolation` (and rolls the move back) if the new
    order would put a feature before something it depends on.
    """
    if feature is None:
        raise TimelineError("No feature to move")
    move_features(body, [feature], target, after)


def move_features(
    body: Any, features: Sequence[Any], target: Any, after: bool = True
) -> None:
    """Move several features next to ``target``, keeping their relative order.

    Same remove/insert recipe as :func:`move_feature`, applied the way
    ``CmdPartDesignMoveFeatureInTree`` does it for a multi-selection: each
    feature is re-inserted after the previous one, so the block ends up
    contiguous and in its original order.  The whole batch is one undo step.
    """
    features = [f for f in features if f is not None]
    if not features:
        return

    group = list(getattr(body, "Group", None) or [])
    for feature in features:
        if feature not in group:
            raise TimelineError(
                "{} is not a member of {}".format(
                    getattr(feature, "Label", feature), getattr(body, "Label", body)
                )
            )
    if target is not None and target not in group:
        # Body::insertObject throws on this; fail before opening a transaction.
        raise TimelineError(
            "The feature to insert relative to is not part of that body"
        )
    # Moving a feature relative to itself is a no-op, not an error;
    # CmdPartDesignMoveFeatureInTree skips it the same way.
    features = [f for f in features if f is not target]
    if not features:
        return

    # Re-insertion walks the list, so the features must go in Group order.
    features = sorted(features, key=group.index)
    previous_tip = getattr(body, "Tip", None)

    name = (
        "Move a feature inside body"
        if len(features) == 1
        else "Move features inside body"
    )
    with transaction(document_of(body), name):
        anchor = target
        for index, feature in enumerate(features):
            body.removeObject(feature)
            # insertObject is positional-only (PyArg_ParseTuple in
            # BodyPyImp.cpp); passing after= as a keyword raises TypeError.
            body.insertObject(feature, anchor, bool(after) if index == 0 else True)
            anchor = feature

        if (
            previous_tip is not None
            and getattr(body, "Tip", None) is not previous_tip
            and previous_tip in list(getattr(body, "Group", None) or [])
        ):
            body.Tip = previous_tip

        violations = model.dependency_violations(body)
        if violations:
            raise DependencyViolation(violations)


def move_selection_to_slot(
    body: Any, entries: Sequence[Any], source_indices: Sequence[int], slot: int
) -> bool:
    """Drag several selected features onto ``slot``.

    Returns ``True`` when the document was changed.
    """
    plan = model.plan_move_many(entries, source_indices, slot)
    if plan is None:
        return False
    target, after = plan
    ordered = sorted({i for i in source_indices if 0 <= i < len(entries)})
    move_features(body, [entries[i].obj for i in ordered], target, after)
    return True


def iter_labels(objects: Iterable[Any]) -> list[str]:
    """Labels for a set of objects, for confirmation dialogs."""
    return [str(getattr(obj, "Label", obj)) for obj in objects]

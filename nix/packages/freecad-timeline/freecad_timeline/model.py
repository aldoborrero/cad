# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure data layer for the Timeline addon.

This module deliberately imports neither Qt nor FreeCAD.  It reaches document
objects only through the small duck-typed surface the timeline needs
(``Group``, ``Tip``, ``BaseFeature``, ``Label``, ``Suppressed``, ``OutList``,
``isDerivedFrom``), which keeps it unit-testable against real FreeCAD objects
*and* against lightweight fakes.

The predicates below mirror FreeCAD ``master`` exactly; the C++ counterpart is
named in each docstring so the two can be diffed when FreeCAD changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "KIND_DATUM",
    "KIND_OTHER",
    "KIND_SKETCH",
    "KIND_SOLID",
    "STATUS_ERROR",
    "STATUS_OK",
    "STATUS_TOUCHED",
    "TimelineEntry",
    "build_timeline",
    "can_be_tip",
    "classify",
    "dependency_violations",
    "entry_at_slot",
    "exclusive_children",
    "feature_status",
    "full_model",
    "is_after",
    "is_datum",
    "is_multi_transform_child",
    "is_sketch",
    "is_solid_feature",
    "is_suppressed",
    "last_tip_slot",
    "plan_move",
    "plan_move_many",
    "status_message",
    "step_tip_slot",
    "tip_navigation_slots",
    "tip_slot",
]

KIND_SOLID = "solid"
KIND_DATUM = "datum"
KIND_SKETCH = "sketch"
KIND_OTHER = "other"

#: Recompute health, read from ``DocumentObject.State``.
STATUS_OK = "ok"
STATUS_TOUCHED = "touched"
STATUS_ERROR = "error"

#: Known spellings of ``Transformed::transformModeEnums``, newest first.  These
#: are only a fallback for objects that cannot report their own enumeration
#: (the test fakes); see :func:`_transform_mode_index` for why they are not
#: compared directly.  FreeCAD renamed them between 1.0 and 1.1.
_TRANSFORM_MODE_SPELLINGS = (
    ("Features", "Whole shape"),  # FreeCAD 1.1+
    ("Transform tool shapes", "Transform body"),  # FreeCAD 1.0
)


# --------------------------------------------------------------------------
# type predicates
# --------------------------------------------------------------------------


def _derived_from(obj: Any, type_name: str) -> bool:
    """``obj.isDerivedFrom(type_name)``, tolerant of anything that is not a
    document object (``None``, deleted proxies, plain fakes)."""
    if obj is None:
        return False
    try:
        return bool(obj.isDerivedFrom(type_name))
    except Exception:
        return False


def is_datum(obj: Any) -> bool:
    """Mirror of ``PartDesign::Feature::isDatum`` (Feature.cpp).

    Datum planes/lines/points and origin elements are not solids and can never
    be the tip of a body.
    """
    return _derived_from(obj, "App::DatumElement") or _derived_from(obj, "Part::Datum")


def is_sketch(obj: Any) -> bool:
    """``Sketcher::SketchObject`` derives from ``Part::Part2DObject``, which is
    the type ``Body::isAllowed`` tests for."""
    return _derived_from(obj, "Part::Part2DObject")


def _transform_mode_index(obj: Any) -> int | None:
    """Index of ``obj``'s current ``TransformMode``, or ``None``.

    The C++ compares the raw index (``TransformMode.getValue() == 0``), but the
    Python binding hands back the *display string* — and those strings were
    renamed between FreeCAD 1.0 (``"Transform tool shapes"`` /
    ``"Transform body"``) and 1.1 (``"Features"`` / ``"Whole shape"``).
    Matching on a baked-in spelling therefore silently stopped detecting
    MultiTransform children on one version or the other.

    So ask the object for its own enumeration and take the index. Only objects
    that cannot answer that (the test fakes) fall back to the known spellings.
    """
    mode = getattr(obj, "TransformMode", None)
    if isinstance(mode, bool):
        return None
    if isinstance(mode, int):
        return mode
    if not isinstance(mode, str):
        return None

    getter = getattr(obj, "getEnumerationsOfProperty", None)
    if getter is not None:
        try:
            return list(getter("TransformMode")).index(mode)
        except Exception:
            pass

    for spelling in _TRANSFORM_MODE_SPELLINGS:
        if mode in spelling:
            return spelling.index(mode)
    return None


def is_multi_transform_child(obj: Any) -> bool:
    """Mirror of ``PartDesign::Transformed::isMultiTransformChild``.

    FreeCAD does not walk the in-list here (unreliable during creation); it
    detects the child by its default property values: ``TransformMode`` still
    at index 0 with an empty ``Originals``.
    """
    if not _derived_from(obj, "PartDesign::Transformed"):
        return False
    if _transform_mode_index(obj) != 0:
        return False
    return not list(getattr(obj, "Originals", None) or [])


def is_solid_feature(obj: Any) -> bool:
    """Mirror of ``PartDesign::Body::isSolidFeature`` (Body.cpp).

    Only solid features contribute to the body's shape, and only they may be
    the tip.
    """
    if not _derived_from(obj, "PartDesign::Feature"):
        return False
    if is_datum(obj):
        return False
    if _derived_from(obj, "PartDesign::Transformed"):
        return not is_multi_transform_child(obj)
    return True


def classify(obj: Any) -> str:
    """Bucket a body member into one of the ``KIND_*`` constants."""
    if is_solid_feature(obj):
        return KIND_SOLID
    if is_datum(obj):
        return KIND_DATUM
    if is_sketch(obj):
        return KIND_SKETCH
    return KIND_OTHER


def is_suppressed(obj: Any) -> bool:
    """Read ``App::SuppressibleExtension::Suppressed``.

    Objects without the extension (datums, sketches on some builds) simply
    report ``False``.
    """
    return bool(getattr(obj, "Suppressed", False))


def feature_status(obj: Any) -> str:
    """Recompute health of ``obj``, from ``DocumentObject.State``.

    ``DocumentObjectPy::getState`` appends ``"Invalid"`` when ``isError()`` and
    ``"Touched"`` when the object is out of date, so those two strings are what
    we key on.  A feature that failed to recompute is the single most useful
    thing a timeline can surface, and it is invisible otherwise.
    """
    states = getattr(obj, "State", None) or []
    try:
        states = list(states)
    except TypeError:
        return STATUS_OK
    if "Invalid" in states:
        return STATUS_ERROR
    if "Touched" in states:
        return STATUS_TOUCHED
    return STATUS_OK


def status_message(obj: Any) -> str:
    """``getStatusString()`` — the recompute error description when in error.

    Returns an empty string when the object is healthy or the call is
    unavailable (fakes, older builds).
    """
    getter = getattr(obj, "getStatusString", None)
    if getter is None:
        return ""
    try:
        text = getter()
    except Exception:
        return ""
    if not text or text in ("Valid", "Up-to-date"):
        return ""
    return str(text)


def _label(obj: Any) -> str:
    return str(getattr(obj, "Label", None) or getattr(obj, "Name", None) or "?")


def _name(obj: Any) -> str:
    return str(getattr(obj, "Name", None) or "")


# --------------------------------------------------------------------------
# body traversal
# --------------------------------------------------------------------------


def full_model(body: Any) -> list[Any]:
    """Mirror of ``Part::BodyBase::getFullModel``: the base feature (if any)
    followed by ``Group`` in order."""
    if body is None:
        return []
    result: list[Any] = []
    base = getattr(body, "BaseFeature", None)
    if base is not None:
        result.append(base)
    result.extend(
        obj for obj in (getattr(body, "Group", None) or []) if obj is not None
    )
    return result


def is_after(body: Any, feature: Any, target: Any) -> bool:
    """Mirror of ``Part::BodyBase::isAfter``.

    Note the two special cases that FreeCAD encodes and that the timeline's
    dimming depends on: a ``None`` target (no tip set) or a target that *is*
    the base feature make every member of ``Group`` "after" it.
    """
    if feature is target:
        return False

    group = list(getattr(body, "Group", None) or [])
    base = getattr(body, "BaseFeature", None)

    if target is None or (base is not None and target is base):
        return feature in group

    if feature not in group or target not in group:
        # C++ returns false when the feature is absent, and comparing against
        # end() can never be greater either.
        return False

    return group.index(feature) > group.index(target)


def can_be_tip(body: Any, obj: Any) -> bool:
    """Whether ``body.Tip = obj`` is legal.

    ``CmdPartDesignMoveTip`` accepts the base feature or any
    ``PartDesign::Feature``; we additionally exclude datums and MultiTransform
    children via :func:`is_solid_feature`, matching ``Body::isSolidFeature``.
    ``None`` is allowed and clears the tip (the C++ command's "tip is the body"
    case).
    """
    if body is None:
        return False
    if obj is None:
        return True
    base = getattr(body, "BaseFeature", None)
    if base is not None and obj is base:
        return True
    group = list(getattr(body, "Group", None) or [])
    return obj in group and is_solid_feature(obj)


# --------------------------------------------------------------------------
# timeline entries
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TimelineEntry:
    """One rendered slot in the timeline.

    ``model_index`` is the position in :func:`full_model`, which stays stable
    even when non-solid features are filtered out of the view.
    """

    obj: Any
    name: str
    label: str
    kind: str
    model_index: int
    is_base: bool
    is_tip: bool
    after_tip: bool
    suppressed: bool
    tip_allowed: bool
    status: str = STATUS_OK
    status_message: str = ""

    @property
    def dimmed(self) -> bool:
        """After-tip features are rolled back and are not part of the result."""
        return self.after_tip

    @property
    def failed(self) -> bool:
        return self.status == STATUS_ERROR

    @property
    def out_of_date(self) -> bool:
        return self.status == STATUS_TOUCHED


def build_timeline(body: Any, show_non_solid: bool = False) -> list[TimelineEntry]:
    """Build the ordered entry list for ``body``.

    Sketches, datums and other non-solid members are hidden unless
    ``show_non_solid`` is set.
    """
    if body is None:
        return []

    base = getattr(body, "BaseFeature", None)
    tip = getattr(body, "Tip", None)

    entries: list[TimelineEntry] = []
    for index, obj in enumerate(full_model(body)):
        kind = classify(obj)
        if kind != KIND_SOLID and not show_non_solid:
            continue
        entries.append(
            TimelineEntry(
                obj=obj,
                name=_name(obj),
                label=_label(obj),
                kind=kind,
                model_index=index,
                is_base=base is not None and obj is base,
                is_tip=tip is not None and obj is tip,
                after_tip=is_after(body, obj, tip),
                suppressed=is_suppressed(obj),
                tip_allowed=can_be_tip(body, obj),
                status=feature_status(obj),
                status_message=status_message(obj),
            )
        )
    return entries


def tip_slot(entries: Sequence[TimelineEntry]) -> int:
    """Slot index the rollback marker sits at.

    Slots run ``0..len(entries)``: slot *n* means "after the first *n*
    entries".  With no tip set the marker sits at the very beginning.
    """
    for position, entry in enumerate(entries):
        if entry.is_tip:
            return position + 1
    return 0


def tip_navigation_slots(entries: Sequence[TimelineEntry]) -> list[int]:
    """Slots the tip may legally occupy, ascending.

    Slot 0 is "before everything" (``Tip = None``); every tip-eligible entry
    contributes the slot just after it. Non-solid members are skipped, so
    stepping never parks the tip on a sketch.
    """
    slots = [0]
    for position, entry in enumerate(entries):
        if entry.tip_allowed:
            slots.append(position + 1)
    return slots


def step_tip_slot(
    entries: Sequence[TimelineEntry], current_slot: int, direction: int
) -> int | None:
    """The next legal tip slot in ``direction`` (-1 back, +1 forward).

    ``None`` when there is nowhere further to go — which is what greys out the
    step buttons at either end of the strip.
    """
    slots = tip_navigation_slots(entries)
    if direction < 0:
        earlier = [slot for slot in slots if slot < current_slot]
        return earlier[-1] if earlier else None
    later = [slot for slot in slots if slot > current_slot]
    return later[0] if later else None


def last_tip_slot(entries: Sequence[TimelineEntry]) -> int:
    """Slot that puts the tip at the end of the body."""
    return tip_navigation_slots(entries)[-1]


def entry_at_slot(entries: Sequence[TimelineEntry], slot: int) -> TimelineEntry | None:
    """The entry a marker dropped at ``slot`` should make the tip, or ``None``
    to clear the tip."""
    index = slot - 1
    if index < 0 or index >= len(entries):
        return None
    return entries[index]


# --------------------------------------------------------------------------
# reordering
# --------------------------------------------------------------------------


def plan_move(
    entries: Sequence[TimelineEntry], source_index: int, slot: int
) -> tuple[Any, bool] | None:
    """Single-feature form of :func:`plan_move_many`."""
    return plan_move_many(entries, [source_index], slot)


def plan_move_many(
    entries: Sequence[TimelineEntry], source_indices: Sequence[int], slot: int
) -> tuple[Any, bool] | None:
    """Translate a drag of one or more features onto ``slot`` into
    ``insertObject`` arguments.

    Returns ``(target, after)`` — the pair to pass to
    ``body.insertObject(feature, target, after)`` *after* the features have
    been removed — or ``None`` when the drag is a no-op.

    ``target`` may be ``None``, which ``Body::insertObject`` interprets (with
    ``after=True``) as "insert at the beginning of the body".  Dragged features
    keep their relative order and end up contiguous, matching
    ``CmdPartDesignMoveFeatureInTree``.
    """
    indices = sorted({i for i in source_indices if 0 <= i < len(entries)})
    if not indices:
        return None
    if any(entries[i].is_base for i in indices):
        # "Impossible to move the base feature of a body."
        return None

    slot = max(0, min(slot, len(entries)))

    moving = set(indices)
    remaining = [e for i, e in enumerate(entries) if i not in moving]
    # Slots to the right of a dragged feature shift left once it is pulled out.
    insert_at = slot - sum(1 for i in indices if i < slot)

    # The block is already sitting exactly where it would land.
    if indices == list(range(insert_at, insert_at + len(indices))):
        return None

    if insert_at <= 0:
        return (None, True)

    predecessor = remaining[insert_at - 1]
    if predecessor.is_base:
        # The base feature is not in Group, so it cannot be an insertObject
        # target; landing right after it means landing at the beginning.
        return (None, True)
    return (predecessor.obj, True)


def _dependency_closure(obj: Any, seen: set[int] | None = None) -> list[Any]:
    """Transitive ``OutList`` closure, the Python equivalent of
    ``App::Document::getDependencyList({obj})``."""
    if seen is None:
        seen = set()
    result: list[Any] = []
    for dependency in getattr(obj, "OutList", None) or []:
        key = id(dependency)
        if key in seen:
            continue
        seen.add(key)
        result.append(dependency)
        result.extend(_dependency_closure(dependency, seen))
    return result


def dependency_violations(body: Any) -> list[tuple[Any, Any, Any]]:
    """Port of the dependency-order check in ``CmdPartDesignMoveFeatureInTree``.

    An earlier feature must not depend, even transitively through non-feature
    objects such as sketches, on a later one.  Returns ``(feature, via,
    later_feature)`` triples; an empty list means the ordering is sound.
    """
    order = {}
    features: list[Any] = []
    for obj in getattr(body, "Group", None) or []:
        if _derived_from(obj, "PartDesign::Feature"):
            order[id(obj)] = len(features)
            features.append(obj)

    violations: list[tuple[Any, Any, Any]] = []
    for position, feature in enumerate(features):
        for linked in getattr(feature, "OutList", None) or []:
            if _derived_from(linked, "PartDesign::Feature"):
                # Feature-to-feature links are the body's own chaining.
                continue
            for dependency in [linked, *_dependency_closure(linked)]:
                other = order.get(id(dependency))
                if other is not None and other > position:
                    violations.append((feature, linked, dependency))
    return violations


def exclusive_children(body: Any, feature: Any) -> list[Any]:
    """Body members that only ``feature`` refers to — a Pad's profile sketch,
    a Revolution's axis, and so on.

    Used to offer "delete the sketch too" when a feature is deleted, without
    ever proposing to remove something another feature still needs.
    """
    if body is None or feature is None:
        return []

    members = [
        obj for obj in (getattr(body, "Group", None) or []) if obj is not feature
    ]
    referenced = set()
    for obj in getattr(feature, "OutList", None) or []:
        referenced.add(id(obj))

    result = []
    for candidate in members:
        if id(candidate) not in referenced:
            continue
        if is_solid_feature(candidate):
            continue
        others = [
            user
            for user in (getattr(candidate, "InList", None) or [])
            if user is not feature and user is not body
        ]
        if not others:
            result.append(candidate)
    return result

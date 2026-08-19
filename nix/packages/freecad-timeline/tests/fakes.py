# SPDX-License-Identifier: LGPL-2.1-or-later
"""In-memory stand-ins for FreeCAD documents, bodies and features.

These are not generic mocks: the type hierarchy and the ``Body`` methods
reproduce the FreeCAD ``master`` semantics that the timeline depends on, so a
test that passes here means the same thing it would against the real module.
Each behaviour is annotated with the C++ function it mirrors.
"""

from __future__ import annotations

from typing import Any

#: Type name -> immediate parent, mirroring the FreeCAD class hierarchy for the
#: types the timeline classifies.
TYPE_PARENTS: dict[str, str | None] = {
    "App::DocumentObject": None,
    "App::GeoFeature": "App::DocumentObject",
    "App::DatumElement": "App::GeoFeature",
    "App::Plane": "App::DatumElement",
    "Part::Feature": "App::GeoFeature",
    "Part::Datum": "Part::Feature",
    "Part::Part2DObject": "Part::Feature",
    "Sketcher::SketchObject": "Part::Part2DObject",
    "PartDesign::Plane": "Part::Datum",
    "PartDesign::Line": "Part::Datum",
    "PartDesign::Feature": "Part::Feature",
    "PartDesign::FeatureRefine": "PartDesign::Feature",
    "PartDesign::FeatureAddSub": "PartDesign::FeatureRefine",
    "PartDesign::ProfileBased": "PartDesign::FeatureAddSub",
    "PartDesign::Pad": "PartDesign::ProfileBased",
    "PartDesign::Pocket": "PartDesign::ProfileBased",
    "PartDesign::Revolved": "PartDesign::ProfileBased",
    "PartDesign::Revolution": "PartDesign::Revolved",
    "PartDesign::Groove": "PartDesign::Revolved",
    "PartDesign::Loft": "PartDesign::ProfileBased",
    "PartDesign::AdditiveLoft": "PartDesign::Loft",
    "PartDesign::SubtractiveLoft": "PartDesign::Loft",
    "PartDesign::DressUp": "PartDesign::FeatureAddSub",
    "PartDesign::Fillet": "PartDesign::DressUp",
    "PartDesign::Chamfer": "PartDesign::DressUp",
    "PartDesign::Draft": "PartDesign::DressUp",
    "PartDesign::Thickness": "PartDesign::DressUp",
    "PartDesign::Boolean": "PartDesign::FeatureRefine",
    "PartDesign::Transformed": "PartDesign::Feature",
    "PartDesign::LinearPattern": "PartDesign::Transformed",
    "PartDesign::MultiTransform": "PartDesign::Transformed",
    "PartDesign::ShapeBinder": "Part::Feature",
    "Part::Box": "Part::Feature",
    "PartDesign::Body": "Part::Feature",
}


class FakeObject:
    """A document object with the attributes the timeline reads."""

    def __init__(self, name, type_id, label=None, document=None, **properties):
        self.Name = name
        self.TypeId = type_id
        self.Label = label if label is not None else name
        self.Document = document
        self.Visibility = properties.pop("Visibility", False)
        self.OutList: list[Any] = list(properties.pop("OutList", []) or [])
        self.InList: list[Any] = list(properties.pop("InList", []) or [])
        # DocumentObjectPy::getState appends "Up-to-date" when nothing is wrong.
        self.State: list[str] = list(properties.pop("State", ["Up-to-date"]))
        self._status_string = properties.pop("StatusString", None)
        #: property name -> allowed values, for getEnumerationsOfProperty
        self._enumerations = dict(properties.pop("Enumerations", {}) or {})
        for key, value in properties.items():
            setattr(self, key, value)

    def getStatusString(self) -> str:
        """``DocumentObject::getStatusString`` — the error description when in
        error, else "Touched"/"Valid"."""
        if self._status_string is not None:
            return self._status_string
        if "Invalid" in self.State:
            return "Error"
        if "Touched" in self.State:
            return "Touched"
        return "Valid"

    def getEnumerationsOfProperty(self, name: str):
        """``DocumentObject.getEnumerationsOfProperty`` for PropertyEnumeration.

        Raises for unknown properties, like the real binding, so callers that
        guard with try/except are exercised.
        """
        if name not in self._enumerations:
            raise AttributeError(name)
        return list(self._enumerations[name])

    def isDerivedFrom(self, type_name: str) -> bool:
        current = self.TypeId
        while current is not None:
            if current == type_name:
                return True
            if current not in TYPE_PARENTS:
                return False
            current = TYPE_PARENTS[current]
        return False

    def hasExtension(self, name: str) -> bool:
        return name == "App::SuppressibleExtension" and hasattr(self, "Suppressed")

    def __repr__(self):
        return f"<{self.TypeId} {self.Name}>"


class FakeFeature(FakeObject):
    """A solid PartDesign feature: carries ``Suppressed`` and ``BaseFeature``."""

    def __init__(self, name, type_id="PartDesign::Pad", **kwargs):
        kwargs.setdefault("Suppressed", False)
        kwargs.setdefault("BaseFeature", None)
        super().__init__(name, type_id, **kwargs)


class FakeBody(FakeObject):
    """A ``PartDesign::Body``.

    ``insertObject`` and ``removeObject`` reproduce ``Body::insertObject`` and
    ``Body::removeObject`` including their sharp edges — insert does not
    remove, and remove reassigns ``Tip``.
    """

    def __init__(self, name="Body", document=None, label=None):
        super().__init__(name, "PartDesign::Body", label=label, document=document)
        self.Group: list[Any] = []
        self.Tip: Any = None
        self.BaseFeature: Any = None

    # -- helpers mirroring the C++ ----------------------------------------

    def hasObject(self, obj) -> bool:
        return obj in self.Group

    @staticmethod
    def _is_solid(obj) -> bool:
        from freecad_timeline import model

        return model.is_solid_feature(obj)

    def getPrevSolidFeature(self, start=None):
        """``Body::getPrevSolidFeature`` — nearest solid strictly before
        ``start``; ``None`` if there is none (it does not fall back to
        ``BaseFeature``)."""
        if start is None:
            start = self.Tip
        if start is None or start not in self.Group:
            return None
        index = self.Group.index(start)
        for obj in reversed(self.Group[:index]):
            if self._is_solid(obj):
                return obj
        return None

    def getNextSolidFeature(self, start=None):
        """``Body::getNextSolidFeature`` — nearest solid strictly after
        ``start``."""
        if start is None:
            start = self.Tip
        if start is None or start not in self.Group:
            return None
        index = self.Group.index(start)
        for obj in self.Group[index + 1 :]:
            if self._is_solid(obj):
                return obj
        return None

    # -- mutating API ------------------------------------------------------

    def addObject(self, obj):
        self.Group.append(obj)
        if self._is_solid(obj):
            self.Tip = obj
        if self.Document is not None and obj.Document is None:
            obj.Document = self.Document
        return [obj]

    def insertObject(self, feature, target, after=False):
        """``Body::insertObject``.

        Positional-only in the real binding, insert-only, and it raises when
        ``target`` is not a member of the body.
        """
        if target is not None and not self.hasObject(target):
            raise ValueError(
                "Body: the feature we should insert relative to is not part of"
                " that body"
            )
        if target is None:
            index = 0 if after else len(self.Group)
        else:
            index = self.Group.index(target) + (1 if after else 0)
        self.Group.insert(index, feature)

    def removeObject(self, feature):
        """``Body::removeObject`` — reroutes the next feature's ``BaseFeature``
        and pulls ``Tip`` back to a neighbouring solid."""
        next_solid = self.getNextSolidFeature(feature)
        prev_solid = self.getPrevSolidFeature(feature)

        if (
            next_solid is not None
            and next_solid.isDerivedFrom("PartDesign::Feature")
            and getattr(next_solid, "BaseFeature", None) is feature
        ):
            next_solid.BaseFeature = prev_solid

        if self.Tip is feature:
            self.Tip = prev_solid if prev_solid is not None else next_solid

        if feature in self.Group:
            self.Group.remove(feature)
        return [feature]


class FakeDocument:
    """A document that records transaction bookkeeping so tests can assert
    that every mutation is a single, properly closed undo step."""

    def __init__(self, name="TestDoc"):
        self.Name = name
        self.Objects: list[Any] = []
        self.transactions: list[str] = []
        self.committed: list[str] = []
        self.aborted: list[str] = []
        self.recomputes = 0
        self._open: list[str] = []

    # -- object bookkeeping ------------------------------------------------

    def addObject(self, type_id, name, cls=FakeObject, **kwargs):
        obj = cls(name, type_id, document=self, **kwargs)
        self.Objects.append(obj)
        return obj

    def add(self, obj):
        obj.Document = self
        self.Objects.append(obj)
        return obj

    def getObject(self, name):
        for obj in self.Objects:
            if obj.Name == name:
                return obj
        return None

    def findObjects(self, type_id):
        return [obj for obj in self.Objects if obj.isDerivedFrom(type_id)]

    def removeObject(self, name):
        obj = self.getObject(name)
        if obj is None:
            raise ValueError(f"No object named {name!r}")
        self.Objects.remove(obj)
        return obj

    # -- transactions ------------------------------------------------------

    def openTransaction(self, name):
        self.transactions.append(name)
        self._open.append(name)

    def commitTransaction(self):
        if not self._open:
            raise AssertionError("commitTransaction without an open transaction")
        self.committed.append(self._open.pop())

    def abortTransaction(self):
        if not self._open:
            raise AssertionError("abortTransaction without an open transaction")
        self.aborted.append(self._open.pop())

    def recompute(self, *args, **kwargs):
        self.recomputes += 1

    @property
    def open_transactions(self):
        return list(self._open)


def make_simple_body(document=None, with_sketch=True):
    """A body with Sketch -> Pad -> Fillet, tip on the fillet.

    Returns ``(document, body, {"sketch": ..., "pad": ..., "fillet": ...})``.
    """
    doc = document or FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)

    parts = {}
    if with_sketch:
        sketch = FakeObject("Sketch", "Sketcher::SketchObject", document=doc)
        doc.add(sketch)
        body.addObject(sketch)
        parts["sketch"] = sketch

    pad = FakeFeature("Pad", "PartDesign::Pad", document=doc)
    doc.add(pad)
    body.addObject(pad)
    parts["pad"] = pad
    if with_sketch:
        pad.OutList = [parts["sketch"]]
        parts["sketch"].InList = [pad]

    fillet = FakeFeature("Fillet", "PartDesign::Fillet", document=doc)
    doc.add(fillet)
    body.addObject(fillet)
    fillet.BaseFeature = pad
    fillet.OutList = [pad]
    parts["fillet"] = fillet

    return doc, body, parts


def make_three_pads(document=None):
    """A body with PadA, PadB, PadC and no base feature.

    Returns ``(document, body, [pads])``.
    """
    doc = document or FakeDocument()
    body = FakeBody(document=doc)
    doc.add(body)
    pads = []
    for name in ("PadA", "PadB", "PadC"):
        pad = FakeFeature(name, document=doc)
        doc.add(pad)
        body.addObject(pad)
        pads.append(pad)
    return doc, body, pads

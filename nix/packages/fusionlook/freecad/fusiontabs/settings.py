"""The addon's four switches, in one place.

They exist in three: this module, the preferences page's .ui, and whatever the
user has actually saved. `tests/test_settings.py` keeps the first two in step —
a key renamed here and not there would silently read its default forever.
"""

from __future__ import annotations

from dataclasses import dataclass

# `Mod/FusionTabs` is what the .ui's prefPath says; ParamGet wants it spelled out.
PREFERENCE_PATH = "Mod/FusionTabs"
PREFERENCES = f"User parameter:BaseApp/Preferences/{PREFERENCE_PATH}"


@dataclass(frozen=True)
class Option:
    key: str
    default: bool
    describes: str


OPTIONS: tuple[Option, ...] = (
    Option(
        key="DocumentTabsOnTop",
        default=True,
        describes="Move the document tabs from the bottom of the 3D view to the top",
    ),
    Option(
        key="StyleDocumentTabs",
        default=True,
        describes="Paint the document tab strip darker than the toolbars, with an "
        "accent edge on the open document",
    ),
    Option(
        key="StyleWorkbenchTabs",
        default=True,
        describes="Flatten the workbench selector to text with an accent underline",
    ),
    Option(
        key="UseWorkbenchTabSelector",
        default=True,
        describes="Switch the workbench selector from a drop-down to FreeCAD's own "
        "tab bar (Preferences > Workbenches > selector type)",
    ),
)

BY_KEY: dict[str, Option] = {option.key: option for option in OPTIONS}

# Stock FreeCAD's own key, not one of ours: 0 is the drop-down, 1 the tab bar
# (Gui/Action.cpp, WorkbenchGroup::addTo). Setting it is the whole of point 2, and
# it is also the one change that outlives uninstalling the addon — which is why the
# addon says so in the report view when it makes it.
WORKBENCH_GROUP = "User parameter:BaseApp/Preferences/Workbenches"
SELECTOR_TYPE_KEY = "WorkbenchSelectorType"
SELECTOR_TAB_BAR = 1

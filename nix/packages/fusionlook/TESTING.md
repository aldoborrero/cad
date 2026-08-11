# Testing the Fusion Look pack

Two halves, tested two ways. The theme and the stylesheet generation are checked
headlessly by `nix flake check`; everything that only exists once Qt is drawing has
to be looked at, and that is the checklist at the bottom.

## What the automated check covers

```
nix flake check                      # ruff, mypy --strict, pytest
nix build .#checks.x86_64-linux.fusionlook
```

`nix/checks/fusionlook.nix` passes the *installed* FreeCAD's stylesheet directory in
as `FREECAD_STYLESHEETS`, so the two coverage tests are claims about the FreeCAD in
this flake rather than about a copy of its token list pasted into a test. The five
worth knowing about:

| Test | What would otherwise go unnoticed |
|---|---|
| `test_the_theme_defines_every_token_the_stylesheet_asks_for` | a token `FreeCAD.qss` uses and the theme does not define — the rule keeps the literal `@Name` and the widget it styled goes missing |
| `test_the_theme_covers_what_freecad_dark_covers` | upstream adding a token to its own theme that this one has not picked up |
| `test_the_colour_functions_agree_with_qcolor` | the `lighten`/`darken` arithmetic drifting from Qt's. The table it asserts against is measured, not written: `tools/qcolor_reference.py` prints it from a real `QColor` |
| `test_the_pack_names_itself_the_same_thing_everywhere` | a rename in one of the four places the pack's own name appears. FreeCAD joins them by string and falls back to `Classic` in silence |
| `test_the_workbench_tabs_are_addressed_through_their_container` | the `QTabBar#WbTabBar` trap: that object name is on the *container*, so the obvious selector matches nothing |

To run them by hand, outside the flake:

```
cd nix/packages/fusionlook
FREECAD_STYLESHEETS=$(nix build --no-link --print-out-paths nixpkgs#freecad)/share/Gui/Stylesheets \
  pytest -q tests
```

The FreeCAD-dependent tests skip, rather than fail, when that variable is unset.

The one thing pytest cannot check is whether FreeCAD's *own* metadata parser accepts
`package.xml` — `FreeCAD.Metadata` is not importable outside FreeCAD. Ask it directly
instead; this is the cheapest way to know the pack will be listed at all, since the
theme selector shows a pack only when its type reads exactly `Theme`:

```
nix shell nixpkgs#freecad --command freecadcmd -c "
import FreeCAD
m = FreeCAD.Metadata('nix/packages/fusionlook/package.xml')
print(m.Name, m.supportsCurrentFreeCAD())
for kind, items in m.Content.items():
    for i in items:
        print(kind, i.Name, repr(i.Type), repr(i.Subdirectory))
"
```

Last run, against FreeCAD 1.1.1:

```
Fusion Look True
preferencepack Fusion Dark Blue 'Theme' ''
workbench FusionTabs '' './'
```

## Installing it to look at

**In this repo** — nothing to do. `nix/packages/freecad.nix` already hands the pack to
FreeCAD with `--module-path`, and its declared preferences select the theme, so

```
nix develop
cad gui iotorero-mount/freecad     # or just: freecad
```

comes up in Fusion Dark Blue with the addon loaded. To go back to FreeCAD's own dark
theme, change `Theme = t "Fusion Dark Blue"` in `nix/packages/freecad.nix` to
`"FreeCAD Dark"` — the pack stays installed and stays selectable in Preferences.

**Against a stock FreeCAD**, which is the path an Addon Manager user takes:

```
mkdir -p ~/.local/share/FreeCAD/Mod
ln -s "$PWD/nix/packages/fusionlook" ~/.local/share/FreeCAD/Mod/FusionLook
nix shell nixpkgs#freecad --command freecad
```

Then Preferences ▸ General ▸ Theme ▸ **Fusion Dark Blue** ▸ Apply, and restart.

The symlink is the whole install: the directory is already in Addon Manager layout —
`package.xml` at the top, the preference pack in `Fusion Dark Blue/`, the addon under
`freecad/fusiontabs/`. `tests/`, `tools/` and `pyproject.toml` ride along harmlessly
when symlinked; the nix package leaves them out.

Note that `python3 -c "import FreeCAD"` does **not** work — FreeCAD's modules are not
on a plain interpreter's path. Use `freecadcmd -c "..."` for anything headless.

## Manual GUI checklist

Run through this after any change to the theme or the addon. Where a step can fail
quietly, the third column says what "failed" looks like.

### 1. The theme applies

| # | Do | Expect | Failure looks like |
|---|---|---|---|
| 1.1 | Preferences ▸ General ▸ Theme | "Fusion Dark Blue" is in the list | not listed → the pack's `<type>Theme</type>` is missing, or the directory is not under a module path |
| 1.2 | Select it, Apply, OK, restart | Panels and toolbars are a blue-grey (`#2a2e34`), not near-black | still FreeCAD Dark's black → the `.cfg` did not apply |
| 1.3 | Look at the menu bar and any tab strip | Distinctly darker than the toolbars, with no rule drawn between them | same colour → `MainWindow/Theme` is set but `parameters/Fusion Dark Blue.yaml` was not found; the tokens fell back |
| 1.4 | Open Preferences and look at buttons, fields, checkboxes | Fields are darker wells; the default button is tinted blue | any widget showing a literal `@SomeToken` colour → a missing token |
| 1.5 | 3D view background | This repo's `#1F1F1F` (its declared preference wins over the pack's lighter `#3f4348`) | — |
| 1.6 | Preferences ▸ Display ▸ UI ▸ accent colour | Autodesk blue `#2a9df4` | — |

### 2. Document tabs (FusionTabs point 1)

| # | Do | Expect |
|---|---|---|
| 2.1 | Open two documents | Their tabs are **above** the 3D view, not below |
| 2.2 | Look at the strip | Darker than the toolbar above it; the open document's tab is the toolbar colour with a 2 px blue edge along its top |
| 2.3 | Hover an inactive tab | It lightens; its text goes from grey to white |
| 2.4 | Hover a tab's ✕ | Small blue square behind the ✕, and it still closes the document |
| 2.5 | Drag a tab | Tabs still reorder (`setTabsMovable` is FreeCAD's, and nothing here should have disturbed it) |

### 3. Workbench tabs (FusionTabs points 2 and 3)

| # | Do | Expect |
|---|---|---|
| 3.1 | Look at the workbench selector | A row of tabs, not a drop-down |
| 3.2 | Look at the current workbench | White text, 2 px blue underline, **no** box or fill behind it |
| 3.3 | Hover another workbench | Quiet background, text brightens |
| 3.4 | Switch workbench, twice | The styling survives. This is the one most likely to break: the toolbar is rebuilt and the addon re-applies on a 600 ms timer |
| 3.5 | Click the **+** at the end of the strip | The overflow menu opens as usual |

### 4. It composes rather than replaces

| # | Do | Expect |
|---|---|---|
| 4.1 | Preferences ▸ General ▸ Theme ▸ FreeCAD Dark, restart | Everything is FreeCAD Dark *except* that the tabs keep their shape — and their colours are now FreeCAD Dark's, because the addon reads whatever theme is active |
| 4.2 | View ▸ Panels ▸ Report view, then restart | At log level, `FusionTabs: document and workbench tabs styled`. No warnings |

### 5. Turning it off

| # | Do | Expect |
|---|---|---|
| 5.1 | Preferences ▸ Display ▸ Fusion Tabs | Four checkboxes, all ticked |
| 5.2 | Untick "Put the document tabs above the 3D view", restart | Tabs are back at the bottom **and still styled** — the accent edge moves to the bottom of the tab |
| 5.3 | Untick all four, restart | Stock tab behaviour and stock tab appearance, theme untouched |

### 6. Clean uninstall

| # | Do | Expect |
|---|---|---|
| 6.1 | Remove the symlink from `~/.local/share/FreeCAD/Mod/` (or the entry from `nix/packages/freecad.nix`), restart | Tabs are back at the bottom, unstyled. No errors in the report view |
| 6.2 | Preferences ▸ General ▸ Theme | "Fusion Dark Blue" is gone from the list, and the theme in use falls back — pick FreeCAD Dark |
| 6.3 | Preferences ▸ Workbenches ▸ selector type | **Still a tab bar.** This is the one thing that outlives the addon: it is a stock FreeCAD preference, the addon says so in the report view when it sets it, and this dialog puts it back to a drop-down |

## Known gaps

* **The theme cannot style the two tab strips on its own.** FreeCAD's stylesheet is
  `defaults.qss` plus exactly one `.qss` file, with no include mechanism, so a theme
  that wanted to add a rule would have to fork the 2700-line `FreeCAD.qss`. The rules
  therefore live in the addon and are applied per widget. The practical consequence:
  **the theme alone does not give you Fusion's tabs** — the addon is not optional if
  that is what you are after.
* **`QTabBar#WbTabBar` is the wrong selector** and this is worth remembering before
  reaching for it in any other context: `WorkbenchTabWidget` puts that object name on
  itself, and the `QTabBar` it contains has none.
* The addon re-applies its stylesheets when the main window gains a child, which is
  how it survives toolbar rebuilds. If a future FreeCAD rebuilds the workbench
  selector without going through the main window's children, step 3.4 is where it
  will show up.
* The palette is **placeholders**. Everything in the marked block at the top of
  `Fusion Dark Blue/parameters/Fusion Dark Blue.yaml` is an approximation of Fusion's
  Dark Blue UI, not a measurement. Replace the five colours there and the rest of the
  file follows; then re-run the check, which asserts the contrast ratios rather than
  the colours themselves.

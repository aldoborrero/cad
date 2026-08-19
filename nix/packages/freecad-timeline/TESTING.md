# Timeline — manual test checklist

The automated suite (`pytest`) covers the data layer, the widget geometry and
the controller against fakes. It cannot cover anything that needs a running
FreeCAD GUI. This checklist does.

Run through it in a FreeCAD 1.0+ GUI build. Tick each box; note the FreeCAD
version and theme you used.

```
FreeCAD version: ______________   Qt: 5 / 6   Theme: ______________
```

## 0. Install

- [ ] Copy or symlink this directory into your `Mod` folder:
      `ln -s $PWD/freecad/Timeline ~/.local/share/FreeCAD/Mod/Timeline`
      (macOS: `~/Library/Application Support/FreeCAD/Mod`,
      Windows: `%APPDATA%\FreeCAD\Mod`)
- [ ] Restart FreeCAD. No errors appear in the Report view at startup.
- [ ] A **Timeline** dock appears at the bottom of the window.
- [ ] The dock is listed under **View → Panels**, and the checkbox there hides
      and shows it.
- [ ] Closing the dock with its X and re-running **Timeline_Show** from the
      Python console (`FreeCADGui.runCommand("Timeline_Show")`) brings it back.

## 1. Read-only timeline

- [ ] With no document open, the dock shows
      *"No active body — activate a PartDesign body to see its timeline."*
- [ ] Create a new document, switch to PartDesign, create a Body. The dock
      shows the body's name and *"This body has no features yet."*
- [ ] Sketch a rectangle and pad it. The Pad appears in the strip with its
      **PartDesign Pad icon** (not a placeholder square).
- [ ] Add a Fillet and a Pocket. Features appear **left to right in Group
      order**, matching the model tree top to bottom.
- [ ] Hover a feature: the tooltip shows the label, internal name, and state
      (`tip`, `suppressed`, `rolled back`).
- [ ] The sketch is **not** shown by default.
- [ ] Toggle **Sketches && datums** in the dock header: the sketch and any
      datum planes appear; toggle off again and they disappear.
- [ ] Add a datum plane. With the toggle on it appears; its context menu's
      *Set tip here* is greyed out (datums cannot be the tip).
- [ ] Many features (10+): a horizontal scrollbar appears, no vertical one,
      and the strip does not wrap to a second row.

## 2. Active body tracking

- [ ] Create a second Body in the same document. Double-click it in the tree to
      activate it: the timeline switches to the new body within a moment.
- [ ] Deactivate the body (double-click it again). Select a feature of a body
      in the tree — the timeline shows **that feature's body**.
- [ ] Open a second document with its own body. Switching tabs switches the
      timeline to the active document's body.
- [ ] **Close a document while the dock is open.** The dock must show the
      placeholder, not crash, and not print a `ReferenceError` traceback.
- [ ] Close all documents. Placeholder again, no errors.

## 3. Selection sync (both ways)

- [ ] Click a feature in the timeline: it becomes selected in the model tree
      and highlights in the 3D view.
- [ ] Click a feature in the model tree: it highlights in the timeline.
- [ ] Clear the selection (click empty space in the tree): the timeline
      highlight clears.
- [ ] Click rapidly back and forth between tree and timeline — no flicker
      loop, no runaway CPU.

## 4. Edit

- [ ] Double-click a Pad in the timeline: its task dialog opens.
- [ ] Cancel the dialog. The timeline is unchanged.
- [ ] Double-click a Fillet: its dialog opens. Change the radius, OK, and the
      timeline refreshes once (not per recompute step).

## 5. Tip / rollback

- [ ] The rollback marker (vertical rule with a handle on top) sits to the
      **right of the tip feature**.
- [ ] Features **after** the tip render dimmed; the tip's own label is bold.
- [ ] Drag the marker to the left, between two features, and release. The body
      rolls back: later features dim and the 3D view shows the earlier shape.
- [ ] Undo (Ctrl+Z) restores the previous tip in **one step**.
- [ ] Drag the marker to the far left (before everything). The body's Tip is
      cleared and everything dims.
- [ ] Drag it to the far right: the last solid becomes the tip.
- [ ] Right-click a feature → **Set tip here**: same effect as dragging.
- [ ] Right-click → **Move tip to end** restores the full model.
- [ ] With sketches shown, drag the marker onto a sketch's slot: a warning says
      only a solid feature can be the tip, and nothing changes.
- [ ] Hovering the marker shows a horizontal-resize cursor; hovering elsewhere
      does not.

## 5b. Error and out-of-date badges

- [ ] Break a feature deliberately: sketch a pocket larger than the pad so it
      removes everything, or delete a fillet's reference edge. The feature gets
      a **red ! badge** in the timeline.
- [ ] Hover it: the tooltip says *Recompute failed* and shows FreeCAD's own
      error text (the same message the Report view prints).
- [ ] The model tree marks the same feature with its error overlay — the two
      agree.
- [ ] Fix the feature. The badge disappears after the recompute.
- [ ] Touch a feature without recomputing (change a parameter with auto-recompute
      off, Edit → Preferences → General → Document → skip recomputes): it gets an
      **amber dot** and the tooltip says *Out of date*.
- [ ] Roll the tip back so a failed feature is dimmed, and suppress it. The
      badge stays at **full opacity** — it must not fade with the item.
- [ ] A feature whose label contains `<` `>` or `&` (e.g. `M6 <clearance> & tap`)
      shows correctly in the tooltip, with no missing text and no raw markup.

## 6. Suppress

- [ ] Right-click a Fillet → **Suppress**. It renders struck through and
      ghosted, and the 3D shape loses the fillet.
- [ ] The model tree shows the same feature as suppressed (consistent state).
- [ ] Right-click → **Unsuppress** restores it and the shape.
- [ ] Undo after a suppress reverts it in one step.
- [ ] Save, close, reopen the document: the suppressed state persists and the
      timeline shows it struck through.

## 7. Rename / delete

- [ ] Right-click → **Rename…**, enter a new label, OK. The strip and the model
      tree both show the new label.
- [ ] Rename to an empty string: rejected with a warning, nothing changes.
- [ ] Right-click a Fillet → **Delete**, confirm. It disappears from the
      timeline and the tree; the body recomputes; the tip falls back to the
      previous solid.
- [ ] Right-click a **Pad** → **Delete**. Because only the Pad uses its sketch,
      the dialog offers *Delete both* / *Feature only* / *Cancel*.
  - [ ] *Cancel* changes nothing.
  - [ ] *Feature only* removes the Pad and leaves the sketch in the body.
  - [ ] *Delete both* removes the sketch too.
- [ ] Undo after each delete restores everything in one step.

## 8. Drag-and-drop reorder

- [ ] Drag a feature to a different position. A dashed insertion line follows
      the cursor at the slot boundary.
- [ ] Drop it. The model tree order changes to match, and the body recomputes.
- [ ] The feature appears **exactly once** in the tree (no duplicate).
- [ ] Undo restores the original order in one step.
- [ ] Drag a feature onto its own position: nothing happens, no transaction in
      the undo stack.
- [ ] Drag the **tip** feature elsewhere: it stays the tip afterwards (the body
      does not silently roll back).
- [ ] Create an illegal order: sketch a pocket **on a face of a later pad**,
      then drag the pocket before that pad. A *Dependency violation* dialog
      appears naming the objects, and the order is **unchanged**.
- [ ] With a base feature (create a Part Box, then a Body based on it): the
      base feature cannot be dragged, and dropping another feature immediately
      after it puts that feature first in the body.

## 8c. Multi-selection and keyboard

- [ ] Ctrl-click two non-adjacent features: both highlight, and both become
      selected in the model tree.
- [ ] Shift-click to extend a range: the whole span highlights.
- [ ] Select several in the **tree**, and they all highlight in the timeline.
- [ ] Right-click **inside** a multi-selection: the menu says *Suppress N
      features* / *Delete N features* and the selection is not reduced.
- [ ] Right-click **outside** it: the selection collapses to that one feature,
      as in any list.
- [ ] **Suppress N features**: all of them go struck through in **one** undo
      step (a single Ctrl+Z brings them all back).
- [ ] With a mixed selection (some suppressed, some not), the action reads
      *Suppress* and suppresses everything. Only when all are already
      suppressed does it read *Unsuppress*.
- [ ] **Rename…** is greyed out for a multi-selection.
- [ ] **Delete N features** removes them all in one undo step.
- [ ] Drag a multi-selection: all of them move together, stay in their original
      relative order, and end up contiguous.
- [ ] Press mouse on a feature *outside* the current selection and drag: only
      that one moves.
- [ ] <kbd>Delete</kbd> deletes the selection (after the confirmation).
- [ ] <kbd>F2</kbd> opens the rename dialog for the focused feature.
- [ ] <kbd>Return</kbd> opens its task dialog.
- [ ] <kbd>←</kbd> / <kbd>→</kbd> still move along the strip.

## 8d. Language

- [ ] Switch FreeCAD to another language (Edit → Preferences → General) and
      restart. With no catalogue shipped for it the timeline stays English and
      nothing breaks — no missing labels, no tracebacks.
- [ ] If you have compiled a `.qm` into `resources/translations/`: the dock
      title, header button, context menu, placeholder and dialogs all appear
      translated.
- [ ] Undo labels in the Edit menu remain English (documented, intentional —
      the data layer is Qt-free).

## 8b. Persistence across sessions

- [ ] Turn on **Sketches && datums**, close FreeCAD, reopen: the toggle is
      still on and non-solids are shown.
- [ ] Close the dock with its X, restart FreeCAD: the dock does **not**
      reappear, but **View → Panels → Timeline** still lists it.
- [ ] Re-enable it from that menu, restart: it comes back on its own.
- [ ] Drag the dock to the **top** area and resize it, restart: it returns to
      the top at the same size (this is `restoreDockWidget`; a dock added from
      Python is created after FreeCAD restores window state, so without it the
      layout is lost).
- [ ] Tab the dock together with another bottom panel, restart: the tabbing is
      preserved.

## 9. Theme

Repeat for each theme, checking that **no colour is hardcoded**:

- [ ] **FreeCAD Light / default** — labels readable, dimmed features clearly
      fainter but legible, marker visible against the background.
- [ ] **FreeCAD Dark** — same.
- [ ] **ProDark** — same; the marker uses the theme accent, not a fixed orange.
- [ ] **OpenTheme Dark** — same.
- [ ] Switch theme with the dock open (Tools → Edit parameters, or the theme
      preference pack). The timeline repaints in the new palette without a
      restart.
- [ ] Selected item's highlight matches the rest of the UI's selection colour.

## 10. Undo/redo and stability

- [ ] Perform: set tip, suppress, rename, reorder, delete. Then press Ctrl+Z
      five times. Each action reverts one at a time, in order.
- [ ] Ctrl+Shift+Z (redo) reapplies them one at a time.
- [ ] The timeline tracks every undo/redo step.
- [ ] Recompute the whole document (Refresh). The timeline repaints **once**,
      not once per feature.
- [ ] Leave the dock open for a long editing session — no growing memory, no
      duplicated observers (check `Report view` for repeated warnings).

## Notes / failures

```
```

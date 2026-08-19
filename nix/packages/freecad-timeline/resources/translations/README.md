# Translations

Every user-facing string in the Qt layer goes through
`freecad_timeline.qtcompat.translate()`, which is a thin wrapper over
`QCoreApplication.translate("Timeline", ...)`. Calls resolve at runtime, so a
language FreeCAD sets after the addon has loaded still applies.

## Extracting strings

```sh
cd freecad/Timeline
pylupdate6 $(git ls-files '*.py') -ts resources/translations/Timeline_es-ES.ts
```

(`pylupdate5` on Qt5 builds. Any `lupdate` that understands Python works —
the calls are plain `translate("…")`, not a custom macro.)

Translate the `.ts` in Qt Linguist, then compile:

```sh
lrelease resources/translations/Timeline_es-ES.ts
```

Name files `Timeline_<locale>.ts` / `.qm`, matching FreeCAD's convention
(`Timeline_de.ts`, `Timeline_fr.ts`, `Timeline_zh-CN.ts`, …).

## Loading

`.qm` files in this directory are installed by
`freecad_timeline.translations.install()`, called from `InitGui.py` before the
dock is built. It uses `FreeCADGui.addLanguagePath()` so FreeCAD's own language
switcher picks the catalogues up and reloads them when the user changes
language.

## Plurals

Strings with `%n` (for example `Delete %n feature(s)?`) are passed a count so
translators can supply the plural forms their language needs. The source text
has to read acceptably on its own, because with no catalogue loaded Qt falls
back to it verbatim — hence the `(s)` phrasing rather than a bare plural.

## What is deliberately not translated

`model.py` and `commands.py` import no Qt, which is what lets the data layer be
tested headlessly. Their transaction names — the labels that appear in
**Edit ▸ Undo** — therefore stay English. Moving them behind a translation hook
would drag Qt into the layer the tests depend on being free of it.

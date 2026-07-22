# iotorero-mount

Outlet cradle for the round **Athom / IoTorero IR remote** (RF + IR, USB-C, ~20 g).
It rests on the rectangular USB charger plugged into a Schuko outlet; the puck hangs
in a cradle just below, with the excess cable tucked into a snap-in clip.

## How it works

- **Rectangular aperture** at the top slips over the charger brick → the mount rests on it.
- **Puck cradle** below: the flat base sits on an annular ledge; **discrete tabs over the
  lower semicircle** hug the straight wall, their **45° lips** hooking over the shoulder
  where the dome begins. The top is open — **slide the puck in/out from above** (so the
  tabs barely flex → durable for repeated in/out).
- **Cable clip** for the excess USB-C cable.

## Parameters

| Name | Meaning | Value |
|------|---------|-------|
| `DEVICE_DIA` | puck base Ø (measured 64.33) | 65 |
| `DEVICE_STRAIGHT` | straight wall height (edge) | 25 |
| `DEVICE_H` | total height at dome centre | 29 |
| `BRICK_W` / `BRICK_H` | charger face size | **TODO: measure** |
| `BRICK_FIT` | slip clearance over the brick | 0.6 |
| `LIP` / `LIP_H` | tab lip reach / height (45° chamfer) | 2 / 2.5 |
| `SHOW_PUCK` | preview the device in place | false |

> **Status:** device geometry is measured and final. The **charger brick dimensions are
> placeholders** — measure width/height/protrusion and update `BRICK_W`/`BRICK_H` before printing.

## Build

```sh
cad render iotorero-mount           # iso PNG -> exports/
cad render iotorero-mount side      # profile
cad export iotorero-mount           # STL (+3MF)
cad gui    iotorero-mount           # tweak interactively (toggle SHOW_PUCK)
```

## Print notes

- **PETG** recommended (durability + layer adhesion; the puck is cycled in/out).
- **Plate flat on the bed, tabs pointing up.** No supports: lips are 45° self-supporting.
- Slide the puck in from the open top; do not force it straight in.

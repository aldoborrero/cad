# espmmwave-v0.2.0

Review draft: hardware operation, enclosure fit and the ESPHome build still need
validation. Read the checks and limitations below before fabrication.

A 45 × 45 mm ESPHome presence sensor: a Seeed XIAO ESP32S3 carrying a Hi-Link HLK-LD2450
24 GHz mmWave radar, in a Hammond 1551V3GY case.

This is a **KiCad rebuild** of `mplinuxgeek/ESPmmWave-LD2450`, which publishes fabrication
output rather than source — gerbers from EasyEDA, no `.kicad_*` file anywhere. The outline,
the drill pattern and every measured coordinate here were parsed out of those gerbers and
are reproduced to the micron; the netlist was recovered by tracing the copper. See
`tools/board.py` for how, and [Differences](#differences-from-the-original) for what
changed on purpose.

## Bill of materials

| Ref | Value | Footprint | Part |
|-----|-------|-----------|------|
| U1 | XIAO_ESP32S3 | `espmmwave:XIAO_ESP32S3` (this project's own) | Seeed Studio XIAO ESP32S3 |
| J2 | HLK-LD2450 | `PinHeader_2x04_P2.00mm_Vertical` | header the radar module plugs into |
| J1 | Power in | `JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical` | 2-pin JST-XH, optional (USB-C also powers it) |
| D1 | WS2812B | `LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm` | status LED, on D3 / GPIO4 |
| **R1** | **330 Ω** | `R_0603_1608Metric` | **added** — series damping on the LED data line |
| **C1** | **100 nF** | `C_0603_1608Metric` | **added** — decoupling at the LED |
| **C2** | **47 µF** | `C_1206_3216Metric` | **added** — bulk at the power inlet |

The three in bold are **not on the original board**: upstream's hardware list is the XIAO,
the radar, the case, a USB-C cable and two optional parts (the LED and the JST). It carries
no passives at all.

Not on the PCB, but needed to build one:

| Item | Note |
|------|------|
| Hammond **1551V3GY** | vented ABS case the outline is cut for. Mouser [1551V3GY](https://www.mouser.com/ProductDetail/Hammond-Manufacturing/1551V3GY) — hammfg.com refuses automated fetches, so that is a distributor page rather than the manufacturer's |
| 4 × M2.5 × 6 mm screws | board to case, and the bracket to the board |
| LD2450 bracket | `STL/LD2450 PCB Bracket.stl` in the upstream repo — not reproduced here |

## Datasheets

| For | Document |
|-----|----------|
| XIAO ESP32S3 | [Getting started](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/) · [Package and PCB design](https://wiki.seeedstudio.com/XIAO_Series_Package_and_PCB_Design/) (the footprint dimensions) |
| HLK-LD2450 | [Operation manual](https://d.hlktech.net/download/HLK-LD2450/1/HLK-LD2450%20operation%20manual.doc..pdf) · [Serial protocol v1.03](https://make.net.za/wp-content/datasheets/HLK%20LD2450%20Serial%20Communication%20Protocol%20v1.03.pdf) · [Hi-Link product page](https://www.hlktech.net/index.php?id=1157) |
| WS2812B | [Datasheet](https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf) (Worldsemi, mirrored by Adafruit) |
| ESPHome | [`ld2450` component](https://esphome.io/components/sensor/ld2450/) · [`neopixelbus` light](https://esphome.io/components/light/neopixelbus/) |

Two of these earned their place rather than decorating the page.

**The serial protocol document settled the radar pinout.** Its *Table 1 – Pin definition*
gives the 2×4 header as two columns — `5V / 3V3 / PA9 / GND` against `Rx / Tx / DP / DM` —
which is what `board.py` encodes, and it is not guesswork: the assignment was traced off
the original board's copper and agrees three ways, with that table, with Seeed's pin map,
and with the GPIO numbers in the ESPHome config. Only **one** of the eight pins is ground.

**The WS2812B datasheet defines the trade-off this board makes**, and it cuts both ways:

```
VDD  Power supply voltage    +3.5 ~ +5.3 V
VIH  Logic high input        0.7 × VDD
```

At VDD = 5 V the LED needs 3.5 V to read a high, and the ESP32-S3 drives 3.3 V — inside the
undefined band, which is the classic works-on-the-bench failure. This board runs the LED at
**3V3** instead, putting VIH at 2.31 V with about a volt of margin. Be aware of what that
costs: **3.3 V is below the datasheet's 3.5 V minimum supply**, so the LED is out of spec on
its rail rather than on its input. It is a status indicator and the swap costs only
brightness, but it is a considered trade rather than a clean fix. A 74AHCT125 buffer, or a
diode dropping 5 V to ~4.3 V, are the two ways to be in spec on both counts.

## Board

| | |
|---|---|
| Outline | 45 × 45 mm, corner radius 2.5 mm |
| Mounting | 4 × Ø2.90 mm on a 29 × 38 mm pattern |
| Layers | 2, ground pour on both |
| Thickness | **1.6 mm — KiCad's default, not a decision.** `board.py` never sets it, and upstream recommends **1.0 or 1.2 mm**. Set it before ordering |

## Build

```sh
cad render espmmwave-v0.2.0 [iso|top|bottom|front|back|left|right]   # raytraced PNG
cad export espmmwave-v0.2.0     # STEP, for the mechanical side
cad gui    espmmwave-v0.2.0     # open the project in KiCad
```

From the project directory, with direnv active:

```sh
check                    # the everyday command: do the board and the schematic agree?
board      --regenerate  # rebuild the .kicad_pcb from the measured geometry
```

**Both KiCad files are edited and kept** — in eeschema and pcbnew, or through the Konnect
MCP server after registering it with your MCP client. `board` refuses to write
without `--regenerate`, because it rebuilds the whole file from scratch: there is no merge,
and an edit made in the editor would simply be gone.

There is no schematic generator any more, and no net class script. Both existed to write
files KiCad is perfectly able to write itself, and the net class one existed only to undo
KiCad's habit of rewriting `.kicad_pro` on close — which stops being a problem once KiCad is
the only thing writing it. **Net classes now live where KiCad keeps them**: Schematic Setup →
Net Classes, three of them (`Power` red and thick, `Radar` blue, `LED` green), matched by
pattern. Mind the leading slash there: a rail is `GND`, a plain label is `/LED_DATA`.

**The schematic owns connectivity; the board owns geometry.** That is KiCad's own direction
of travel, and when `board --regenerate` does run, it reads the netlist out of the schematic
— the half of *Update PCB from Schematic* that matters here, and the only description of the
circuit there is.
Doing it in code keeps something the dialog would take away: it offers to delete footprints
with no symbol, and the four mounting holes are exactly that, anonymous footprints carrying
the Ø2.90 pattern that fixes the board in its enclosure. Eleven footprints on the board,
seven symbols on the sheet — that difference is not an error to be tidied away.

So the loop is: **edit either file → run `check`.**

`check` is what replaces the guarantee that generating both files used to give for free.
It runs three checks that fail for different reasons: the board's pad-to-net assignment
against the schematic's netlist, every symbol's instance reference and root-sheet path — a
thing `kicad-cli sch erc` is structurally blind to, see the repo's `CLAUDE.md` — and KiCad's
own ERC and DRC. All three are proven to fail as well as pass: rename a label and it names
both sides of the divergence; delete one track segment and it reports 2 DRC violations and
1 unconnected pad. Exit 1 either way.

The measured geometry in `board.py` is the one thing kept as bootstrap: `board --regenerate`
rebuilds the outline, the drill pattern and the placement from it, and asserts itself on the
way past — `check_pads()` fails unless every pad lands on a hole the original drill file
actually contains. That is worth keeping because KiCad cannot do it: there is no way to
import a board from gerbers, which is the whole reason this project exists.

## ESPHome

`esphome/espmmwave-v0.2.0.yaml`, adapted from upstream's `yaml/example.yaml`. Copy
`esphome/secrets.yaml.example` to `secrets.yaml`, fill it in, then `esphome run`.

The 1085-line `ld2450-base.yaml` is **not** vendored here. Upstream's own example does not
use its local copy either — that line is commented out in favour of a `github://` reference
to EverythingSmartHome's original, which is what actually runs, and which ESPHome fetches
at build time.

Firmware and copper agree without any override: the base config hardcodes `tx_pin: GPIO9`
and `rx_pin: GPIO8`, and on the XIAO those are `D10` and `D9` — exactly where this board
routes `RADAR_RX` and `RADAR_TX`.

Worth knowing: upstream's README says the LD2450 is "NOT yet officially supported in
ESPHome". **That is now out of date** — ESPHome ships an official
[`ld2450`](https://esphome.io/components/sensor/ld2450/) platform, so the borrowed base
package is no longer the only route. Moving to it would drop the external dependency
entirely. Not done here, because it is a rewrite of the sensor and zone entities rather
than a swap.

## Differences from the original

**Source, not output.** Upstream ships gerbers, an STL and YAML. This is a KiCad project
that regenerates the board and a schematic from one netlist. Upstream publishes no
schematic at all.

**Three passives added** — `R1` 330 Ω in series with the LED data line, `C1` 100 nF across
the LED's supply, `C2` 47 µF of bulk at the inlet. The first two are what the WS2812B
datasheet asks for; the bulk is because the ESP32-S3 pulls ~350 mA spikes when the radio
keys up and the LD2450 is an RF module of its own, both at the far end of whatever cable
feeds J1. Neither the original nor the first draft of this board had any of them.

**The LED moved from 5 V to 3V3**, for the logic-threshold reason set out under
[Datasheets](#datasheets), with the supply-range caveat that comes with it.

**Ground pour on both layers.** Measured during the rebuild: 1625 mm² on the front and
1751 mm² on the back, against about 1974 mm² per face on the original, which also pours on
both. An earlier draft of this board poured on the back only — copper on one face alone
warps at reflow, quite apart from the return path.

**Set the thickness before ordering.** See [Board](#board).

## Credits

The original design is **[ESPmmWave-LD2450](https://github.com/mplinuxgeek/ESPmmWave-LD2450)**
by **MartinP** ([@mplinuxgeek](https://github.com/mplinuxgeek)), published under the MIT
licence (declared in their README; the repository carries no `LICENSE` file). The board
outline, the drill pattern, the component placement and the enclosure choice are all
theirs — this project measured them, it did not invent them.

The ESPHome configuration descends from **[Everything Presence
Lite](https://github.com/EverythingSmartHome/everything-presence-lite)** by
**EverythingSmartHome**, which upstream credits plainly in their README: *"The code was
mostly borrowed from EverythingSmartHome with some changes to suit my use case."*

One caveat on that chain, since it affects anyone reusing this. Everything Presence Lite
**declares no licence** — no `LICENSE` file, and GitHub detects none — which by default
means all rights reserved. Upstream's blanket MIT therefore sits over a file that is
"mostly borrowed" from an unlicensed project. That is why `ld2450-base.yaml` is referenced
here rather than copied: referencing it leaves the licensing question where it belongs,
with its author, instead of quietly restating it as ours.

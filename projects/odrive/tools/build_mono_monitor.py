#!/usr/bin/env python3
"""Build the STM32F405 mono diagnostic image; never flash or start motor PWM.

Requires explicitly supplied CMSIS, GNU ARM tools and diagnostic UV/OV settings.
The default image monitors the bus. An explicit driver profile adds GPIO wake,
SPI configuration in COAST and retained fault monitoring; it can raise ENABLE.
An additional current profile runs one manual B/C zero calibration in COAST.
An additional timing profile transfers calibration into continuous internal TIM1/ADC
capture with GPIO PWM LOW and COAST retained.
No source/toolchain downloads, board writes or runtime qualification are performed.
"""

import argparse
import hashlib
import json
import math
import struct
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmsis-root", type=Path, required=True)
    parser.add_argument("--arm-gcc", type=Path, required=True)
    parser.add_argument("--undervoltage", type=float, required=True)
    parser.add_argument("--overvoltage", type=float, required=True)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument(
        "--driver-config",
        type=Path,
        help="Explicit JSON gate/timing profile for COAST-only driver diagnostic",
    )
    parser.add_argument(
        "--current-config",
        type=Path,
        help="Explicit JSON current/zero/capture profile; requires --driver-config",
    )
    parser.add_argument(
        "--timing-config",
        type=Path,
        help="Explicit internal TIM1/ADC timing profile; requires --current-config; no motor PWM",
    )
    args = parser.parse_args()
    if args.timing_config and not args.current_config:
        parser.error("--timing-config requires --current-config")
    if args.current_config and not args.driver_config:
        parser.error("--current-config requires --driver-config")
    if not (
        math.isfinite(args.undervoltage)
        and math.isfinite(args.overvoltage)
        and 0 < args.undervoltage < args.overvoltage < 66
    ):
        parser.error(
            "Require finite 0 < undervoltage < overvoltage < 66 V; not production qualification"
        )
    root = Path(__file__).resolve().parents[3]
    source = root / "projects/odrive/firmware/mono56"
    build = (
        args.build_dir
        or root
        / (
            ".scratch/v4-56v-implementation/timing-monitor-image"
            if args.timing_config
            else ".scratch/v4-56v-implementation/current-monitor-image"
            if args.current_config
            else ".scratch/v4-56v-implementation/driver-monitor-image"
            if args.driver_config
            else ".scratch/v4-56v-implementation/monitor-image"
        )
    ).resolve()
    cmsis = args.cmsis_root.resolve()
    gcc = args.arm_gcc.absolute()
    if not str(gcc).endswith("gcc"):
        parser.error("--arm-gcc must name arm-none-eabi-gcc beside its companion tools")
    prefix = str(gcc).removesuffix("gcc")
    for suffix in ("gcc", "g++", "objcopy", "nm", "readelf", "size"):
        if not Path(prefix + suffix).is_file():
            parser.error(f"Missing tool: {prefix + suffix}")
    headers = [cmsis / "Include", cmsis / "Device/ST/STM32F4xx/Include"]
    if not (headers[1] / "stm32f405xx.h").is_file():
        parser.error("CMSIS root lacks STM32F405 device header")
    build.mkdir(parents=True, exist_ok=True)
    (build / "validation.json").unlink(missing_ok=True)
    driver_profile = None
    generated_config = None
    if args.driver_config:
        driver_profile = json.loads(args.driver_config.read_text())
        gate_keys = [
            "hs_source_ma",
            "hs_sink_ma",
            "ls_source_ma",
            "ls_sink_ma",
            "drive_time_ns",
            "dead_time_ns",
            "vds_trip_mv",
            "ocp_deglitch_us",
            "csa_gain",
            "sense_trip_mv",
        ]
        timing_keys = [
            "sleep_us",
            "wake_us",
            "feedback_timeout_us",
            "max_service_gap_us",
            "spi_deadline_us",
            "bus_wait_timeout_us",
            "register_check_period_us",
        ]
        if not isinstance(driver_profile, dict) or set(driver_profile) != {
            "gate",
            "timing",
        }:
            parser.error("Driver JSON must contain exactly gate and timing objects")
        for section, keys in [("gate", gate_keys), ("timing", timing_keys)]:
            values = driver_profile[section]
            if not isinstance(values, dict) or set(values) != set(keys):
                parser.error(f"Driver {section} requires exactly: {', '.join(keys)}")
            for key, value in values.items():
                limit = (
                    255
                    if key in ["ocp_deglitch_us", "csa_gain"]
                    else 65535
                    if section == "gate"
                    else 1000000
                )
                if type(value) is not int or not 0 < value <= limit:
                    parser.error(f"Invalid positive integer for {section}.{key}")
        t = driver_profile["timing"]
        if not (
            t["sleep_us"] >= 1001
            and t["wake_us"] >= 1001
            and t["max_service_gap_us"] >= 125
            and 60 <= t["spi_deadline_us"] <= 1000
            and t["spi_deadline_us"] < t["max_service_gap_us"]
        ):
            parser.error(
                "Driver timing violates sleep/wake, SPI or service constraints"
            )
        generated_config = build / "monitor_driver_config.h"
        gate = ", ".join(str(driver_profile["gate"][key]) for key in gate_keys)
        timing = ", ".join(str(t[key]) for key in timing_keys)
        generated_config.write_text(
            '#pragma once\n#include "driver_monitor.hpp"\nnamespace odrive::mono56 {\ninline constexpr DriverMonitorConfig monitor_driver_config{{'
            + gate
            + "}, "
            + timing
            + "};\n}\n"
        )
    current_profile = None
    generated_current_config = None
    if args.current_config:
        current_profile = json.loads(args.current_config.read_text())
        current_keys = [
            "shunt_b_uohm",
            "shunt_c_uohm",
            "polarity_b",
            "polarity_c",
            "max_age_us",
            "max_pair_skew_us",
            "max_supply_skew_us",
            "max_zero_age_us",
            "vdda_min_mv",
            "vdda_max_mv",
            "rail_margin_mv",
            "max_abs_phase_current_ma",
            "max_zero_offset_codes",
            "max_calibration_supply_change_mv",
        ]
        zero_keys = [
            "samples",
            "settle_us",
            "min_span_us",
            "timeout_us",
            "max_peak_to_peak_codes",
        ]
        capture_keys = ["period_us", "deadline_us"]
        if not isinstance(current_profile, dict) or set(current_profile) != {
            "current",
            "zero",
            "capture",
        }:
            parser.error(
                "Current JSON requires exactly current, zero and capture objects"
            )
        for section, keys in [
            ("current", current_keys),
            ("zero", zero_keys),
            ("capture", capture_keys),
        ]:
            values = current_profile[section]
            if not isinstance(values, dict) or set(values) != set(keys):
                parser.error(f"Current {section} requires exactly: {', '.join(keys)}")
            for key, value in values.items():
                if type(value) is not int or (
                    value not in (-1, 1)
                    if key.startswith("polarity_")
                    else not 0 < value <= 1000000
                ):
                    parser.error(f"Invalid integer for {section}.{key}")
        c, z, a = (current_profile[k] for k in ["current", "zero", "capture"])
        gain = driver_profile["gate"]["csa_gain"]
        if not (
            c["shunt_b_uohm"] == c["shunt_c_uohm"] == 1000
            and gain in (5, 10, 20, 40)
            and 2400 <= c["vdda_min_mv"] < c["vdda_max_mv"] <= 3600
            and c["rail_margin_mv"] >= 250
            and c["max_zero_offset_codes"] < 2048
            and c["max_calibration_supply_change_mv"]
            <= c["vdda_max_mv"] - c["vdda_min_mv"]
            and c["max_pair_skew_us"] <= c["max_age_us"]
            and c["max_supply_skew_us"] <= c["max_age_us"]
            and 2 <= z["samples"] <= 4096
            and z["max_peak_to_peak_codes"] < 4095
            and 3 <= a["deadline_us"] < a["period_us"] - 1
            and a["deadline_us"] + 1 <= c["max_pair_skew_us"]
            and z["settle_us"] + z["min_span_us"] + a["deadline_us"] + 1
            <= z["timeout_us"]
        ):
            parser.error(
                "Current profile violates board scaling, supply, sampling or collection bounds"
            )
        headroom_mv = (
            c["vdda_min_mv"] / 2
            - c["rail_margin_mv"]
            - c["max_zero_offset_codes"] * c["vdda_max_mv"] / 4096
        )
        if c["max_abs_phase_current_ma"] * gain * 0.001 >= headroom_mv:
            parser.error("Current limit exceeds conservative amplifier headroom")
        values = [
            "0.001f",
            "0.001f",
            str(gain),
            str(c["polarity_b"]),
            str(c["polarity_c"]),
        ]
        values += [str(c[k]) for k in current_keys[4:8]]
        values += [f"{c[k] / 1000!r}f" for k in current_keys[8:12]]
        values += [
            f"{c['max_zero_offset_codes']}.0f",
            f"{c['max_calibration_supply_change_mv'] / 1000!r}f",
        ]
        generated_current_config = build / "monitor_current_config.h"
        generated_current_config.write_text(
            '#pragma once\n#include "current_monitor.hpp"\nnamespace odrive::mono56 {\ninline constexpr CurrentMonitorConfig monitor_current_config{{'
            + ", ".join(values)
            + "}, {"
            + ", ".join(str(z[k]) for k in zero_keys)
            + "}, "
            + str(a["period_us"])
            + ", "
            + str(a["deadline_us"])
            + "};\n}\n"
        )
    timing_profile = None
    generated_timing_config = None
    if args.timing_config:
        timing_profile = json.loads(args.timing_config.read_text())
        groups = {
            "sampling": [
                "half_period_ticks",
                "dead_time_ns",
                "low_side_settle_ns",
                "edge_margin_ns",
                "min_input_pulse_ns",
                "arm_budget_ns",
                "completion_service_ns",
            ],
            "timing": [
                "boundary_budget_ns",
                "commit_budget_ns",
                "adc_deadline_us",
                "min_trigger_spacing_us",
            ],
            "compares": ["a", "b", "c"],
        }
        if not isinstance(timing_profile, dict) or set(timing_profile) != set(groups):
            parser.error(
                "Timing JSON requires exactly sampling, timing and compares objects"
            )
        for group, keys in groups.items():
            values = timing_profile[group]
            if not isinstance(values, dict) or set(values) != set(keys):
                parser.error(f"Timing {group} requires exactly: {', '.join(keys)}")
            for key, value in values.items():
                limit = (
                    65535
                    if group == "compares" or key == "half_period_ticks"
                    else 1000000
                )
                if type(value) is not int or not 0 < value <= limit:
                    parser.error(
                        f"Timing {group}.{key} must be an integer in 1..{limit}"
                    )
        sampling = timing_profile["sampling"]
        timing = timing_profile["timing"]
        if sampling["half_period_ticks"] < 2 or any(
            v >= sampling["half_period_ticks"]
            for v in timing_profile["compares"].values()
        ):
            parser.error("Timing compares must be strictly inside the half-period")
        if (
            timing["adc_deadline_us"] < 3
            or timing["min_trigger_spacing_us"] <= timing["adc_deadline_us"]
        ):
            parser.error(
                "Timing requires ADC deadline >=3 us and strictly greater trigger spacing"
            )
        generated_timing_config = build / "monitor_timing_config.h"
        generated_timing_config.write_text(
            '#pragma once\n#include "timing_monitor.hpp"\nnamespace odrive::mono56 {\n'
            "inline constexpr TimingMonitorConfig monitor_timing_config{{"
            + ", ".join(str(sampling[k]) for k in groups["sampling"])
            + "}, "
            + ", ".join(str(timing[k]) for k in groups["timing"])
            + ", "
            + ", ".join(str(timing_profile["compares"][k]) for k in groups["compares"])
            + "};\n}\n"
        )
    commands = []

    def run(argv: list[str]) -> str:
        result = subprocess.run(
            argv, cwd=root, capture_output=True, text=True, check=False
        )
        commands.append(
            {"argv": argv, "stdout": result.stdout, "stderr": result.stderr}
        )
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            result.check_returncode()
        return result.stdout

    flags = [
        "-mcpu=cortex-m4",
        "-mthumb",
        "-mfpu=fpv4-sp-d16",
        "-mfloat-abi=hard",
        "-O2",
        "-g3",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fno-builtin",
        "-ffunction-sections",
        "-fdata-sections",
        "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables",
        "-I" + str(source / "include"),
        "-I" + str(source / "monitor"),
        *[flag for path in headers for flag in ["-isystem", str(path)]],
    ]
    if driver_profile:
        flags += ["-DMONO56_MONITOR_DRIVER", "-I" + str(build)]
    if current_profile:
        flags += ["-DMONO56_MONITOR_CURRENT"]
    if timing_profile:
        flags += ["-DMONO56_MONITOR_TIMING"]
    sources = sorted((source / "src").glob("*.c")) + sorted(
        (source / "src").glob("*.cpp")
    )
    sources += [source / "monitor" / name for name in ("startup.c", "monitor.cpp")]
    if driver_profile:
        sources.append(source / "monitor/driver_monitor.cpp")
    if current_profile:
        sources.append(source / "monitor/current_monitor.cpp")
    if timing_profile:
        sources.append(source / "monitor/timing_monitor.cpp")
    objects = []
    for file in sources:
        cpp = file.suffix == ".cpp"
        language = (
            ["-std=c++17", "-fno-exceptions", "-fno-rtti"]
            if cpp
            else ["-std=c11", "-ffreestanding"]
        )
        obj = build / (file.stem + ".o")
        run(
            [
                prefix + ("g++" if cpp else "gcc"),
                *flags,
                *language,
                f"-DMONO56_MONITOR_UV={args.undervoltage!r}f",
                f"-DMONO56_MONITOR_OV={args.overvoltage!r}f",
                "-c",
                str(file),
                "-o",
                str(obj),
            ]
        )
        objects.append(str(obj))
    elf = build / "mono56-monitor.elf"
    binary = build / "mono56-monitor.bin"
    ihex = build / "mono56-monitor.hex"
    vectors_file = build / "vectors.bin"
    script = source / "monitor/stm32f405-monitor.ld"
    run(
        [
            prefix + "g++",
            *flags,
            "-nostdlib",
            "-Wl,--gc-sections",
            "-Wl,--fatal-warnings",
            "-T" + str(script),
            "-Wl,-Map=" + str(build / "monitor.map"),
            *objects,
            "-o",
            str(elf),
        ]
    )
    for format_name, output in (("binary", binary), ("ihex", ihex)):
        run([prefix + "objcopy", "-O", format_name, str(elf), str(output)])
    run([prefix + "objcopy", "--dump-section", f".isr_vector={vectors_file}", str(elf)])
    raw = elf.read_bytes()
    if raw[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<HH", raw, 16) != (2, 40):
        raise RuntimeError("Expected a linked 32-bit little-endian ARM executable")
    entry = struct.unpack_from("<I", raw, 24)[0]
    symbols = {}
    for line in run([prefix + "nm", "-n", str(elf)]).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    if run([prefix + "nm", "-u", str(elf)]).strip():
        raise RuntimeError("Image contains unresolved symbols")
    attributes = run([prefix + "readelf", "-A", str(elf)])
    if "VFP registers" not in attributes or "v7E-M" not in attributes:
        raise RuntimeError("Missing Cortex-M4 / hard-float image attributes")
    vectors = struct.unpack("<98I", vectors_file.read_bytes())
    if vectors[0] != 0x20020000 or vectors[1] != entry or not entry & 1:
        raise RuntimeError("Invalid initial stack or Thumb reset vector")
    expected_vectors = {
        1: "Reset_Handler",
        71: "TIM7_IRQHandler",
        72: "DMA2_Stream0_IRQHandler",
    }
    expected_vectors.update(
        {34: "ADC_IRQHandler", 66: "TIM5_IRQHandler"}
        if current_profile
        else {34: "Default_Handler", 66: "Default_Handler"}
    )
    expected_vectors[41] = (
        "TIM1_UP_TIM10_IRQHandler" if timing_profile else "Default_Handler"
    )
    for index, name in expected_vectors.items():
        if vectors[index] != symbols[name] | 1:
            raise RuntimeError(f"Incorrect vector {index}: {name}")
    for index in (2, 3, 4, 5, 6):
        if vectors[index] != symbols["Default_Handler"] | 1:
            raise RuntimeError(
                f"Exception {index} does not enter the inhibiting handler"
            )
    for vector in vectors[1:]:
        if vector and (not vector & 1 or not 0x08000000 <= vector < 0x080C0000):
            raise RuntimeError("Handler vector outside executable Flash/Thumb range")
    if not 0x20000000 <= symbols["frame_buffer"] <= 0x2001FFFC:
        raise RuntimeError("ADC DMA buffer is outside accessible SRAM")
    if symbols["frame_buffer"] % 4:
        raise RuntimeError("ADC DMA buffer is not aligned")
    if not 392 <= binary.stat().st_size <= 768 * 1024:
        raise RuntimeError("Image is empty or exceeds reserved Flash area")
    if driver_profile:
        for name in [
            "mono56_driver_monitor",
            "mono56_driver_monitor_fault",
            "mono56_driver_monitor_step",
            "mono56_drv8353_spi3_exchange",
        ]:
            if name not in symbols:
                raise RuntimeError(f"Driver diagnostic lacks linked symbol: {name}")
        if any("release_coast" in name for name in symbols):
            raise RuntimeError("COAST-only image unexpectedly links COAST release")
    elif "mono56_driver_monitor" in symbols:
        raise RuntimeError("Bus-only image unexpectedly includes driver startup")
    if current_profile:
        for name in [
            "mono56_current_monitor",
            "mono56_current_capture_start",
            "mono56_current_capture_adc_irq",
            "mono56_current_capture_deadline_irq",
        ]:
            if name not in symbols:
                raise RuntimeError(f"Current diagnostic lacks linked symbol: {name}")
        for transition in ["begin_current_calibration", "end_current_calibration"]:
            if not any(transition in name for name in symbols):
                raise RuntimeError(
                    f"Current diagnostic lacks linked transition: {transition}"
                )
    elif "mono56_current_monitor" in symbols:
        raise RuntimeError("Non-current diagnostic unexpectedly includes calibration")
    if timing_profile:
        for name in [
            "mono56_timing_monitor",
            "mono56_current_capture_release",
            "TIM1_UP_TIM10_IRQHandler",
        ]:
            if name not in symbols:
                raise RuntimeError(f"Timing diagnostic lacks linked symbol: {name}")
        for transition in [
            "begin_timing",
            "pwm_capture_start",
            "pwm_capture_queue",
            "pwm_capture_take",
        ]:
            if not any(transition in name for name in symbols):
                raise RuntimeError(
                    f"Timing diagnostic lacks linked transition: {transition}"
                )
    size_output = run([prefix + "size", str(elf)])
    files = sources + [script, Path(__file__).resolve()]
    files += list((source / "include").glob("*")) + list(
        (source / "monitor").glob("*.h")
    )
    files += list((source / "monitor").glob("*.hpp"))
    if generated_config:
        files += [generated_config, args.driver_config.resolve()]
    if generated_current_config:
        files += [generated_current_config, args.current_config.resolve()]
    if generated_timing_config:
        files += [generated_timing_config, args.timing_config.resolve()]
    files += [p for directory in headers for p in directory.glob("*.h")]
    evidence = {
        "scope": "Linked diagnostic ARM image with static ELF/vector/DMA-memory checks",
        "mode": "calibrated-internal-timing"
        if timing_profile
        else "current-zero-coast"
        if current_profile
        else "driver-coast"
        if driver_profile
        else "bus-only",
        "driver_profile": driver_profile,
        "current_profile": current_profile,
        "can_raise_driver_enable": bool(driver_profile),
        "can_start_pwm": False,
        "can_start_internal_tim1": bool(timing_profile),
        "timing_profile": timing_profile,
        "runtime_tested": False,
        "motor_control_firmware": False,
        "flashed": False,
        "settings_are_qualified": False,
        "diagnostic_uv_v": args.undervoltage,
        "diagnostic_ov_v": args.overvoltage,
        "hse_hz": 8000000,
        "hclk_hz": 168000000,
        "pclk1_hz": 42000000,
        "pclk2_hz": 84000000,
        "compiler": run([prefix + "gcc", "--version"]),
        "commands": commands,
        "entry": entry,
        "dma_buffer": symbols["frame_buffer"],
        "size": size_output,
        "source_sha256": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
        "artifacts": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [elf, binary, ihex]
        },
    }
    (build / "validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(size_output.strip())
    print(f"Diagnostic image and static evidence: {build}; no device programmed")


if __name__ == "__main__":
    main()

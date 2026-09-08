#!/usr/bin/env python3
"""Test mono firmware components and compile production code for Cortex-M4.

GNU ARM builds C/C++ and combines the objects; Clang checks the C sources.
Neither produces a linked/flashable firmware image. CMSIS
must be supplied explicitly; no upstream sources or toolchains are downloaded.
"""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmsis-root", type=Path, required=True)
    parser.add_argument("--arm-clang", type=Path)
    parser.add_argument(
        "--arm-gcc", type=Path, help="arm-none-eabi-gcc beside g++, ld, nm and readelf"
    )
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--build-dir", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    source = repo / "projects/odrive/firmware/mono56"
    build = (
        args.build_dir or repo / ".scratch/v4-56v-implementation/firmware-components"
    ).resolve()
    cmsis = args.cmsis_root.resolve()
    clang = args.arm_clang.absolute() if args.arm_clang else None
    gcc = args.arm_gcc.absolute() if args.arm_gcc else None
    cmake = shutil.which(args.cmake)
    if cmake is None or not (clang or gcc):
        parser.error("Supply CMake and at least one of --arm-clang / --arm-gcc")
    for compiler in (clang, gcc):
        if compiler and not compiler.is_file():
            parser.error(f"Compiler does not exist: {compiler}")
    headers = [cmsis / "Include", cmsis / "Device/ST/STM32F4xx/Include"]
    if not (headers[1] / "stm32f405xx.h").is_file():
        parser.error("CMSIS root does not contain the STM32F405 device header")
    ctest = Path(cmake).with_name("ctest")
    commands = []
    build.mkdir(parents=True, exist_ok=True)
    (build / "validation.json").unlink(missing_ok=True)

    def run(command: list[str]) -> str:
        result = subprocess.run(
            command, cwd=repo, check=False, capture_output=True, text=True
        )
        commands.append(
            {"argv": command, "stdout": result.stdout, "stderr": result.stderr}
        )
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            result.check_returncode()
        return result.stdout

    run(
        [
            cmake,
            "-S",
            str(source),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DMONO56_BUILD_TESTS=ON",
            f"-DMONO56_CMSIS_ROOT={cmsis}",
        ]
    )
    run([cmake, "--build", str(build)])
    # Verify that all expected executables exist, so a configuration which
    # silently omits the CMSIS-dependent tests cannot be reported as complete.
    for test in [
        "bus_voltage_test",
        "adc1_acquisition_test",
        "bus_supervision_test",
        "monitor_service_test",
        "drv8353_test",
        "spi3_transport_test",
        "driver_io_test",
        "driver_monitor_test",
        "phase_current_test",
        "adc23_acquisition_test",
        "current_capture_test",
        "current_monitor_test",
        "timing_monitor_test",
        "pwm_sample_plan_test",
        "pwm_cycle_test",
        "pwm_capture_test",
        "memory_test",
    ]:
        if not (build / test).is_file():
            raise RuntimeError(f"Missing required test executable: {test}")
    registered = json.loads(
        run([str(ctest), "--test-dir", str(build), "--show-only=json-v1"])
    )
    names = {test["name"] for test in registered["tests"]}
    if (
        not {
            "bus_voltage",
            "adc1_acquisition",
            "bus_supervision",
            "monitor_service",
            "drv8353",
            "spi3_transport",
            "driver_io",
            "driver_monitor",
            "phase_current",
            "adc23_acquisition",
            "current_capture",
            "current_monitor",
            "pwm_sample_plan",
            "pwm_cycle",
            "pwm_capture",
            "memory",
            "current_monitor_missing_b",
            "current_monitor_missing_c",
            "current_monitor_adc_irq_loss",
            "current_monitor_noise",
            "current_monitor_csa_drift",
            "current_monitor_exit_loss",
            "current_monitor_supply_drift",
            "current_monitor_collection_timeout",
            "current_monitor_stale_frame",
            "current_monitor_supply_skew",
            "current_monitor_invalid_config",
            "current_monitor_foreground_stall",
            "current_monitor_uncertain_span",
            "current_monitor_post_fault",
            "timing_monitor",
            "timing_monitor_missing_b",
            "timing_monitor_missing_c",
            "timing_monitor_adc_irq_loss",
            "timing_monitor_update_irq_loss",
            "timing_monitor_nfault",
            "timing_monitor_brake",
            "timing_monitor_bus_ov",
            "timing_monitor_csa_drift",
            "timing_monitor_foreground_stall",
            "timing_monitor_timing_supply_skew",
            "timing_monitor_timing_zero_age",
            "timing_monitor_timing_supply_drift",
            "timing_monitor_timing_stale_bus",
            "driver_monitor_bus_ov",
            "driver_monitor_spi_loss",
            "driver_monitor_nfault",
            "driver_monitor_brake",
            "driver_monitor_coast_drift",
            "driver_monitor_foreground_stall",
            "driver_monitor_stale_bus",
            "driver_monitor_bus_timeout",
        }
        <= names
    ):
        raise RuntimeError(f"Required tests are not registered with CTest: {names}")
    test_output = run(
        [str(ctest), "--test-dir", str(build), "-V", "--output-on-failure"]
    )
    for line in test_output.splitlines():
        if "checks passed" in line:
            print(line)
    arm_objects = {}
    compiler_versions = {}
    common_flags = [
        "-mcpu=cortex-m4",
        "-mthumb",
        "-mfpu=fpv4-sp-d16",
        "-mfloat-abi=hard",
        "-fno-builtin",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I" + str(source / "include"),
        *[flag for path in headers for flag in ["-isystem", str(path)]],
    ]

    def check_object(path: Path) -> None:
        elf = path.read_bytes()
        if elf[:6] != b"\x7fELF\x01\x01" or struct.unpack_from("<H", elf, 18)[0] != 40:
            raise RuntimeError(f"Not a 32-bit little-endian ARM object: {path}")
        arm_objects[str(path)] = hashlib.sha256(elf).hexdigest()

    c_sources = [
        "memory.c",
        "adc23_acquisition.c",
        "current_capture.c",
        "adc1_acquisition.c",
        "motor_inhibit.c",
        "spi3_transport.c",
        "driver_io.c",
    ]
    cpp_sources = [
        "bus_voltage.cpp",
        "bus_supervision.cpp",
        "drv8353.cpp",
        "driver_wake.cpp",
        "phase_current.cpp",
        "pwm_sample_plan.cpp",
        "pwm_cycle.cpp",
        "pwm_capture.cpp",
    ]
    if clang:
        compiler_versions["clang"] = run([str(clang), "--version"])
        for name in c_sources:
            obj = build / f"{Path(name).stem}.clang.arm.o"
            run(
                [
                    str(clang),
                    "--target=arm-none-eabi",
                    *common_flags,
                    "-std=c11",
                    "-ffreestanding",
                    "-c",
                    str(source / "src" / name),
                    "-o",
                    str(obj),
                ]
            )
            check_object(obj)
    combined = None
    if gcc:
        prefix = str(gcc).removesuffix("gcc")
        if not str(gcc).endswith("gcc"):
            parser.error("--arm-gcc must name the gcc executable")
        for suffix in ["g++", "ld", "nm", "readelf"]:
            if not Path(prefix + suffix).is_file():
                parser.error(f"Missing companion tool: {prefix + suffix}")
        compiler_versions["gcc"] = run([str(gcc), "--version"])
        compiler_versions["g++"] = run([prefix + "g++", "--version"])
        objects = []
        for name in c_sources + cpp_sources:
            cpp = name.endswith(".cpp")
            # C++ uses newlib/libstdc++ headers like the upstream ODrive build.
            # GCC 15 intentionally disallows <cmath> under -ffreestanding.
            language = (
                ["-std=c++17", "-fno-exceptions", "-fno-rtti"]
                if cpp
                else ["-std=c11", "-ffreestanding"]
            )
            obj = build / f"{Path(name).stem}.gcc.arm.o"
            run(
                [
                    prefix + "g++" if cpp else str(gcc),
                    *common_flags,
                    *language,
                    "-c",
                    str(source / "src" / name),
                    "-o",
                    str(obj),
                ]
            )
            check_object(obj)
            attributes = run([prefix + "readelf", "-A", str(obj)])
            if "VFP registers" not in attributes or "v7E-M" not in attributes:
                raise RuntimeError(f"Missing Cortex-M4/hard-float attributes: {obj}")
            objects.append(str(obj))
        combined = build / "mono56-components.arm.o"
        run([prefix + "ld", "-r", *objects, "-o", str(combined)])
        check_object(combined)
        undefined = run([prefix + "nm", "-u", str(combined)])
        if undefined.strip():
            raise RuntimeError(f"Unresolved component dependencies: {undefined}")
    files = [
        p
        for p in source.rglob("*")
        if p.is_file()
        and (p.suffix in [".c", ".cpp", ".h", ".hpp"] or p.name == "CMakeLists.txt")
    ]
    files.append(Path(__file__).resolve())
    files += [p for directory in headers for p in directory.glob("*.h")]
    evidence = {
        "scope": "Host register-event tests and Cortex-M4 component object compilation only",
        "flashable_firmware": False,
        "commands": commands,
        "compiler_versions": compiler_versions,
        "combined_component_object": str(combined) if combined else None,
        "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "arm_object_sha256": arm_objects,
    }
    (build / "validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"ARM components and validation evidence: {build}")


if __name__ == "__main__":
    main()

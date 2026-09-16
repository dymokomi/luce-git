#!/usr/bin/env python3
"""Instrument generated Base C; does not replace native-mode tests."""
import os
from pathlib import Path
import subprocess
from run import ROOT, SOURCES


def main():
    base = ROOT / "build/toolchain/luce-base"
    runtime = ROOT.parent / "luce-base/runtime"
    output = ROOT / "build/sanitize"
    output.mkdir(parents=True, exist_ok=True)
    os.environ["ASAN_OPTIONS"] = "halt_on_error=1:abort_on_error=1"
    os.environ["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    def run(command):
        subprocess.run([str(a) for a in command], cwd=ROOT, check=True, timeout=180)
    for source, name in SOURCES:
        generated = output / f"{name}.c"
        run([base.resolve(), "build", ROOT / source, "--emit=c", "-o", generated])
        run([os.environ.get("CC", "cc"), "-std=gnu11", "-O1", "-g", "-w", "-fno-strict-aliasing",
             "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", runtime,
             generated, runtime / "lucb_rt.c", "-pthread", "-lm", "-o", output / name])
        run([output / name])
    print("PASS AddressSanitizer + UndefinedBehaviorSanitizer", flush=True)


if __name__ == "__main__":
    main()

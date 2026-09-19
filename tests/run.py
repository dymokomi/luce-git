#!/usr/bin/env python3
"""Build and test native Git object IDs in every pinned mode."""
import argparse
import os
from pathlib import Path
import subprocess
from object_oracle import check
from loose_oracle import check as check_loose
from tree_oracle import check as check_tree
from delta_oracle import check as check_delta
from pack_oracle import check as check_pack

ROOT = Path(__file__).resolve().parents[1]
MODES = {f"native{i}": ["--native", "--opt", str(i)] for i in range(4)}
MODES.update({"c": ["--backend=c"], "c-release": ["--backend=c", "--release"]})
SOURCES = [("src/luce_git/git_tests.lucb", "git-tests"),
           ("src/luce_git/pack_tests.lucb", "pack-tests"),
           ("src/luce_git/delta_tests.lucb", "delta-tests"),
           ("src/luce_git/tree_tests.lucb", "tree-tests"),
           ("src/luce_git/loose_tests.lucb", "loose-tests"),
           ("src/luce_git/object_tests.lucb", "object-tests"),
           ("src/luce_git/packet_tests.lucb", "packet-tests")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=[*MODES, "all"], default="all")
    parser.add_argument("--base", type=Path, default=ROOT / "build/toolchain/luce-base")
    args = parser.parse_args()
    if not args.base.is_file():
        raise SystemExit("Run python3 tools/bootstrap.py first")
    environment = dict(os.environ, LUCE_BASE=str(args.base.resolve()))
    environment.setdefault("LUCE_STD", str(ROOT.parent / "luce-base/src/std"))
    environment.setdefault("LUCE_CACHE", str(ROOT / "build/cache"))
    def run(command):
        subprocess.run([str(a) for a in command], cwd=ROOT, env=environment, check=True, timeout=120)
    for mode, flags in MODES.items():
        if args.mode not in (mode, "all"): continue
        output = ROOT / "build" / mode
        output.mkdir(parents=True, exist_ok=True)
        print(f"MODE {mode}", flush=True)
        for source, name in SOURCES:
            run([args.base.resolve(), "build", ROOT / source, *flags, "-o", output / name])
            run([output / name])
            if name == 'object-tests': check(output / name)
            if name == 'loose-tests': check_loose(output / name)
            if name == 'tree-tests': check_tree(output / name)
            if name == 'delta-tests': check_delta(output / name)
            if name == 'pack-tests': check_pack(output / name)
        print(f"PASS {mode}", flush=True)
    print("PASS all selected compiler modes", flush=True)


if __name__ == "__main__":
    main()

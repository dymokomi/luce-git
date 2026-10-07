#!/usr/bin/env python3
"""Stock Git as the oracle: each check drives one built test program (oracles.py BINARIES)
with fixtures that `git` itself wrote or reads back, so the comparison is independent of
luce-git's own code. Git is only ever a test oracle, never a runtime dependency."""
from pathlib import Path
import sys

from object_oracle import check as check_object
from loose_oracle import check as check_loose
from tree_oracle import check as check_tree
from delta_oracle import check as check_delta
from pack_oracle import check as check_pack
from pack_writer_oracle import check as check_pack_writer
from refs_oracle import check as check_refs
from commit_oracle import check as check_commit
from tag_oracle import check as check_tag
from push_oracle import check as check_push
from fetch_oracle import check as check_fetch

CHECKS = {"object": check_object, "loose": check_loose, "tree": check_tree, "delta": check_delta,
          "pack": check_pack, "pack_writer": check_pack_writer, "refs": check_refs,
          "commit": check_commit, "tag": check_tag, "push": check_push, "fetch": check_fetch}

if __name__ == "__main__":
    binaries = Path(sys.argv[1]).resolve()
    for name, check in CHECKS.items():
        check(binaries / name)
        print(f"PASS git oracle: {name}", flush=True)

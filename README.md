# luce-git

Native Git object identity for Luce Base. MIT OR Apache-2.0.
v1 object IDs are SHA-1 of canonical `{type} {size}\\0{payload}` as in stock Git.
SHA-1 is not used for release signatures or vaults.

Experimental. Packs, refs and Smart HTTP are later slices.

```sh
python3 tools/bootstrap.py
python3 tests/run.py
```

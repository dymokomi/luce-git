# Provenance

Original Luce Base Git object identity, Copyright 2026 Dy Mokomi,
MIT OR Apache-2.0. No libgit2, command-line Git backend or foreign hash engine
is included or linked.

Git object IDs follow the stock SHA-1 loose-object header
`{type} {size}\\0{payload}` used by Git. SHA-1 is isolated to object identity;
release signatures and vaults use SHA-256 and ML-DSA-65 in other packages.

Stock Git is an interoperability client and test oracle only.
Build/test/bootstrap scaffolding follows the MIT OR Apache-2.0 `luce-crypto`
patterns by the same author.

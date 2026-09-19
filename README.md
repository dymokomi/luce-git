# luce-git

Native Git object identity for Luce Base. MIT OR Apache-2.0.
v1 object IDs are SHA-1 of canonical `{type} {size}\\0{payload}` as in stock Git.
SHA-1 is not used for release signatures or vaults.

Experimental. Packs, refs and Smart HTTP are later slices.

`hash_object(kind, payload, output)` supports blob, tree, commit and tag IDs;
`hash_blob` remains a convenience wrapper. `encode_object` and `decode_object`
handle the **uncompressed** loose-object envelope: known kind, canonical decimal
size, NUL, and exact binary payload. Decode borrows unchanged input. Encode requires
non-overlapping input/output and rejects invalid requests before writing. Hashing
currently allocates one header-plus-payload buffer; callers must bound input sizes.
These functions do not validate tree/commit/tag semantics, object references,
SHA-1 collision attacks, compression, or storage durability. They are not a safe
object-ingestion service on their own. Release authenticity still uses ML-DSA-65
and SHA-256, not Git SHA-1.

Based on [Git object storage](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).
Tests compare all four types against stock `git hash-object --literally` and an
independent SHA-1 implementation, plus canonical framing and rejection tests.
Stock Git is only an interoperability oracle, never a runtime dependency.

`encode_loose(kind, payload, max_output)` returns an owning reference to a native
zlib-compressed object; read `result.value().bytes()` and release the reference.
`decode_loose(compressed, expected_id, output)` requires a raw 20-byte Git ID,
validates the entire zlib stream and canonical object envelope, and verifies the
ID before copying into caller storage. Its returned object borrows that storage.
Failures leave the output unchanged; trailing/concatenated streams are rejected.
This buffered API caps compressed input/output and decompressed storage at 64 MiB;
encoding reserves 32 bytes of that limit for the header. Smaller caller buffers
bound decompression, including high-expansion streams. Compression is entirely
native `luce-compress`, pinned in `bootstrap/COMPRESS`. An expected SHA-1 ID is
not publisher authentication, collision protection or permission to extract paths.

`encode_tree_entry` / `decode_tree_entry` handle borrowed binary SHA-1 tree entries.
`validate_tree` checks the complete payload, canonical modes (40000, 100644,
100755, 120000, 160000), non-null IDs, Git's directory-as-slash ordering and
duplicate names, including nonadjacent file/directory duplicates. It rejects
empty/dot/dot-dot/slash/NUL components and case-insensitive `.git`. Limits are
64 MiB, 1,048,576 entries and 4096 bytes per name. Duplicate detection uses an
owned array of borrowed names and heapsort (O(n log n) comparisons).
This structural profile is not full `git fsck`: it does not verify referenced
objects, platform-specific filename aliases, symlink destinations or extraction
safety. Call it explicitly after decoding a tree object; loose decoding does not
implicitly apply semantic policies. Ordering follows
[Git's tree comparator](https://github.com/git/git/blob/master/tree.c), with
tests against `git mktree` and hostile structural fixtures.

`encode_packet` / `decode_packet` provide binary-safe pkt-line framing with a
65520-byte total limit, plus flush, delimiter and response-end controls. The
decoder returns one packet and a consumed count; fields borrow retained input.
It accepts an empty data packet distinctly from flush and leaves payload bytes
(including LF) unchanged. Accumulate fragmented input before calling; incomplete
packets fail without changing input. Encoding uses lowercase hex and requires
non-overlapping input/output; validation failures leave output unchanged.
Control-packet legality depends on the negotiated protocol and is the caller's
responsibility. This is framing, not an implementation of fetch/push negotiation.
Based on [Git's common protocol](https://git-scm.com/docs/protocol-common) and
[protocol v2](https://git-scm.com/docs/gitprotocol-v2).

```sh
python3 tools/bootstrap.py
python3 tests/run.py
```

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

`apply_delta(base, instructions, output)` reconstructs a Git pack delta from an
already resolved base, returning the result length. It validates sizes, copy
ranges, literals and complete output length before writing; errors leave output
unchanged. Each buffer is limited to 64 MiB. Inputs must remain stable and must
not overlap output. It allocates no memory and does not recursively resolve bases.
Pack-level checksums, base lookup, delta-chain depth, aggregate budgets and object
validation still belong to the unfinished pack reader. Based on the
[Git pack delta format](https://git-scm.com/docs/gitformat-pack), with independent
generated packs reconstructed by stock `git index-pack` as the test oracle.

`decode_pack(bytes)` reads complete self-contained SHA-1 packs (versions 2/3),
checks the trailer checksum and exact object count, decodes zlib entries and
reconstructs offset/reference deltas, including forward references. The returned
`Pack` owns its `items`, payloads and IDs: call `close()` and do not copy ownership.
Limits: 64 MiB input, 4096 objects, 64 MiB cumulative inflated-plus-reconstructed
bytes, 64 delta levels and 16,777,216 base-search comparisons. Resolution currently
uses bounded linear searches; indexing is future work. Missing/cyclic bases fail.
`decode_pack_with(bytes, lookup, context)` also accepts thin packs. Its exact-type
callback returns an optional borrowed `Object`; missing objects return `none`,
errors propagate, and the borrow need only survive until the next callback or
decode return. Every external base is SHA-1-verified before use; returned packs
retain neither its payload nor kind storage. Only REF deltas consult lookup,
after internal resolution stalls. Additional limits are 4096 lookups and 64 MiB
cumulative external-base bytes (including repeated successful lookups). Callers
must authorize and bound lookup storage access themselves.
This is not yet an ingestion service:
object semantics, collision rejection, authorization, durable storage, pack writing
and protocol negotiation remain separate requirements. Tests read real stock-Git
packs as well as malformed, forward-reference and offset fixtures.

`encode_pack(objects, output)` writes deterministic version-2 packs containing full
objects with native zlib compression and a SHA-1 trailer. It stages output so a
failure cannot partially modify the caller buffer. Limits are 4096 objects,
64 MiB total input payload and 64 MiB output; scratch storage equals output
capacity, plus the current compressed object. Input order is preserved. Delta
selection is not implemented. This encoder does not validate object semantics or
authorize publication. Tests require stock Git `index-pack --strict`, `cat-file`
and `fsck --strict` to accept a native-written fixture repository.

`valid_ref(name)` checks ordinary multi-component ref syntax without allocation,
normalization, wildcard expansion or branch-shorthand handling. It follows
[Git's ref-format rules](https://git-scm.com/docs/git-check-ref-format), with an
additional 4096-byte limit. `HEAD` and other one-level symbolic names are outside
this API. A valid name is not authorization or a safe filesystem path: repository
namespace restrictions, conflicting prefixes, aliases and atomic ref updates are
still required. Differential tests cover fixed cases, ASCII bytes, Unicode and
deterministic generated names against `git check-ref-format`.

`decode_commit(payload)` parses bounded SHA-1 commit structure without allocation:
one tree ID, contiguous parent IDs, author and committer headers, optional extension
headers with space-prefixed continuations, a required empty separator line, and
an unchanged binary message. Its fields borrow the retained, unmodified input;
`parent(index)` retrieves a validated parent's hexadecimal ID in constant time.
`decode_id(text, output)` converts either hex case to exactly 20 bytes and leaves
output unchanged on validation failure. Commit tree/parent IDs cannot be all zero.

Limits are 64 MiB per payload, 1 MiB of headers, 65536 bytes per header line and
4096 parents. NUL/CR header bytes, repeated/misplaced structural headers, orphan
continuations and missing separators are rejected. Message bytes remain opaque,
including NUL/non-UTF-8 bytes. Author/committer fields are nonempty raw values:
this is **not** identity/date validation, full `git fsck`, object graph closure,
signature verification, publisher authorization or release authenticity. Extra
headers are structurally parsed, not semantically validated. A parsed commit must
not be admitted to a public repository solely on this result.

The original implementation follows the documented
[Git object structure](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects) and
[header folding](https://git-scm.com/docs/gitformat-signature). Tests compare native
tree/parent extraction with actual `commit-tree`, `rev-list` and `rev-parse` output,
then exercise folded headers, binary messages, every pre-message truncation and
the complete parent-count boundary. Stock Git is used only in these test oracles.

`decode_tag(payload)` parses annotated tag structure: a nonzero hexadecimal
object ID, declared target kind (blob/tree/commit/tag), nonempty tag label,
optional nonempty tagger, required empty separator and unchanged binary message.
Returned fields borrow retained, unmodified input. Historical tags without a
tagger are accepted; additional/folded tag headers are not supported. Limits are
64 MiB payload, 1 MiB header region and 65536 bytes per header line; NUL/CR header
bytes and malformed ordering are rejected. The tag label and raw tagger are not
validated as a ref name or identity/date. Embedded signature text stays in the
message and is not verified. Target existence, actual type, graph closure and
signature/publisher trust must be checked separately before publication.
Tests extract stock-Git annotated tags targeting each of the four object kinds,
including nested tags, and cover every header truncation, missing/repeated
headers, binary/signature messages and bounds. No Git executable is used at runtime.

`encode_packet` / `decode_packet` provide binary-safe pkt-line framing with a
65520-byte total limit, plus flush, delimiter and response-end controls. The
decoder returns one packet and a consumed count; fields borrow retained input.
It accepts an empty data packet distinctly from flush and leaves payload bytes
(including LF) unchanged. Accumulate fragmented input before calling; incomplete
packets fail without changing input. Encoding uses lowercase hex and requires
non-overlapping input/output; validation failures leave output unchanged.
Control-packet legality depends on the negotiated protocol and is the caller's
responsibility. This is framing, not an implementation of fetch/push negotiation.

`decode_fetch` parses one stateless SHA-1 upload-pack negotiation round into a
borrowed `FetchRequest`: `want(index)`, `have(index)`, counts, first-want
capabilities, and `done`. Limits are 1 MiB input, 1024 wants, 4096 haves and
4096 capability bytes. Optional packet LF and repeated IDs are accepted;
case-insensitive nonzero IDs are validated. Wants end with flush; haves end with
flush or done. A want-only round and bare no-work flush are supported. Trailing
bytes, misplaced capabilities, unsupported control packets and shallow/deepen/
filter commands fail. This is framing, not capability negotiation, advertised-ID
authorization, ACK selection or pack generation. The server must enforce those
separately. Tests include a real stock-Git upload-pack response, strict index-pack
verification, malformed packets and exact limits. See the
[Git pack protocol](https://git-scm.com/docs/gitprotocol-pack).

`decode_push` parses the SHA-1 receive-pack command section into a borrowed
`PushRequest` with up to 64 commands (`at(index)`), first-packet capabilities,
and the remaining pack bytes. It requires a flush, valid IDs/ref names, unique
refs and at least one non-null ID per command. Limits are 1 MiB of command data,
4096 capability bytes and 64 MiB of pack data. Optional trailing LF is removed
from command packets. Capability lists accept boundary spaces used by stock Git's
HTTP send-pack; the returned view trims them while preserving strict interior
tokens. Delete-only requests cannot carry a pack; create/update
requests must carry at least a 32-byte PACK-prefixed payload, including empty packs.
The caller must still fully decode/verify that pack: this parser does not check
its checksum or graph. Shallow updates, push certificates, push-options sections
and delimiter/response-end packets are rejected. Other capability tokens are
returned, **not negotiated or authorized**. No storage, ref update, ancestry,
authentication or HTTP endpoint is performed here.
Tests cover truncations, duplicate refs, command/capability bounds, unsupported
forms and requests actually applied by stock Git receive-pack for create/update/
delete. The wire contract follows [Git's pack protocol](https://git-scm.com/docs/gitprotocol-pack).

Based on [Git's common protocol](https://git-scm.com/docs/protocol-common) and
[protocol v2](https://git-scm.com/docs/gitprotocol-v2).

```sh
python3 tools/bootstrap.py
python3 tests/run.py
```

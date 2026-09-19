# luce-git

Native Git object identity for Luce Base. MIT OR Apache-2.0.
v1 object IDs are SHA-1 of canonical `{type} {size}\\0{payload}` as in stock Git.
SHA-1 is not used for release signatures or vaults.

Experimental. Packs, refs and Smart HTTP are later slices.

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

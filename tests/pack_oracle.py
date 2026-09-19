"""Native pack reader versus stock Git, with hostile complete pack fixtures."""
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib
from delta_oracle import varint, pack_header, copy_instruction, identity

def finish(entries, count, version=2):
    wire = b'PACK' + struct.pack('>II', version, count) + entries
    return wire + hashlib.sha1(wire).digest()

def ofs(distance):
    data = bytearray([distance & 127])
    while distance >> 7:
        distance = (distance >> 7) - 1
        data.insert(0, 128 | (distance & 127))
    return bytes(data)

def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-pack-') as temporary:
        root = Path(temporary)
        path = root / 'input.pack'
        bases_path = root / 'bases.pack'
        def run(wire, expected=None, bases=None, wrong=False):
            path.write_bytes(wire)
            arguments = [str(binary), str(path)]
            if bases is not None:
                bases_path.write_bytes(bases)
                arguments.append(str(bases_path))
            if wrong: arguments.append('wrong')
            result = subprocess.run(arguments, capture_output=True, timeout=30)
            assert result.returncode >= 0 and b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr
            if expected is None:
                assert result.returncode != 0, 'invalid pack accepted'
            else:
                assert result.returncode == 0, result.stderr
                assert sorted(result.stdout.decode().splitlines()) == sorted(expected), result.stdout
        def line(payload):
            return f'blob {identity(payload).hex()} {len(payload)}'
        base = b'base source\n' * 100
        target = base + b'new'
        delta = varint(len(base)) + varint(len(target)) + copy_instruction(0, len(base)) + b'\x03new'
        full = pack_header(3, len(base)) + zlib.compress(base)
        ref = pack_header(7, len(delta)) + identity(base) + zlib.compress(delta)
        offset = pack_header(6, len(delta)) + ofs(len(full)) + zlib.compress(delta)
        expected = [line(base), line(target)]
        run(finish(full + ref, 2), expected)
        run(finish(ref + full, 2), expected)  # forward ref base
        run(finish(full + offset, 2, 3), expected)
        run(finish(b'', 0), [])
        mixed, mixed_expected = b'', []
        for form, kind in enumerate(('commit', 'tree', 'blob', 'tag'), 1):
            payload = b'' if kind == 'tree' else kind.encode() + b' fixture\n'
            mixed += pack_header(form, len(payload)) + zlib.compress(payload)
            oid = hashlib.sha1(kind.encode() + b' ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
            mixed_expected.append(f'{kind} {oid} {len(payload)}')
        run(finish(mixed, 4), mixed_expected)
        run(finish(ref, 1))  # thin/missing base
        run(finish(ref, 1), [line(target)], bases=finish(full, 1))
        run(finish(ref, 1), bases=finish(b'', 0))
        wrong_base = pack_header(3, 5) + zlib.compress(b'wrong')
        run(finish(ref, 1), bases=finish(wrong_base, 1), wrong=True)
        # Forward internal dependency must become resolvable after an external
        # base lookup, even when the first callback returns missing.
        later = target + b'!'
        later_delta = varint(len(target)) + varint(len(later)) + copy_instruction(0, len(target)) + b'\x01!'
        later_ref = pack_header(7, len(later_delta)) + identity(target) + zlib.compress(later_delta)
        run(finish(later_ref + ref, 2), [line(target), line(later)], bases=finish(full, 1))
        run(finish(full + pack_header(6, len(delta)) + b'\0' + zlib.compress(delta), 2))
        run(finish(full + pack_header(6, len(delta)) + ofs(len(full) - 1) + zlib.compress(delta), 2))
        for version in (0, 1, 4): run(finish(b'', 0, version))
        run(finish(b'', 4097))
        run(finish(full, 0))
        run(finish(full, 2))
        run(finish(full + b'extra', 1))
        run(finish(pack_header(0, 0) + zlib.compress(b''), 1))
        run(finish(pack_header(5, 0) + zlib.compress(b''), 1))
        run(finish(pack_header(3, len(base) - 1) + zlib.compress(base), 1))
        run(finish(pack_header(3, len(base) + 1) + zlib.compress(base), 1))
        run(finish(pack_header(3, 67108865), 1))
        run(finish(pack_header(3, 0) + b'bad-zlib', 1))
        valid = finish(full, 1)
        for cut in range(len(valid)): run(valid[:cut])
        run(valid[:-1] + bytes([valid[-1] ^ 1]))
        # Chain depth is measured after resolution, including forward refs.
        payload = b'x'
        chain = pack_header(3, 1) + zlib.compress(payload)
        chain_expected = [line(payload)]
        for depth in range(1, 66):
            next_payload = payload + b'x'
            change = varint(len(payload)) + varint(len(next_payload)) + copy_instruction(0, len(payload)) + b'\x01x'
            chain += pack_header(7, len(change)) + identity(payload) + zlib.compress(change)
            payload = next_payload
            chain_expected.append(line(payload))
            if depth == 64: run(finish(chain, 65), chain_expected)
        run(finish(chain, 66))
        # Stock Git generates full objects and real delta chains in both forms.
        repo = root / 'repo.git'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repo)], check=True)
        ids, expected = [], []
        for i in range(24):
            payload = b'common package source\n' * 200 + f'change {i}\n'.encode()
            oid = subprocess.check_output(['git', '--git-dir', str(repo), 'hash-object', '-w', '--stdin'], input=payload).strip()
            ids.append(oid)
            expected.append(line(payload))
        for flags in ([], ['--delta-base-offset']):
            wire = subprocess.check_output(['git', '--git-dir', str(repo), 'pack-objects', '--stdout', '--window=24', '--depth=20', *flags], input=b'\n'.join(ids) + b'\n')
            run(wire, expected)
    print('PASS native packs: forward REF/OFS deltas, stock Git packs, checksum/framing/limits and rejection', flush=True)

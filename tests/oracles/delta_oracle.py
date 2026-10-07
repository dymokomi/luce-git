"""Stock Git index-pack reconstructs the same independently generated deltas."""
import hashlib
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import zlib

def varint(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)

def pack_header(kind, size):
    first = (kind << 4) | (size & 15)
    size >>= 4
    return bytes([first | (128 if size else 0)]) + (varint(size) if size else b'')

def identity(payload):
    return hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).digest()

def copy_instruction(offset, size):
    flags = 128
    fields = bytearray()
    for bit, value in enumerate(offset.to_bytes(4, 'little') + size.to_bytes(3, 'little')):
        if value:
            flags |= 1 << bit
            fields.append(value)
    return bytes([flags]) + fields

def check(binary):
    rng = random.Random(92831)
    with tempfile.TemporaryDirectory(prefix='git-delta-') as temporary:
        root = Path(temporary)
        repo = root / 'oracle.git'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repo)], check=True)
        base_file, delta_file, result_file = (root / name for name in ('base', 'delta', 'result'))
        base = bytes(rng.randrange(256) for _ in range(180000))
        base_file.write_bytes(base)
        cases = [(b'\x80', base[:65536]), (copy_instruction(65537, 66000), base[65537:131537])]
        for _ in range(24):
            instructions, result = bytearray(), bytearray()
            for _ in range(12):
                if rng.randrange(2):
                    offset = rng.randrange(len(base))
                    size = rng.randrange(1, min(8192, len(base) - offset) + 1)
                    instructions += copy_instruction(offset, size)
                    result += base[offset:offset + size]
                else:
                    literal = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 128)))
                    instructions += bytes([len(literal)]) + literal
                    result += literal
            cases.append((bytes(instructions), bytes(result)))
        for instructions, expected in cases:
            delta = varint(len(base)) + varint(len(expected)) + instructions
            delta_file.write_bytes(delta)
            subprocess.run([str(binary), str(base_file), str(delta_file), str(result_file)], check=True, timeout=30)
            assert result_file.read_bytes() == expected
            # Full pack: one base blob followed by a ref-delta against that blob.
            pack = (b'PACK' + struct.pack('>II', 2, 2) + pack_header(3, len(base)) + zlib.compress(base)
                    + pack_header(7, len(delta)) + identity(base) + zlib.compress(delta))
            pack += hashlib.sha1(pack).digest()
            subprocess.run(['git', '--git-dir', str(repo), 'index-pack', '--stdin'], input=pack,
                           capture_output=True, check=True, timeout=30)
            stock = subprocess.check_output(['git', '--git-dir', str(repo), 'cat-file', 'blob', identity(expected).hex()], timeout=30)
            assert stock == expected
    print('PASS 26 delta reconstructions against stock Git index-pack, including implicit 64KiB copy', flush=True)

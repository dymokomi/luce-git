"""Independent zlib interoperability in both directions (test-only Python codec)."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import zlib

def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-loose-') as temporary:
        root = Path(temporary)
        repository = root / 'oracle.git'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repository)], check=True, timeout=30)
        source, encoded, key, result = (root / name for name in ('source', 'encoded', 'key', 'result'))
        for kind in ('blob', 'tree', 'commit', 'tag'):
            for payload in (b'', bytes(range(256)), b'repeated source\n' * 4096):
                wire = kind.encode() + b' ' + str(len(payload)).encode() + b'\0' + payload
                key.write_bytes(hashlib.sha1(wire).digest())
                source.write_bytes(payload)
                subprocess.run([str(binary), 'encode', kind, str(source), str(encoded)], check=True, timeout=30)
                decoder = zlib.decompressobj()
                assert decoder.decompress(encoded.read_bytes()) == wire
                assert decoder.eof and not decoder.unused_data
                oid = key.read_bytes().hex()
                stored = repository / 'objects' / oid[:2] / oid[2:]
                stored.parent.mkdir(exist_ok=True)
                stored.write_bytes(encoded.read_bytes())
                assert subprocess.check_output(['git', '--git-dir', str(repository), 'cat-file', kind, oid], timeout=30) == payload
                for level in (0, 1, 9):
                    encoded.write_bytes(zlib.compress(wire, level))
                    subprocess.run([str(binary), 'decode', str(key), str(encoded), str(result)], check=True, timeout=30)
                    assert result.read_bytes() == payload
        # Explicit decompression bomb hits the fixture's 1 MiB output bound.
        payload = b'x' * 1100000
        wire = b'blob 1100000\0' + payload
        key.write_bytes(hashlib.sha1(wire).digest())
        encoded.write_bytes(zlib.compress(wire))
        before = result.read_bytes()
        refused = subprocess.run([str(binary), 'decode', str(key), str(encoded), str(result)], capture_output=True, timeout=30)
        assert refused.returncode > 0 and b'Sanitizer' not in refused.stderr and b'runtime error:' not in refused.stderr, refused.stderr
        assert result.read_bytes() == before
    print('PASS independent zlib loose objects both directions and bounded expansion', flush=True)

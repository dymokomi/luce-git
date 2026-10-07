"""Stock Git is a test oracle only; production hashing remains native Base."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-object-oracle-') as temporary:
        path = Path(temporary) / 'payload'
        for kind in ('blob', 'tree', 'commit', 'tag'):
            for size in (0, 1, 9, 10, 55, 56, 63, 64, 65, 99, 100, 255, 256, 4096):
                payload = bytes((i * 37) % 256 for i in range(size))
                path.write_bytes(payload)
                expected = hashlib.sha1(kind.encode() + b' ' + str(size).encode() + b'\0' + payload).hexdigest()
                # --literally skips semantic validation; this gate tests envelopes/IDs.
                stock = subprocess.check_output(['git', 'hash-object', '--literally', '-t', kind, '--stdin'],
                                                input=payload, timeout=30).decode().strip()
                actual = subprocess.check_output([str(binary), kind, str(path)], timeout=30).decode().strip()
                assert actual == stock == expected, (kind, size, actual, stock, expected)
    print('PASS 56 binary object IDs against stock Git and hashlib', flush=True)

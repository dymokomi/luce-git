"""Native output is accepted by stock Git's strict pack and repository checks."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-pack-writer-') as temporary:
        root = Path(temporary)
        pack = root / 'native.pack'
        subprocess.run([str(binary), str(pack)], check=True, timeout=30)
        repo = root / 'repo.git'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repo)], check=True)
        subprocess.run(['git', '--git-dir', str(repo), 'index-pack', '--strict', '--stdin'],
                       input=pack.read_bytes(), capture_output=True, check=True, timeout=30)
        objects = [('blob', b'hello\0pack\n'), ('tree', b''),
                   ('commit', b'tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904\nauthor Test <test@example.invalid> 1 +0000\ncommitter Test <test@example.invalid> 1 +0000\n\nfixture\n'),
                   ('blob', b'')]
        for kind, payload in objects:
            oid = hashlib.sha1(kind.encode() + b' ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
            actual = subprocess.check_output(['git', '--git-dir', str(repo), 'cat-file', kind, oid], timeout=30)
            assert actual == payload
            if kind == 'commit':
                subprocess.run(['git', '--git-dir', str(repo), 'update-ref', 'refs/heads/test', oid], check=True)
        subprocess.run(['git', '--git-dir', str(repo), 'fsck', '--strict', '--no-reflogs'], capture_output=True, check=True, timeout=30)
    print('PASS native pack accepted by stock Git index-pack --strict, cat-file and fsck --strict', flush=True)

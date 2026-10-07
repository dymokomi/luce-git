"""Git mktree sorting oracle and hostile structural inputs."""
from pathlib import Path
import subprocess
import tempfile

def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-tree-') as temporary:
        root = Path(temporary)
        repo = root / 'oracle.git'
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repo)], check=True)
        path = root / 'tree'
        oid = b'1' * 40
        raw_id = bytes.fromhex(oid.decode())
        def entry(mode, name, identity=raw_id):
            return mode + b' ' + name + b'\0' + identity
        def validate(wire, success):
            path.write_bytes(wire)
            result = subprocess.run([str(binary), str(path)], capture_output=True, timeout=30)
            assert result.returncode >= 0 and b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr
            assert (result.returncode == 0) == success, (wire[:100], result.stdout, result.stderr)
        items = [(b'100644', b'blob', b'foo.bar'), (b'040000', b'tree', b'foo'),
                 (b'040000', b'tree', b'foo.dir'), (b'100755', b'blob', b'executable'),
                 (b'120000', b'blob', b'link'), (b'160000', b'commit', b'submodule'),
                 (b'100644', b'blob', b'white space\n\xff')]
        text = b''.join(mode + b' ' + kind + b' ' + oid + b'\t' + name + b'\0' for mode, kind, name in items)
        tree = subprocess.check_output(['git', '--git-dir', str(repo), 'mktree', '--missing', '-z'], input=text).strip()
        wire = subprocess.check_output(['git', '--git-dir', str(repo), 'cat-file', 'tree', tree])
        validate(wire, True)
        validate(b'', True)
        for mode in (b'40000', b'100644', b'100755', b'120000', b'160000'):
            validate(entry(mode, b'a'), True)
        for mode in (b'040000', b'0100644', b'100664', b'777777', b'', b'-1'):
            validate(entry(mode, b'a'), False)
        for name in (b'', b'.', b'..', b'.git', b'.GIT', b'a/b', b'x' * 4097):
            validate(entry(b'100644', name), False)
        validate(entry(b'100644', b'a', b'\0' * 20), False)
        validate(entry(b'100644', b'b') + entry(b'100644', b'a'), False)
        validate(entry(b'100644', b'a') * 2, False)
        # Git tree sorting can separate a duplicate file and directory name.
        validate(entry(b'100644', b'foo') + entry(b'100644', b'foo.bar') + entry(b'40000', b'foo'), False)
        # Directory prefixes do NOT preserve ordinary name ordering.
        validate(entry(b'40000', b'foo.bar') + entry(b'40000', b'foo'), True)
        validate(entry(b'100644', b'foo') + entry(b'40000', b'foo.bar') + entry(b'40000', b'foo'), False)
        for n in range(1, len(entry(b'100644', b'a'))): validate(entry(b'100644', b'a')[:n], False)
        many = b''.join(entry(b'100644', f'file{i:05}'.encode()) for i in range(10000))
        validate(many, True)
    print('PASS stock Git tree ordering, 10k entries, modes, names, IDs and nonadjacent duplicates', flush=True)

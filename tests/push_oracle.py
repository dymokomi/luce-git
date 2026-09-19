"""Compare parsed receive-pack commands with actual stock Git ref transactions."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


def check(binary):
    binary = str(Path(binary).resolve())
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
               GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test')
    with tempfile.TemporaryDirectory(prefix='git-push-oracle-') as temporary:
        root = Path(temporary)
        repo = root / 'repo.git'
        request = root / 'request'
        subprocess.run(['git', 'init', '--bare', '--object-format=sha1', '-q', str(repo)], env=env, check=True)

        def git(*args, payload=None):
            return subprocess.check_output(['git', '--git-dir', str(repo), *args], input=payload,
                                           env=env, stderr=subprocess.PIPE, timeout=30)

        tree = git('hash-object', '-t', 'tree', '-w', '--stdin', payload=b'').strip()
        first = git('commit-tree', tree.decode(), payload=b'first\n').strip()
        second = git('commit-tree', tree.decode(), '-p', first.decode(), payload=b'second\n').strip()
        zero = b'0' * 40
        head = b'PACK\0\0\0\2\0\0\0\0'
        empty_pack = head + hashlib.sha1(head).digest()
        name = b'refs/heads/fixture'
        for old, new in [(zero, first), (first, second), (second, zero)]:
            command = old + b' ' + new + b' ' + name
            data = command + b'\0report-status'
            pack = b'' if new == zero else empty_pack
            wire = f'{len(data) + 4:04x}'.encode() + data + b'0000' + pack
            request.write_bytes(wire)
            parsed = subprocess.check_output([binary, str(request)], timeout=30).splitlines()
            assert parsed == [b'1', command, b'report-status', str(len(pack)).encode()], parsed
            status = git('receive-pack', '--stateless-rpc', str(repo), payload=wire)
            assert b'unpack ok' in status and b'ok ' + name in status, status
            actual = git('for-each-ref', '--format=%(objectname)', name.decode()).strip()
            assert actual == (b'' if new == zero else new), actual
    print('PASS native push parsing agrees with stock Git create/update/delete transactions', flush=True)

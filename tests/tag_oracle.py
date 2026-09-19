"""Annotated tag extraction against stock Git; no runtime Git dependency."""
import os
from pathlib import Path
import subprocess
import tempfile


def check(binary):
    binary = str(Path(binary).resolve())
    with tempfile.TemporaryDirectory(prefix='git-tag-oracle-') as temporary:
        root = Path(temporary)
        repo = root / 'repo.git'
        path = root / 'payload'
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                   GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test',
                   GIT_AUTHOR_DATE='1700000000 +0545', GIT_COMMITTER_DATE='1700000000 +0545')

        def git(*args, payload=None):
            return subprocess.check_output(['git', '-c', 'tag.gpgsign=false', '--git-dir', str(repo), *args],
                                           input=payload, env=env, stderr=subprocess.PIPE, timeout=30)

        subprocess.run(['git', 'init', '--bare', '--object-format=sha1', '-q', str(repo)], env=env, check=True)
        blob = git('hash-object', '-t', 'blob', '-w', '--stdin', payload=b'fixture').strip()
        tree = git('hash-object', '-t', 'tree', '-w', '--stdin', payload=b'').strip()
        commit = git('commit-tree', tree.decode(), payload=b'fixture\n').strip()
        tagger = b'Fixture <fixture@example.test> 1700000000 +0545'

        def accepts(payload, target, kind, name, identity, message):
            path.write_bytes(payload)
            actual = subprocess.check_output([binary, str(path)], timeout=30).splitlines()
            assert actual == [target, kind, name, identity, str(len(message)).encode()], actual

        targets = [(blob, b'blob'), (tree, b'tree'), (commit, b'commit')]
        for index in range(4):
            target, kind = targets[index]
            name = f'v{index}'.encode()
            message = f'tag fixture {index}\n'.encode()
            git('tag', '-a', name.decode(), target.decode(), '-F', '-', payload=message)
            oid = git('rev-parse', 'refs/tags/' + name.decode()).strip()
            payload = git('cat-file', 'tag', oid.decode())
            accepts(payload, target, kind, name, tagger, message)
            assert git('cat-file', '-t', target.decode()).strip() == kind
            if index == 0: targets.append((oid, b'tag'))
        git('fsck', '--strict', '--no-reflogs')
        stem = b'object ' + commit + b'\ntype commit\ntag v1\n'
        standard = stem + b'tagger ' + tagger + b'\n'
        accepts(stem + b'\n', commit, b'commit', b'v1', b'', b'')
        # Signature bytes belong to the message; no signature verification claim.
        for message in [b'', b'\x00\xffbinary', b'message\n-----BEGIN PGP SIGNATURE-----\nfixture\n-----END PGP SIGNATURE-----\n']:
            accepts(standard + b'\n' + message, commit, b'commit', b'v1', tagger, message)
        accepts(standard.replace(commit, commit.upper()) + b'\n', commit.upper(), b'commit', b'v1', tagger, b'')

        def rejects(payload):
            path.write_bytes(payload)
            result = subprocess.run([binary, str(path)], capture_output=True, timeout=30)
            assert result.returncode > 0, (payload[:100], result.returncode, result.stderr)
            assert b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr

        for end in range(len(standard) + 1): rejects((standard + b'\n')[:end])
        for payload in [standard.replace(commit, b'0' * 40), standard.replace(commit, b'g' * 40),
                        standard.replace(commit, commit[:-1]), standard.replace(b'type commit', b'type unknown'),
                        standard.replace(b'tag v1', b'tag '), standard.replace(b'type commit\n', b''),
                        standard.replace(b'tag v1\n', b''), standard.replace(b'object ', b'object  '),
                        standard.replace(b'\n', b'\r\n'), standard.replace(b'v1', b'v\x001'),
                        stem + b'tagger \n', standard + b'tagger ' + tagger + b'\n',
                        standard + b'tag duplicate\n', standard + b'type tag\n',
                        standard + b'x-extra value\n', standard + b' continuation\n',
                        standard.replace(b'tag v1', b'tag ' + b'a' * 65537)]:
            rejects(payload + b'\nmessage')
    print('PASS stock Git annotated tags targeting all four kinds, binary/signature messages, bounds and truncations', flush=True)

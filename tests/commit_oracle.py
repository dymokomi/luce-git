"""Commit structure interoperability; stock Git is a test oracle, never runtime."""
import os
from pathlib import Path
import subprocess
import tempfile


def check(binary):
    binary = str(Path(binary).resolve())
    with tempfile.TemporaryDirectory(prefix='git-commit-oracle-') as temporary:
        root = Path(temporary)
        repo = root / 'repo.git'
        payload_file = root / 'payload'
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='Fixture Author', GIT_AUTHOR_EMAIL='author@example.test',
                   GIT_COMMITTER_NAME='Fixture Committer', GIT_COMMITTER_EMAIL='committer@example.test',
                   GIT_AUTHOR_DATE='1700000000 +0545', GIT_COMMITTER_DATE='1700000010 -0330')

        def git(*args, payload=None):
            return subprocess.check_output(['git', '-c', 'commit.gpgsign=false', '--git-dir', str(repo), *args],
                                           input=payload, env=env, stderr=subprocess.PIPE, timeout=30)

        subprocess.run(['git', 'init', '--bare', '--object-format=sha1', '-q', str(repo)],
                       env=env, check=True, timeout=30)
        tree = git('hash-object', '-w', '-t', 'tree', '--stdin', payload=b'').strip()
        author = b'Fixture Author <author@example.test> 1700000000 +0545'
        committer = b'Fixture Committer <committer@example.test> 1700000010 -0330'
        stem = b'tree ' + tree + b'\nauthor ' + author + b'\ncommitter ' + committer + b'\n'

        def accepts(payload, parents, message, expected_tree=tree):
            payload_file.write_bytes(payload)
            actual = subprocess.check_output([binary, str(payload_file)], timeout=30).splitlines()
            expected = [expected_tree, str(len(parents)).encode(), *parents, author, committer, str(len(message)).encode()]
            assert actual == expected, (actual, expected)

        commits = []
        for i, parents in enumerate([[], [], [], [0], [0, 1], [0, 1, 2]]):
            message = f'fixture {i}\n\nbody\n'.encode()
            argv = ['commit-tree', tree.decode()]
            for parent in parents: argv += ['-p', commits[parent].decode()]
            oid = git(*argv, payload=message).strip()
            payload = git('cat-file', 'commit', oid.decode())
            expected_parents = [commits[parent] for parent in parents]
            accepts(payload, expected_parents, message)
            assert git('rev-list', '--parents', '-1', oid.decode()).split()[1:] == expected_parents
            assert git('rev-parse', oid.decode() + '^{tree}').strip() == tree
            commits.append(oid)
        git('update-ref', 'refs/heads/main', commits[-1].decode())
        git('fsck', '--strict', '--no-reflogs')
        # Synthetic extension fixtures retain standard header folding, including
        # blank continuation lines. These signatures are NOT cryptographically valid.
        for extra in [b'', b'encoding UTF-8\n', b'x-fixture value\n',
                      b'gpgsig -----BEGIN SSH SIGNATURE-----\n abc\n \n -----END SSH SIGNATURE-----\n',
                      b'mergetag object\n type commit\n tag nested\n \n message\n']:
            message = b'body\x00\xff\n'
            accepts(stem + extra + b'\n' + message, [], message)
        accepts(stem + b'\n', [], b'')
        accepts(stem.replace(tree, tree.upper()) + b'\ntext', [], b'text', tree.upper())
        parent_line = b'parent ' + commits[0] + b'\n'
        payload = b'tree ' + tree + b'\n' + parent_line * 4096 + b'author ' + author + b'\ncommitter ' + committer + b'\n\n'
        accepts(payload, [commits[0]] * 4096, b'')

        def rejects(payload):
            payload_file.write_bytes(payload)
            result = subprocess.run([binary, str(payload_file)], capture_output=True, timeout=30)
            assert result.returncode > 0, (result.returncode, result.stdout, result.stderr)
            assert b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr

        # Every cut before the required empty line must fail, but arbitrary
        # message truncation is legal and intentionally NOT called malformed.
        for end in range(len(stem) + 1): rejects((stem + b'\n')[0:end])
        rejects(payload.replace(parent_line * 4096, parent_line * 4097))
        for mutation in [stem.replace(b'tree ', b'tree  '), stem.replace(tree, b'0' * 40),
                         stem.replace(tree, b'g' * 40), stem.replace(tree, tree[:-1]),
                         stem.replace(b'author ', b'author\x00'), stem.replace(b'\n', b'\r\n'),
                         stem.replace(b'author ' + author + b'\n', b''),
                         stem.replace(b'committer ' + committer + b'\n', b''),
                         stem + b'tree ' + tree + b'\n', stem + parent_line,
                         stem + b'author ' + author + b'\n', stem + b'committer ' + committer + b'\n',
                         stem + b' orphan\n', stem + b'bad-header-without-space\n',
                         stem + b'bad\tkey value\n', stem + b'x ' + b'a' * 65537 + b'\n',
                         stem + (b'x ' + b'a' * 65500 + b'\n') * 17]:
            rejects(mutation + b'\nmessage')
    print('PASS commit-tree/rev-list/tree interoperability, folded headers, binary messages, limits and truncations', flush=True)

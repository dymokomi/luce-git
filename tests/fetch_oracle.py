"""Independent upload-pack negotiation framing, limits, and stock Git oracle."""
from pathlib import Path
import os
import subprocess
import tempfile


def packet(payload):
    return f'{len(payload) + 4:04x}'.encode() + payload


def check(binary):
    with tempfile.TemporaryDirectory(prefix='git-fetch-') as temporary:
        root = Path(temporary)
        path = root / 'request'
        oid = b'1' * 40
        other = b'A' * 40
        want = packet(b'want ' + oid + b'\n')
        have = packet(b'have ' + other)
        done = packet(b'done\n')

        def run(wire, wants=None, haves=(), caps='', completed=False):
            path.write_bytes(wire)
            result = subprocess.run([str(binary), str(path)], capture_output=True, timeout=30)
            assert result.returncode >= 0 and b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr
            if wants is None:
                assert result.returncode != 0, wire[:100]
            else:
                assert result.returncode == 0, result.stderr
                expected = [f'{len(wants)} {len(haves)}', 'done' if completed else 'round', caps]
                expected += [value.decode() for value in (*wants, *haves)]
                assert result.stdout.decode().splitlines() == expected

        run(b'0000', [])
        run(want + b'0000', [oid])
        run(want + b'0000' + done, [oid], completed=True)
        run(want + b'0000' + have + b'0000', [oid], [other])
        run(want + b'0000' + have + done, [oid], [other], completed=True)
        caps = 'multi_ack_detailed side-band-64k ofs-delta'
        run(packet(b'want ' + oid + b' ' + caps.encode()) + want + b'0000' + done,
            [oid, oid], caps=caps, completed=True)
        run(want * 1024 + b'0000', [oid] * 1024)
        run(want * 1025 + b'0000')
        run(want + b'0000' + have * 4096 + done, [oid], [other] * 4096, completed=True)
        run(want + b'0000' + have * 4097 + done)
        run(packet(b'want ' + oid + b' ' + b'a' * 4096) + b'0000', [oid], caps='a' * 4096)
        run(packet(b'want ' + oid + b' ' + b'a' * 4097) + b'0000')
        for line in (b'want ' + b'0' * 40, b'want ' + b'z' * 40,
                     b'want ' + oid + b' ', b'want ' + oid + b' a  b',
                     b'want ' + oid + b' a\0b', b'want ' + oid + b' a\tb',
                     b'shallow ' + oid, b'deepen 1', b'filter blob:none', b'done'):
            run(packet(line) + b'0000')
        run(want + packet(b'want ' + oid + b' ofs-delta') + b'0000')
        for tail in (have, b'0001', b'0002', done + b'0000', b'0000' + done,
                     packet(b'have ' + b'0' * 40) + done, want + done):
            run(want + b'0000' + tail)
        run(b'0000' + done)
        run(b'x' * 1048577)
        wire = want + b'0000' + done
        for cut in range(len(wire)):
            if cut == len(want) + 4: continue  # complete want-only round
            run(wire[:cut])

        # The same native-accepted request produces a valid full pack in stock Git.
        repo = root / 'repo.git'
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                   GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test')
        def git(*args, input=None):
            return subprocess.check_output(['git', '--git-dir', str(repo), *args], input=input, env=env)
        subprocess.run(['git', 'init', '--bare', '--quiet', str(repo)], check=True, env=env)
        tree = git('mktree', input=b'').strip()
        commit = git('commit-tree', tree.decode(), input=b'fetch fixture\n').strip()
        git('update-ref', 'refs/heads/main', commit.decode())
        wire = packet(b'want ' + commit + b'\n') + b'0000' + done
        run(wire, [commit], completed=True)
        response = git('upload-pack', '--stateless-rpc', str(repo), input=wire)
        assert response.startswith(b'0008NAK\nPACK'), response[:100]
        git('index-pack', '--stdin', '--strict', input=response[8:])
    print('PASS fetch negotiation, hostile framing, count/byte limits and stock Git upload-pack', flush=True)

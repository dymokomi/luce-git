"""Differential ordinary-ref syntax against stock Git; no repo writes."""
import random
import subprocess

def check(binary):
    names = ['', 'HEAD', '@', '/refs/heads/a', 'refs/heads/a/', 'refs//a',
             'refs/heads/a.lock/b', 'refs/heads/a.LOCK', 'refs/.hidden/a',
             'refs/heads/a..b', 'refs/heads/a@{1}', 'refs/heads/@',
             'refs/heads/a./b', 'refs/heads/a.', 'refs/heads/-a',
             'refs/heads/é', 'refs/heads/日本語', 'refs/heads/a}b',
             'refs/heads/a]b', 'refs/heads/a\\b', 'heads/a',
             'refs/heads/' + 'a' * 4096]
    names += ['refs/heads/a' + chr(value) + 'b' for value in range(1, 128)]
    rng = random.Random(9213)
    alphabet = 'abc./@{}[]\\~^:?*-_ lock'
    names += ['refs/' + ''.join(rng.choice(alphabet) for _ in range(rng.randrange(1, 40))) for _ in range(180)]
    result = subprocess.run([str(binary), *names], capture_output=True, check=True, timeout=30)
    assert b'Sanitizer' not in result.stderr and b'runtime error:' not in result.stderr, result.stderr
    answers = result.stdout.decode().splitlines()
    assert len(answers) == len(names)
    for name, answer in zip(names, answers):
        stock = subprocess.run(['git', 'check-ref-format', name], capture_output=True, timeout=30)
        expected = stock.returncode == 0 and len(name.encode()) <= 4096
        assert (answer == 'yes') == expected, (repr(name), answer, stock.returncode)
    print(f'PASS {len(names)} ref syntax comparisons with stock Git and the explicit byte limit', flush=True)

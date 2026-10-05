"""Bash-only SHA-256 checked against known answers and Python's hashlib.

The subprocess PATH contains no programs. Includes NUL, high-bit bytes, padding
boundaries, UTF-8, and the actual published source. No hashing tools are invoked.
"""
import hashlib
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BashHashTests(unittest.TestCase):
    def hash_file(self, path):
        return subprocess.run(
            ['/bin/bash', '-c', 'set -u; source "$1"; sha256_bash "$2"',
             'sha-test', str(ROOT / 'lib/sha256.sh'), str(path)],
            env={'PATH': '/nonexistent-programs', 'LC_ALL': 'C'},
            capture_output=True, text=True, timeout=60,
        )

    def assert_digest(self, data, expected=None):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'input with spaces.bin'
            path.write_bytes(data)
            r = self.hash_file(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected or hashlib.sha256(data).hexdigest())

    def test_known_answers(self):
        self.assert_digest(b'', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
        self.assert_digest(b'abc', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
        self.assert_digest(b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',
                           '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1')

    def test_padding_boundaries(self):
        randomizer = random.Random(1804)
        for size in list(range(0, 130)) + [255, 256, 511, 512, 1023, 1024, 4096]:
            with self.subTest(size=size):
                self.assert_digest(bytes(randomizer.randrange(256) for _ in range(size)))

    def test_all_bytes_and_nuls(self):
        for data in [bytes(range(256)), bytes(range(255, -1, -1)), b'\0' * 128,
                     b'\xff' * 129, b'a\0b\0\n\r\t', b'"\'\\$()\n', 'Recovery — SHA-256 ✓'.encode()]:
            with self.subTest(data=data[:20]):
                self.assert_digest(data)

    def test_actual_core(self):
        self.assert_digest((ROOT / 'enrollment-lab.sh').read_bytes())

    def test_actual_launcher(self):
        self.assert_digest((ROOT / 'launcher.sh').read_bytes())

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            r = self.hash_file(Path(td) / 'absent')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, '')

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            r = self.hash_file(td)
        self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()

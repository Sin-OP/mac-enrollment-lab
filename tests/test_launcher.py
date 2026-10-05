"""Launcher fixtures never invoke a core mutation or contact the network."""
import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def run_shell(self, body, input_text=''):
        return subprocess.run(
            ['/bin/bash', '-c', f'source {shlex.quote(str(ROOT / "launcher.sh"))}\n'
             'reply() { IFS= read -r "$1"; }\n' + body],
            input=input_text, capture_output=True, text=True,
        )

    def test_published_launcher_matches_source(self):
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go2').read_bytes())

    def test_core_pin_matches_reviewed_script(self):
        r = self.run_shell('printf "%s" "$CORE_SHA"')
        self.assertEqual(r.stdout, hashlib.sha256((ROOT / 'enrollment-lab.sh').read_bytes()).hexdigest())

    def test_selection_preserves_spaces_and_stdout_is_only_path(self):
        r = self.run_shell('CHOICES=("/Volumes/Data One" "/Volumes/Data Two"); choose Target', '2\n')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, '/Volumes/Data Two\n')

    def test_invalid_number_does_not_select(self):
        r = self.run_shell('CHOICES=("/Volumes/Data One"); choose Target', '9999\n0\n01\n1\n')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, '/Volumes/Data One\n')
        self.assertEqual(r.stderr.count('Invalid selection'), 3)

    def test_cancel_has_no_path(self):
        r = self.run_shell('CHOICES=("/Volumes/Data"); choose Target', 'q\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, '')

    def test_no_volumes(self):
        r = self.run_shell('CHOICES=(); choose Target')
        self.assertNotEqual(r.returncode, 0)

    def test_bad_checksum_stops_download(self):
        r = self.run_shell('fetch_core() { return 0; }; core_hash() { echo bad; }; download_verified_core')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Checksum mismatch', r.stderr)

    def test_download_error_stops_before_hash(self):
        r = self.run_shell('fetch_core() { return 22; }; core_hash() { echo CALLED; }; download_verified_core')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('CALLED', r.stdout + r.stderr)

    def test_valid_download_is_checked_but_never_executed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'core.sh'
            p.write_text('#!/bin/bash\nprintf SHOULD_NOT_EXECUTE\n')
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            r = self.run_shell(f'CORE={shlex.quote(str(p))}; CORE_SHA={digest}; '
                               'fetch_core() { return 0; }; download_verified_core')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn('SHOULD_NOT_EXECUTE', r.stdout)

    def test_recovery_without_openssl_or_shasum(self):
        r = self.run_shell(f'CORE={shlex.quote(str(ROOT / "enrollment-lab.sh"))}; '
                           'fetch_core() { return 0; }; '
                           'launcher_openssl() { return 127; }; '
                           'launcher_shasum() { return 127; }; download_verified_core')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Using built-in Bash SHA-256', r.stderr)
        self.assertIn('Checksum verified', r.stderr)

    def test_corrupt_download_rejected_with_bash_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'bad-core'
            p.write_text('corrupt download')
            r = self.run_shell(f'CORE={shlex.quote(str(p))}; '
                               'fetch_core() { return 0; }; '
                               'launcher_openssl() { return 127; }; '
                               'launcher_shasum() { return 127; }; download_verified_core')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('Checksum mismatch', r.stderr)

    def test_apply_requires_explicit_confirmation(self):
        body = '''
choose_target() { echo '/Volumes/Data One'; }
choose_backup() { echo '/Volumes/USB/backup'; }
run_core() { printf 'COMMAND:%s\n' "$1"; }
guided_apply
'''
        r = self.run_shell(body, '\n\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('COMMAND:plan', r.stdout)
        self.assertNotIn('COMMAND:apply', r.stdout)

    def test_failed_plan_prevents_apply(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data'; }
run_core() { printf 'COMMAND:%s\n' "$1"; return 1; }
guided_apply
''', '\nAPPLY\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('COMMAND:apply', r.stdout)

    def test_confirmed_apply_preserves_arguments(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data One'; }
choose_backup() { echo '/Volumes/Backup Disk/snapshot'; }
run_core() { printf '<%s>' "$@"; echo; }
guided_apply
''', '\nAPPLY\n')
        self.assertEqual(r.returncode, 0)
        self.assertIn('<apply><--data-volume></Volumes/Data One><--create-admin><labadmin>'
                      '<--backup-dir></Volumes/Backup Disk/snapshot>', r.stdout)


if __name__ == '__main__':
    unittest.main()

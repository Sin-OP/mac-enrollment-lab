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
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go3').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go4').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go5').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go6').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go7').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go8').read_bytes())
        self.assertEqual((ROOT / 'launcher.sh').read_bytes(), (ROOT / 'docs/go9').read_bytes())

    def test_recovery_platform_check_needs_no_uname_binary(self):
        self.assertNotIn('/usr/bin/uname', (ROOT / 'launcher.sh').read_text())
        self.assertNotIn('/usr/bin/uname', (ROOT / 'enrollment-lab.sh').read_text())
        self.assertNotIn('/usr/bin/uname', (ROOT / 'docs/check').read_text())
        self.assertEqual(self.run_shell('OSTYPE=darwin23; launcher_is_macos').returncode, 0)
        self.assertNotEqual(self.run_shell('OSTYPE=linux; launcher_is_macos').returncode, 0)

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
        self.assertIn('curl exit 22', r.stderr)
        self.assertIn('HTTP error', r.stderr)

    def test_download_errors_explain_recovery_failures(self):
        hints = {
            6: 'DNS lookup failed',
            7: 'Could not connect',
            23: 'Could not write',
            28: 'timed out',
            35: 'TLS',
            60: 'TLS',
        }
        for code, hint in hints.items():
            with self.subTest(code=code):
                r = self.run_shell(f'fetch_core() {{ return {code}; }}; '
                                   'core_hash() { echo SHOULD_NOT_HASH; }; download_verified_core')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(f'curl exit {code}', r.stderr)
                self.assertIn(hint, r.stderr)
                self.assertNotIn('SHOULD_NOT_HASH', r.stdout + r.stderr)

    def test_ipv4_connection_failure_retries_standard_route(self):
        with tempfile.TemporaryDirectory() as td:
            core = Path(td) / 'core.sh'
            r = self.run_shell(f'''
CORE={shlex.quote(str(core))}
launcher_curl() {{
    if [ "$1" = -4fL ]; then return 7; fi
    printf '%s\\n' "$1" > "$CORE"
}}
fetch_core && /bin/cat "$CORE"
''')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), '-fL')
            self.assertIn('standard network route', r.stderr)

    def test_http_error_does_not_retry_another_route(self):
        with tempfile.TemporaryDirectory() as td:
            core = Path(td) / 'core.sh'
            r = self.run_shell(f'''
CORE={shlex.quote(str(core))}
launcher_curl() {{
    printf '%s\\n' "$1"
    return 22
}}
fetch_core
''')
            self.assertEqual(r.returncode, 22)
            self.assertEqual(r.stdout, '-4fL\n')
            self.assertNotIn('standard network route', r.stderr)

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

    def test_preview_can_finish_without_backup_or_apply(self):
        body = '''
choose_target() { echo '/Volumes/Data One'; }
choose_backup() { echo SHOULD_NOT_SELECT; }
run_core() { printf 'COMMAND:%s\n' "$1"; }
guided_apply
'''
        r = self.run_shell(body, '\n\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('COMMAND:plan', r.stdout)
        self.assertNotIn('COMMAND:apply', r.stdout)
        self.assertNotIn('SHOULD_NOT_SELECT', r.stdout)
        self.assertIn('PREVIEW PASSED', r.stderr)
        self.assertIn('apply was not requested', r.stderr)

    def test_apply_still_requires_explicit_confirmation(self):
        body = '''
choose_target() { echo '/Volumes/Data One'; }
choose_backup() { echo '/Volumes/USB/backup'; }
run_core() { printf 'COMMAND:%s\n' "$1"; }
guided_apply
'''
        r = self.run_shell(body, '\nY\n\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('COMMAND:plan', r.stdout)
        self.assertNotIn('COMMAND:apply', r.stdout)
        self.assertIn('Apply cancelled before changes', r.stderr)

    def test_failed_plan_prevents_apply(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data'; }
run_core() { printf 'COMMAND:%s\n' "$1"; return 1; }
guided_apply
''', '\nAPPLY\n')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('COMMAND:apply', r.stdout)
        self.assertIn('PREVIEW BLOCKED (exit 1)', r.stderr)

    def test_preview_cancel_is_distinct_from_failed_plan(self):
        r = self.run_shell('''
choose_target() { return 1; }
run_core() { echo SHOULD_NOT_RUN; }
guided_apply
''')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Preview cancelled', r.stderr)
        self.assertNotIn('SHOULD_NOT_RUN', r.stdout + r.stderr)

    def test_unavailable_backup_is_blocked_not_called_cancellation(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data'; }
choose_backup() { return 2; }
run_core() { [ "$1" != apply ]; }
guided_apply
''', '\nY\n')
        self.assertEqual(r.returncode, 2)
        self.assertIn('PREVIEW PASSED', r.stderr)
        self.assertIn('Backup selection blocked (exit 2)', r.stderr)
        self.assertNotIn('Apply cancelled', r.stderr)

    def test_apply_failure_reports_stage_and_exit(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data'; }
choose_backup() { echo '/Volumes/Backup/snapshot'; }
run_core() { [ "$1" != apply ] || return 9; }
guided_apply
''', '\nY\nAPPLY\n')
        self.assertEqual(r.returncode, 9)
        self.assertIn('PREVIEW PASSED', r.stderr)
        self.assertIn('APPLY FAILED (exit 9)', r.stderr)

    def test_confirmed_apply_preserves_arguments(self):
        r = self.run_shell('''
choose_target() { echo '/Volumes/Data One'; }
choose_backup() { echo '/Volumes/Backup Disk/snapshot'; }
run_core() { printf '<%s>' "$@"; echo; }
guided_apply
''', '\nY\nAPPLY\n')
        self.assertEqual(r.returncode, 0)
        self.assertIn('<apply><--data-volume></Volumes/Data One><--create-admin><labadmin>'
                      '<--backup-dir></Volumes/Backup Disk/snapshot>', r.stdout)


if __name__ == '__main__':
    unittest.main()

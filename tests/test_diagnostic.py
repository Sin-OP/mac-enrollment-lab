"""The diagnostic must preserve failure evidence and only dispatch plan."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticTests(unittest.TestCase):
    def test_failed_preview_reports_command_and_exit_status(self):
        with tempfile.TemporaryDirectory() as td:
            core = Path(td) / 'fake-core.sh'
            core.write_text('printf "ARG:%s\\n" "$@"\nprintf "fixture failure\\n"\nexit 41\n')
            result = subprocess.run(['/bin/bash', '-c',
                f'source {shlex.quote(str(ROOT / "docs/check"))}; '
                f'LAB_TMP={shlex.quote(td)}; CORE={shlex.quote(str(core))}; '
                'diagnostic_plan "/Volumes/Data One" epyon'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 41)
            self.assertIn('exit code: 41', result.stderr)
            trace = (Path(td) / 'preview.log').read_text()
            self.assertIn('ARG:plan\nARG:--data-volume\nARG:/Volumes/Data One\nARG:--create-admin\nARG:epyon\n', trace)
            self.assertIn('fixture failure', result.stdout)
            self.assertNotIn('ARG:apply', trace)
            self.assertNotIn('ARG:restore', trace)

    def test_failed_verification_prevents_preview(self):
        result = subprocess.run(['/bin/bash', '-c',
            f'source {shlex.quote(str(ROOT / "docs/check"))}; '
            'download_verified_core() { return 1; }; '
            'diagnostic_plan() { echo SHOULD_NOT_RUN; }; diagnostic_main; '
            'rc=$?; [ -z "$LAB_TMP" ] || /bin/rm -rf "$LAB_TMP"; exit "$rc"'],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('SHOULD_NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()

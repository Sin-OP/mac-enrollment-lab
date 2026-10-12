"""The diagnostic must report stages without exposing trace values or mutating."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticTests(unittest.TestCase):
    @staticmethod
    def sourced_scripts():
        return (f'source {shlex.quote(str(ROOT / "launcher.sh"))}; '
                f'source {shlex.quote(str(ROOT / "diagnostic.sh"))}; ')

    def test_failed_preview_reports_command_and_exit_status(self):
        with tempfile.TemporaryDirectory() as td:
            core = Path(td) / 'fake-core.sh'
            core.write_text('xml="<data>LAB_SECRET_FIXTURE</data>"\n'
                            'printf "ARG:%s\\n" "$@"\n'
                            'printf "fixture failure\\n" >&2\nexit 41\n')
            result = subprocess.run(['/bin/bash', '-c',
                self.sourced_scripts() +
                f'LAB_TMP={shlex.quote(td)}; CORE={shlex.quote(str(core))}; '
                'diagnostic_plan "/Volumes/Data One" epyon'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 41)
            self.assertIn('PREVIEW BLOCKED (exit 41)', result.stderr)
            self.assertIn('ARG:plan\nARG:--data-volume\nARG:/Volumes/Data One\nARG:--create-admin\nARG:epyon\n', result.stdout)
            self.assertIn('fixture failure', result.stderr)
            self.assertNotIn('LAB_SECRET_FIXTURE', result.stdout + result.stderr)
            self.assertFalse((Path(td) / 'preview.log').exists())
            self.assertNotIn('ARG:apply', result.stdout)
            self.assertNotIn('ARG:restore', result.stdout)

    def test_supplied_target_uses_labadmin_not_stale_default(self):
        result = subprocess.run(['/bin/bash', '-c',
            self.sourced_scripts() +
            'download_verified_core() { return 0; }; '
            'diagnostic_plan() { printf "TARGET:%s ACCOUNT:%s\\n" "$1" "$2"; }; '
            'diagnostic_main "/Volumes/HDD - Data"'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('TARGET:/Volumes/HDD - Data ACCOUNT:labadmin', result.stdout)
        self.assertNotIn('epyon', result.stdout + result.stderr)

    def test_failed_verification_prevents_preview(self):
        result = subprocess.run(['/bin/bash', '-c',
            self.sourced_scripts() +
            'download_verified_core() { echo DOWNLOAD_ATTEMPTED; return 1; }; '
            'diagnostic_plan() { echo SHOULD_NOT_RUN; }; '
            'diagnostic_main "/Volumes/Data" labadmin; '
            'exit $?'],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DOWNLOAD_ATTEMPTED', result.stdout)
        self.assertNotIn('SHOULD_NOT_RUN', result.stdout)


if __name__ == '__main__':
    unittest.main()

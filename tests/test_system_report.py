"""Standalone system-report tests: no live system collection or network calls."""
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'system-report.sh'


class SystemReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='system-report-test-')
        self.root = Path(self.temp.name)
        self.report = self.root / 'report'
        self.work = self.root / 'work'
        self.report.mkdir()
        self.work.mkdir()
        (self.work / 'findings').write_text('')

    def tearDown(self):
        self.temp.cleanup()

    def run_shell(self, body, timeout=15, input_text=''):
        prefix = f'''
source {shlex.quote(str(SCRIPT))}
export LC_ALL=C
SR_DIR={shlex.quote(str(self.report))}
SR_WORK={shlex.quote(str(self.work))}
'''
        return subprocess.run(['/bin/bash', '-c', prefix + body],
                              capture_output=True, text=True, timeout=timeout, input=input_text)

    def test_numbered_choice_preserves_spaces_and_rejects_invalid_numbers(self):
        result = self.run_shell('''
sr_find_volumes() { SR_VOLUMES=("/Volumes/Data One" "/Volumes/USB Two"); }
sr_reply() { IFS= read -r "$1"; }
sr_choose Destination Temporary
''', input_text='999\n2\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '/Volumes/USB Two\n')
        self.assertIn('Enter a listed number', result.stderr)

    def test_default_choice_and_cancel_are_distinct(self):
        body = '''
sr_find_volumes() { SR_VOLUMES=(); }
sr_reply() { IFS= read -r "$1"; }
sr_choose Destination Temporary
'''
        default = self.run_shell(body, input_text='\n')
        cancelled = self.run_shell(body, input_text='q\n')
        self.assertEqual(default.returncode, 0)
        self.assertEqual(default.stdout, '')
        self.assertNotEqual(cancelled.returncode, 0)

    def test_missing_program_is_unavailable_and_next_probe_can_run(self):
        result = self.run_shell('''
sr_probe absent 'Missing fixture' /does/not/exist
sr_probe present 'Present fixture' /usr/bin/true
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = (self.report / 'checks.tsv').read_text()
        self.assertIn('absent\tUNAVAILABLE\t127', rows)
        self.assertIn('present\tOK\t0', rows)

    def test_failed_command_records_exit_without_dumping_output(self):
        result = self.run_shell("sr_probe broken 'Broken fixture' /bin/bash -c "
                                "'printf PRIVATE_FIXTURE; exit 7'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('broken\tFAILED\t7', (self.report / 'checks.tsv').read_text())
        self.assertNotIn('PRIVATE_FIXTURE', (self.report / 'report.txt').read_text())

    def test_timeout_is_bounded_and_does_not_block_next_probe(self):
        start = time.monotonic()
        result = self.run_shell('''
SR_PROBE_SECONDS=1
sr_probe slow 'Slow fixture' /bin/sleep 20
sr_probe next 'Next fixture' /usr/bin/true
''', timeout=6)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(time.monotonic() - start, 5)
        rows = (self.report / 'checks.tsv').read_text()
        self.assertIn('slow\tTIMEOUT\t', rows)
        self.assertIn('next\tOK\t0', rows)

    def test_exhausted_budget_skips_remaining_command(self):
        result = self.run_shell('''
SECONDS=2
SR_DEADLINE=1
sr_probe budget Budget /bin/bash -c 'echo SHOULD_NOT_EXECUTE'
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('budget\tSKIPPED\t124', (self.report / 'checks.tsv').read_text())
        self.assertEqual((self.work / 'probe-1').read_bytes(), b'')

    def test_raw_probe_output_has_size_limit(self):
        payload = self.root / 'large.txt'
        payload.write_bytes(b'x' * 1024 * 1024)
        result = self.run_shell(f'sr_probe huge Huge /bin/cat {shlex.quote(str(payload))}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual((self.work / 'probe-1').stat().st_size, 128 * 1024)
        self.assertNotIn('huge\tOK\t', (self.report / 'checks.tsv').read_text())

    def test_disk_allowlist_excludes_uuid_and_volume_name(self):
        raw = self.work / 'disk'
        raw.write_text('''Device Identifier: disk3s5
Volume Name: PERSONAL_VOLUME_FIXTURE
Volume UUID: PRIVATE_UUID_FIXTURE
SMART Status: Verified
FileVault: No
Locked: No
''')
        result = self.run_shell(f'SR_OUTPUT={shlex.quote(str(raw))}; sr_disk_fields target')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.report / 'report.txt').read_text()
        self.assertIn('disk3s5', report)
        self.assertIn('SMART Status: Verified', report)
        self.assertNotIn('PRIVATE_UUID_FIXTURE', report)
        self.assertNotIn('PERSONAL_VOLUME_FIXTURE', report)

    def test_unrecognized_metadata_is_explicitly_unknown(self):
        raw = self.work / 'disk'
        raw.write_text('Successful command but no known metadata\n')
        result = self.run_shell(f'SR_OUTPUT={shlex.quote(str(raw))}; sr_disk_fields target')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('target.parse\tUNKNOWN\t', (self.report / 'checks.tsv').read_text())

    def test_architecture_evidence_matrix(self):
        cases = [
            ('arm64', '1', '0', '', 'Apple silicon'),
            ('arm64', '', '', '', 'Apple silicon'),
            ('x86_64', '0', '', '', 'Intel'),
            ('x86_64', '', '', 'GenuineIntel', 'Intel'),
            ('x86_64', '1', '1', '', 'Apple silicon'),
            ('x86_64', '', '1', '', 'Apple silicon'),
            ('x86_64', '', '', '', 'UNKNOWN'),
            ('arm64', '0', '0', '', 'UNKNOWN'),
            ('arm64', '1', '1', '', 'UNKNOWN'),
            ('arm64', '1', '0', 'GenuineIntel', 'UNKNOWN'),
            ('unknown', '', '', '', 'UNKNOWN'),
        ]
        for arch, capability, translated, vendor, family in cases:
            with self.subTest(arch=arch, capability=capability, translated=translated, vendor=vendor):
                args = ' '.join(shlex.quote(v) for v in (arch, capability, translated, vendor))
                result = self.run_shell(f'sr_architecture {args}; printf "%s" "$SR_HARDWARE_FAMILY"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, family)

    def test_plist_reader_falls_back_when_recovery_tool_is_missing(self):
        result = self.run_shell('''
sr_probe() {
    SR_OUTPUT="$SR_WORK/raw"
    SR_RC=0; SR_STATUS=OK
    case "$1" in
        *.PlistBuddy) SR_RC=127; SR_STATUS=UNAVAILABLE; : > "$SR_OUTPUT" ;;
        *.plutil) printf '14.4\n' > "$SR_OUTPUT" ;;
    esac
    sr_record "$1" "$2" "$SR_STATUS" "$SR_RC" 0
}
sr_plist_os_value target.version Version ProductVersion /fixture/SystemVersion.plist
printf '%s' "$SR_VALUE"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '14.4')
        rows = (self.report / 'checks.tsv').read_text()
        self.assertIn('target.version.PlistBuddy\tUNAVAILABLE', rows)
        self.assertIn('target.version.plutil\tOK', rows)
        self.assertNotIn('unresolved', rows)

    def test_unusable_plist_values_remain_unknown_after_both_readers(self):
        result = self.run_shell('''
sr_probe() {
    SR_OUTPUT="$SR_WORK/raw"
    printf 'not a version\n' > "$SR_OUTPUT"
    SR_STATUS=OK; SR_RC=0
    sr_record "$1" "$2" OK 0 0
}
sr_plist_os_value target.version Version ProductVersion /fixture/SystemVersion.plist
printf '%s' "$SR_VALUE"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        rows = (self.report / 'checks.tsv').read_text()
        self.assertIn('target.version.PlistBuddy.parse\tUNKNOWN', rows)
        self.assertIn('target.version.plutil.parse\tUNKNOWN', rows)
        self.assertIn('target.version.unresolved\tUNKNOWN', rows)

    def test_running_os_falls_back_and_keeps_version_and_build_separate(self):
        result = self.run_shell('''
sr_probe() {
    SR_OUTPUT="$SR_WORK/raw"
    SR_STATUS=OK; SR_RC=0
    case "$1" in
        boot.os.version|boot.os.build) SR_STATUS=UNAVAILABLE; SR_RC=127; : > "$SR_OUTPUT" ;;
        boot.os.version.*) printf '26.0.1\n' > "$SR_OUTPUT" ;;
        boot.os.build.*) printf '25A362\n' > "$SR_OUTPUT" ;;
    esac
    sr_record "$1" "$2" "$SR_STATUS" "$SR_RC" 0
}
sr_running_os
printf '%s' "$SR_RUNNING_VERSION"
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '26.0.1')
        report = (self.report / 'report.txt').read_text()
        self.assertIn('ProductVersion: 26.0.1', report)
        self.assertIn('ProductBuildVersion: 25A362', report)

    def test_os_metadata_formats_do_not_imply_a_version_support_ceiling(self):
        for version in ['10.12.6', '10.15.7', '11.7.10', '14.4', '15.0', '26.0.1', '99.1']:
            with self.subTest(version=version):
                result = self.run_shell(f'sr_os_value_valid ProductVersion {version}')
                self.assertEqual(result.returncode, 0, result.stderr)
        for value in ['', 'Sonoma', '14.x', '14.4 extra']:
            with self.subTest(invalid=value):
                self.assertNotEqual(self.run_shell(
                    f'sr_os_value_valid ProductVersion {shlex.quote(value)}').returncode, 0)

    def test_old_os_skips_commands_that_did_not_exist_yet(self):
        result = self.run_shell('''
sr_probe() { echo SHOULD_NOT_RUN >&2; return 9; }
SR_RUNNING_VERSION=10.12.6
sr_root_policy
sr_apfs_inventory
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('SHOULD_NOT_RUN', result.stderr)
        rows = (self.report / 'checks.tsv').read_text()
        self.assertIn('security.seal\tSKIPPED', rows)
        self.assertIn('storage.roles\tSKIPPED', rows)

    def test_new_or_unknown_os_still_attempts_capability_probes(self):
        for version in ['11.0', '14.4', '26.0', '99.0', '']:
            with self.subTest(version=version):
                result = self.run_shell(f'''
sr_probe() {{ SR_STATUS=UNAVAILABLE; printf '%s\n' "$1"; }}
SR_RUNNING_VERSION={shlex.quote(version)}
sr_root_policy
sr_apfs_inventory
''')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ['security.seal', 'storage.roles'])

    def test_capacity_allows_spaces_in_filesystem_and_mount_names(self):
        raw = self.work / 'capacity'
        for row, capacity in [
            ('map auto_home 0 0 0 100% /System/Volumes/Data/home', '0 / 0 / 0'),
            ('/dev/disk3s1 100 40 60 40% /Volumes/Data One', '100 / 40 / 60'),
            ('/dev/disk3s1 100 40 60 40% /Volumes/Mount 1 2 3 4% extra', '100 / 40 / 60'),
        ]:
            with self.subTest(row=row):
                (self.report / 'report.txt').write_text('')
                raw.write_text('Filesystem 1024-blocks Used Available Capacity Mounted on\n' + row + '\n')
                result = self.run_shell(f'SR_OUTPUT={shlex.quote(str(raw))}; sr_space capacity')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(capacity, (self.report / 'report.txt').read_text())
                self.assertFalse((self.report / 'checks.tsv').exists())

    def test_hfs_and_apfs_metadata_are_reported_without_assuming_roles(self):
        raw = self.work / 'disk'
        for filesystem in ['Journaled HFS+', 'APFS']:
            with self.subTest(filesystem=filesystem):
                raw.write_text(f'File System Personality: {filesystem}\nVolume Read-Only: No\n')
                result = self.run_shell(f'SR_OUTPUT={shlex.quote(str(raw))}; sr_disk_fields target')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(filesystem, (self.report / 'report.txt').read_text())
                self.assertFalse((self.report / 'checks.tsv').exists())

    def test_mount_without_system_plist_is_explicit_and_does_not_run_readers(self):
        result = self.run_shell(f'''
sr_probe() {{ echo SHOULD_NOT_RUN >&2; return 9; }}
sr_os_file selected {shlex.quote(str(self.root))}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('SHOULD_NOT_RUN', result.stderr)
        self.assertIn('selected.metadata\tSKIPPED', (self.report / 'checks.tsv').read_text())

    def test_non_macos_is_rejected_before_creating_report(self):
        result = self.run_shell(f'OSTYPE=linux-gnu; system_report_main --no-network --output-parent {shlex.quote(str(self.root))}')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('for macOS and macOS Recovery', result.stderr)
        self.assertEqual(list(self.root.glob('mac-support.*')), [])

    def test_network_success_without_http_code_is_unknown(self):
        result = self.run_shell('''
sr_probe() {
    SR_OUTPUT="$SR_WORK/network"
    printf 'http_code=000\n' > "$SR_OUTPUT"
    SR_STATUS=OK; SR_RC=0
    sr_record "$1" "$2" OK 0 0
}
sr_network github https://github.com/ automatic
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('github.automatic.parse\tUNKNOWN', (self.report / 'checks.tsv').read_text())
        self.assertNotIn('HTTP response received', (self.report / 'report.txt').read_text())

    def test_control_characters_cannot_inject_report_lines(self):
        result = self.run_shell("sr_field Label $'text\\nspoof\\t\\033[31m'; "
                                "sr_record check $'title\\tdata\\nrow' UNKNOWN 0 0")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = (self.report / 'report.txt').read_text()
        self.assertIn('text?spoof??[31m', report)
        self.assertNotIn('\x1b', report)
        self.assertEqual(len((self.report / 'checks.tsv').read_text().splitlines()), 1)

    def test_report_write_failure_is_retained(self):
        (self.report / 'report.txt').mkdir()
        result = self.run_shell('sr_field Label Value; printf "%s" "$SR_WRITE_FAILED"')
        self.assertEqual(result.stdout, 'true')

    def test_collection_failure_keeps_incomplete_report_and_removes_raw_scratch(self):
        raw_path_record = self.root / 'raw-path'
        result = self.run_shell(f'''
sr_collect() {{
    printf '%s' "$SR_WORK" > {shlex.quote(str(raw_path_record))}
    printf 'PRIVATE_RAW_FIXTURE' > "$SR_WORK/raw"
    return 1
}}
system_report_main --output-parent {shlex.quote(str(self.root))} --no-network
''')
        self.assertNotEqual(result.returncode, 0)
        bundles = list(self.root.glob('mac-support.*'))
        self.assertEqual(len(bundles), 1)
        self.assertIn('INCOMPLETE REPORT', (bundles[0] / 'summary.txt').read_text())
        self.assertFalse(Path(raw_path_record.read_text()).exists())

    def test_full_fixture_collection_preserves_target_and_removes_raw_scratch(self):
        target = self.root / 'Target with spaces'
        target.mkdir()
        sentinel = target / 'unchanged'
        sentinel.write_bytes(b'unchanged target data')
        result = self.run_shell(f'''
sr_find_volumes() {{ SR_VOLUMES=(); }}
sr_probe() {{
    SR_OUTPUT="$SR_WORK/raw"
    case "$1" in
        storage.boot|storage.target)
            printf 'Device Identifier: disk3s5\nVolume UUID: PRIVATE_UUID_FIXTURE\nFileVault: No\n' > "$SR_OUTPUT" ;;
        storage.roles)
            printf 'APFS Volume Disk (Role): disk3s5 (Data)\nUUID: PRIVATE_UUID_FIXTURE\n' > "$SR_OUTPUT" ;;
        storage.tmp|storage.target.space)
            printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/disk3 100 40 60 40%% /\n' > "$SR_OUTPUT" ;;
        *) printf 'fixture\n' > "$SR_OUTPUT" ;;
    esac
    SR_STATUS=OK; SR_RC=0
    sr_record "$1" "$2" OK 0 0
}}
system_report_main --target {shlex.quote(str(target))} --output-parent {shlex.quote(str(self.root))} --no-network
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        bundle = Path(result.stdout.strip())
        self.assertEqual({p.name for p in bundle.iterdir()}, {'report.txt', 'checks.tsv', 'summary.txt'})
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
        for file in bundle.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('PRIVATE_UUID_FIXTURE', file.read_text())
        self.assertIn('APFS volume / role: disk3s5 (Data)', (bundle / 'report.txt').read_text())
        self.assertIn('network\tSKIPPED', (bundle / 'checks.tsv').read_text())
        self.assertEqual(list(target.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b'unchanged target data')


if __name__ == '__main__':
    unittest.main()

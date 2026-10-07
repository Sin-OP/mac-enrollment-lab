"""Offline regression tests. All writes are confined to temporary fixtures.

Production disk discovery, Directory Services and Recovery checks are never run.
The mock backend is defined only in this test process, not exposed by the CLI.
"""

import plistlib
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "enrollment-lab.sh"
UUID = "11111111-2222-3333-4444-555555555555"


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="enrollment-lab-test-")
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / "Data with spaces"
        self.backup = self.root / "backup"
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.node = self.target / "private/var/db/dslocal/nodes/Default"
        self.settings = self.target / "private/var/db/ConfigurationProfiles/Settings"
        for d in [self.node / "users", self.node / "groups", self.settings,
                  self.target / "private/etc", self.target / "Users"]:
            d.mkdir(parents=True, exist_ok=True)
        self.hosts = self.target / "private/etc/hosts"
        self.hosts.write_text("127.0.0.1 localhost\n# retain this comment\n")
        self.hosts.chmod(0o644)
        self.write_plist(self.node / "users/root.plist", {"uid": ["0"], "name": ["root"]})
        self.write_plist(self.node / "groups/admin.plist", {"users": ["root"]})
        self.write_plist(self.scratch / "target.plist", {"FileVault": False})
        self.volume_info = {
            "FileVault": False, "MountPoint": str(self.target),
            "VolumeUUID": UUID, "DeviceIdentifier": "disk9s1",
            "FilesystemType": "apfs", "Writable": True,
        }
        self.write_plist(self.root / "disk-info.plist", self.volume_info)
        self.write_plist(self.root / "live-info.plist", {"VolumeUUID": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"})
        self.inventory = {"Containers": [{"ContainerReference": "disk9", "Volumes": [
            {"DeviceIdentifier": "disk9s1", "Roles": ["Data"]},
            {"DeviceIdentifier": "disk9s2", "Roles": ["System"]},
        ]}]}
        self.write_plist(self.root / "inventory.plist", self.inventory)
        (self.settings / ".cloudConfigRecordFound").write_bytes(b"original hidden record\0")
        (self.settings / ".cloudConfigHasActivationRecord").write_text("activation")
        self.before = self.capture()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_plist(path, value):
        path.write_bytes(plistlib.dumps(value))

    def capture(self):
        return {str(p.relative_to(self.target)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.target.rglob("*") if p.is_file()}

    def run_bash(self, body, *, transaction_cleanup=False, real_backup_validation=False):
        # Parse plist fixtures without requiring Apple's PlistBuddy on Linux.
        parser = (
            "import plistlib,sys; v=plistlib.load(open(sys.argv[1],'rb')); "
            "\nfor k in sys.argv[2].split(':'): v=v[int(k)] if isinstance(v,list) else v[k]"
            "\nprint(str(v).lower() if isinstance(v,bool) else v)"
        )
        setup = f"""
source {shlex.quote(str(SCRIPT))}
set -u
set -o pipefail
umask 077
TARGET={shlex.quote(str(self.target))}
BACKUP={shlex.quote(str(self.backup))}
SCRATCH={shlex.quote(str(self.scratch))}
ADMIN=labadmin
VOLUME_UUID={UUID}
plist_get() {{ {shlex.quote(sys.executable)} -c {shlex.quote(parser)} "$1" "$2" 2>/dev/null; }}
disk_info() {{
    if [ "$1" = /System/Volumes/Data ]; then
        /bin/cat {shlex.quote(str(self.root / 'live-info.plist'))}
    else
        /bin/cat {shlex.quote(str(self.root / 'disk-info.plist'))}
    fi
}}
apfs_inventory() {{ /bin/cat {shlex.quote(str(self.root / 'inventory.plist'))}; }}
create_admin() {{
    printf 'fixture account\\n' > "$TARGET/private/var/db/dslocal/nodes/Default/users/$ADMIN.plist" || return 1
    printf 'fixture membership\\n' >> "$TARGET/private/var/db/dslocal/nodes/Default/groups/admin.plist" || return 1
    /bin/mkdir -m 700 "$TARGET/Users/$ADMIN" || return 1
    CREATED_HOME=true
}}
build_paths
"""
        if not real_backup_validation:
            setup += "validate_backup_parent() { return 0; }\n"
        if transaction_cleanup:
            setup += "trap cleanup EXIT\n"
        return subprocess.run(
            ["/bin/bash", "-c", setup + body], text=True, capture_output=True,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(self.root)},
        )

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_apply_verify_and_restore_exact_files_and_modes(self):
        r = self.run_bash("validate_fresh_install && apply_transaction && load_backup && restore_snapshot")
        self.assert_ok(r)
        self.assertEqual(self.capture(), self.before)
        self.assertFalse((self.target / "Users/labadmin").exists())

    def test_hidden_markers_are_backed_up(self):
        self.assert_ok(self.run_bash("prepare_backup"))
        self.assertEqual((self.backup / "3.original").read_bytes(), b"original hidden record\0")
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o700)

    def test_no_failure_is_reported_as_success(self):
        r = self.run_bash("write_markers() { return 23; }; apply_transaction", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("restored", r.stderr)
        self.assertNotIn("Changes staged", r.stderr)
        self.assertEqual(self.capture(), self.before)

    def test_partial_account_failure_rolls_back(self):
        r = self.run_bash("""
create_admin() {
    printf partial > "$TARGET/private/var/db/dslocal/nodes/Default/users/$ADMIN.plist"
    return 1
}
apply_transaction
""", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.capture(), self.before)

    def test_hosts_write_failure_rolls_back_account(self):
        r = self.run_bash("replace_hosts() { return 1; }; apply_transaction", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.capture(), self.before)

    def test_backup_failure_prevents_mutation(self):
        self.backup.mkdir()
        r = self.run_bash("apply_transaction", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.capture(), self.before)

    def test_target_drift_prevents_restore(self):
        r = self.run_bash("""
apply_transaction || exit 1
printf '127.0.0.1 new-entry\n' >> "$TARGET/private/etc/hosts"
load_backup
""")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("changed since apply", r.stderr)
        self.assertIn("new-entry", self.hosts.read_text())

    def test_changed_account_home_prevents_restore(self):
        r = self.run_bash("""
apply_transaction || exit 1
printf valuable > "$TARGET/Users/labadmin/document"
load_backup
""")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("contains data", r.stderr)
        self.assertEqual((self.target / "Users/labadmin/document").read_text(), "valuable")

    def test_corrupt_snapshot_prevents_any_restore(self):
        r = self.run_bash("""
apply_transaction || exit 1
printf tampered > "$BACKUP/7.original"
load_backup && restore_snapshot
""")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("checksum mismatch", r.stderr)
        self.assertIn("BEGIN mac-enrollment-lab", self.hosts.read_text())

    def test_wrong_volume_backup_rejected(self):
        r = self.run_bash("apply_transaction && VOLUME_UUID=other && load_backup")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("another volume", r.stderr)

    def test_backup_metadata_never_evaluated(self):
        r = self.run_bash("""
apply_transaction || exit 1
printf '%s\n' '$(touch SHOULD_NOT_EXIST)' > "$BACKUP/admin-name"
load_backup
""")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Invalid backup account name", r.stderr)
        self.assertFalse((ROOT / "SHOULD_NOT_EXIST").exists())

    def test_symlinked_hosts_rejected(self):
        outside = self.root / "outside"
        outside.write_text("untouched")
        self.hosts.unlink()
        self.hosts.symlink_to(outside)
        r = self.run_bash("validate_fresh_install")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(outside.read_text(), "untouched")

    def test_symlinked_parent_rejected(self):
        real = self.target / "private/etc-real"
        self.hosts.parent.rename(real)
        self.hosts.parent.symlink_to(real, target_is_directory=True)
        r = self.run_bash("safe_path private/etc/hosts")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Symlink", r.stderr)

    def test_completed_setup_rejected(self):
        (self.target / "private/var/db/.AppleSetupDone").touch()
        r = self.run_bash("validate_fresh_install")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Setup-completion marker exists", r.stderr)

    def test_account_alias_collision_rejected(self):
        self.write_plist(self.node / "users/different.plist", {
            "uid": ["502"], "name": ["different", "LABADMIN"],
        })
        r = self.run_bash("validate_fresh_install")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("account or alias", r.stderr)

    def test_filevault_creation_rejected(self):
        self.write_plist(self.scratch / "target.plist", {"FileVault": True})
        r = self.run_bash("validate_fresh_install")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FileVault", r.stderr)

    def test_configured_profile_store_rejected(self):
        store = self.settings.parent / "Store"
        store.mkdir()
        (store / "profile").write_text("fixture")
        r = self.run_bash("validate_fresh_install")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Unexpected profile-store file", r.stderr)

    def make_observed_profile_store(self):
        store = self.settings.parent / 'Store'
        store.mkdir(exist_ok=True)
        for name in ['.fl8FC95EC6', 'ConfigProfiles.binary', 'Provisioning.binary']:
            (store / name).write_bytes(b'')
        (store / 'MCXPrivate.keychain').write_bytes(b'opaque fixture keychain')
        self.write_plist(store / 'MDM_ComputerPrefs.plist', {'MDMServerHash': bytes(range(32))})
        return store

    def test_observed_store_accepted_with_unknown_enrollment_status(self):
        store = self.make_observed_profile_store()
        for fmt in [plistlib.FMT_XML, plistlib.FMT_BINARY]:
            with self.subTest(fmt=fmt):
                (store / 'MDM_ComputerPrefs.plist').write_bytes(
                    plistlib.dumps({'MDMServerHash': bytes(range(32))}, fmt=fmt))
                snapshot = self.capture()
                r = self.run_bash('validate_fresh_install')
                self.assert_ok(r)
                self.assertIn('Enrollment status remains UNKNOWN', r.stderr)
                self.assertEqual(self.capture(), snapshot)

    def test_observed_store_preserved_by_apply_and_restore(self):
        store = self.make_observed_profile_store()
        snapshot = self.capture()
        r = self.run_bash('validate_fresh_install && apply_transaction && load_backup && restore_snapshot')
        self.assert_ok(r)
        self.assertEqual(self.capture(), snapshot)

    def test_populated_profile_databases_rejected(self):
        store = self.make_observed_profile_store()
        for name in ['ConfigProfiles.binary', 'Provisioning.binary']:
            with self.subTest(name=name):
                (store / name).write_bytes(b'profile payload')
                r = self.run_bash('validate_profile_store')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('Nonempty profile database', r.stderr)
                (store / name).write_bytes(b'')

    def test_profile_preferences_schema_is_strict(self):
        store = self.make_observed_profile_store()
        for value in [
            {}, {'MDMServerHash': b''}, {'MDMServerHash': 'text'},
            {'MDMServerHash': b'hash', 'Other': True}, {'MDM ServerHash': b'hash'},
            {'MDMServerHash': {'nested': b'hash'}}, {'MDMServerHash': [b'hash']},
        ]:
            with self.subTest(value=value):
                self.write_plist(store / 'MDM_ComputerPrefs.plist', value)
                r = self.run_bash('validate_profile_store')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('Unrecognized profile preferences', r.stderr)

    def test_unexpected_hidden_profile_file_rejected(self):
        store = self.make_observed_profile_store()
        (store / '.unexpected').write_bytes(b'')
        r = self.run_bash('validate_profile_store')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Unexpected profile-store file: .unexpected;', r.stderr)

    def test_marker_prefix_is_literal_lowercase_fl(self):
        store = self.make_observed_profile_store()
        marker = store / '.fl8FC95EC6'
        for name in ['.f18FC95EC6', '.FL8FC95EC6', '.fl8FC95EC', '.fl8FC95EC67',
                     '.fl8FC95ECG', 'xfl8FC95EC6']:
            with self.subTest(name=name):
                marker.rename(store / name)
                r = self.run_bash('validate_profile_store')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(name, r.stderr)
                (store / name).rename(marker)

    def test_nonempty_fl_marker_rejected(self):
        store = self.make_observed_profile_store()
        (store / '.fl8FC95EC6').write_bytes(b'not empty')
        r = self.run_bash('validate_profile_store')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('.fl8FC95EC6', r.stderr)

    def test_profile_store_symlink_entry_rejected(self):
        store = self.make_observed_profile_store()
        (store / 'ConfigProfiles.binary').unlink()
        (store / 'ConfigProfiles.binary').symlink_to(store / 'Provisioning.binary')
        self.assertNotEqual(self.run_bash('validate_profile_store').returncode, 0)

    def test_incomplete_observed_store_rejected(self):
        store = self.make_observed_profile_store()
        (store / 'ConfigProfiles.binary').unlink()
        self.assertNotEqual(self.run_bash('validate_profile_store').returncode, 0)

    def test_profile_store_subdirectory_rejected(self):
        store = self.make_observed_profile_store()
        (store / 'extra').mkdir()
        self.assertNotEqual(self.run_bash('validate_profile_store').returncode, 0)

    def test_multiple_store_markers_rejected(self):
        store = self.make_observed_profile_store()
        (store / '.fl01234567').write_bytes(b'')
        self.assertNotEqual(self.run_bash('validate_profile_store').returncode, 0)

    def test_uid_collision_is_skipped_without_logs_in_value(self):
        self.write_plist(self.node / "users/one.plist", {"uid": ["501"]})
        self.write_plist(self.node / "users/two.plist", {"uid": ["502"]})
        r = self.run_bash("choose_uid")
        self.assert_ok(r)
        self.assertEqual(r.stdout, "503\n")

    def test_uid_exhaustion_never_reuses_501(self):
        for uid in range(501, 600):
            self.write_plist(self.node / f"users/u{uid}.plist", {"uid": [str(uid)]})
        r = self.run_bash("choose_uid")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertIn("No free UID", r.stderr)

    def test_missing_uid_record_is_not_treated_as_available(self):
        self.write_plist(self.node / "users/broken.plist", {"name": ["broken"]})
        r = self.run_bash("choose_uid")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Cannot read", r.stderr)

    def test_volume_validation_returns_no_log_text_on_stdout(self):
        r = self.run_bash("validate_target && printf '%s' \"$TARGET\"")
        self.assert_ok(r)
        self.assertEqual(r.stdout, str(self.target))

    def test_system_volume_role_rejected(self):
        self.inventory["Containers"][0]["Volumes"][0]["Roles"] = ["System"]
        self.write_plist(self.root / "inventory.plist", self.inventory)
        r = self.run_bash("validate_target")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Data role", r.stderr)

    def test_role_is_matched_by_device_not_first_volume(self):
        self.inventory["Containers"][0]["Volumes"].insert(0, {
            "DeviceIdentifier": "disk8s1", "Roles": ["Data"],
        })
        self.write_plist(self.root / "inventory.plist", self.inventory)
        r = self.run_bash("validate_target && printf '%s' \"$DEVICE_ID\"")
        self.assert_ok(r)
        self.assertEqual(r.stdout, "disk9s1")

    def test_subdirectory_of_volume_rejected(self):
        self.volume_info["MountPoint"] = str(self.root)
        self.write_plist(self.root / "disk-info.plist", self.volume_info)
        r = self.run_bash("validate_target")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mount point", r.stderr)

    def test_readonly_volume_rejected(self):
        self.volume_info["Writable"] = False
        self.write_plist(self.root / "disk-info.plist", self.volume_info)
        r = self.run_bash("validate_target")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not writable", r.stderr)

    @unittest.skipUnless(Path('/System/Volumes/Data').is_dir(), 'macOS live Data guard')
    def test_live_volume_identity_rejected(self):
        self.write_plist(self.root / "live-info.plist", {"VolumeUUID": UUID})
        r = self.run_bash("validate_target")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("running system", r.stderr)

    def recovery_live_check(self, row, recovery=True):
        return self.run_bash(f'''
disk_info() {{ return 1; }}
require_recovery() {{ return {0 if recovery else 1}; }}
live_data_filesystem() {{ printf '%s\\n' {shlex.quote(row)}; }}
validate_live_data
''')

    def test_recovery_tmpfs_is_recognized_after_diskutil_failure(self):
        r = self.recovery_live_check('Filesystem 1024-blocks Used Available Capacity Mounted on\n'
                                     'tmpfs 2621440 172032 2449408 7% /System/Volumes/Data')
        self.assert_ok(r)
        self.assertIn('Recognized Recovery', r.stderr)
        self.assertEqual(r.stdout, '')
        self.assertEqual(self.capture(), self.before)

    def test_full_preview_continues_past_recovery_tmpfs(self):
        r = self.run_bash(f'''
disk_info() {{
    [ "$1" != /System/Volumes/Data ] || return 1
    /bin/cat {shlex.quote(str(self.root / 'disk-info.plist'))}
}}
require_recovery() {{ return 0; }}
live_data_filesystem() {{ printf '%s\\n' 'tmpfs 2621440 172032 2449408 7% /System/Volumes/Data'; }}
main plan --data-volume "$TARGET" --create-admin "$ADMIN"
''')
        self.assert_ok(r)
        self.assertIn('Plan: create admin', r.stderr)
        self.assertEqual(self.capture(), self.before)

    def test_tmpfs_exception_requires_recovery(self):
        r = self.recovery_live_check('tmpfs 10 1 9 10% /System/Volumes/Data', recovery=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('outside verified Recovery', r.stderr)

    def test_unknown_live_filesystem_is_rejected(self):
        for source in ['/dev/disk1s1', 'apfs', 'ramdisk', '']:
            with self.subTest(source=source):
                r = self.recovery_live_check(f'{source} 10 1 9 10% /System/Volumes/Data')
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('Unrecognized', r.stderr)

    def test_tmpfs_must_be_mounted_at_exact_live_data_path(self):
        r = self.recovery_live_check('tmpfs 10 1 9 10% /tmp')
        self.assertNotEqual(r.returncode, 0)

    def test_failed_recovery_filesystem_query_is_reported(self):
        r = self.run_bash('disk_info() { return 1; }; require_recovery() { return 0; }; '
                          'live_data_filesystem() { return 1; }; validate_live_data')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Cannot inspect', r.stderr)

    def test_missing_live_uuid_is_reported_not_treated_as_tmpfs(self):
        self.write_plist(self.root / 'live-info.plist', {})
        r = self.run_bash('require_recovery() { return 0; }; '
                          'live_data_filesystem() { echo "tmpfs 10 1 9 10% /System/Volumes/Data"; }; '
                          'validate_live_data')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Cannot read the running Data volume UUID', r.stderr)

    def test_status_error_is_unknown_not_unenrolled(self):
        r = self.run_bash("profiles_status() { printf 'permission denied'; return 7; }; running_status")
        self.assertEqual(r.returncode, 2)
        self.assertIn("UNKNOWN", r.stderr)
        self.assertNotIn("Not Enrolled", r.stdout + r.stderr)

    def test_invalid_names(self):
        for name in ["root", "../escape", "a b", "-flag", "$(id)", "a" * 32]:
            r = self.run_bash(f"valid_name {shlex.quote(name)}")
            self.assertNotEqual(r.returncode, 0, name)

    def test_verify_failure_has_nonzero_exit(self):
        r = self.run_bash("verify_local")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("CHECKS PASSED", r.stderr)

    def test_lock_is_exclusive(self):
        r = self.run_bash("acquire_lock && acquire_lock")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("lock exists", r.stderr)

    def test_failed_rollback_keeps_target_lock(self):
        r = self.run_bash("""
acquire_lock || exit 1
write_markers() { return 1; }
restore_snapshot() { return 1; }
apply_transaction
""", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((self.target / "private/var/db/mac-enrollment-lab.lock").is_dir())
        self.assertIn("ROLLBACK INCOMPLETE", r.stderr)

    def test_successful_rollback_releases_lock(self):
        r = self.run_bash("""
acquire_lock || exit 1
write_markers() { return 1; }
apply_transaction
""", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.target / "private/var/db/mac-enrollment-lab.lock").exists())
        self.assertEqual(self.capture(), self.before)

    def test_checksum_fallback(self):
        import hashlib
        r = self.run_bash('hash_shasum() { return 127; }; digest "$TARGET/private/etc/hosts"')
        self.assert_ok(r)
        self.assertEqual(r.stdout.strip(), hashlib.sha256(self.hosts.read_bytes()).hexdigest())

    def test_no_checksum_backend_prevents_mutations(self):
        r = self.run_bash("""
hash_shasum() { return 127; }
hash_openssl() { return 127; }
sha256_bash() { return 1; }
apply_transaction
""", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.capture(), self.before)
        self.assertNotIn("Changes staged", r.stderr)

    def test_apply_and_restore_without_openssl_or_shasum(self):
        r = self.run_bash("""
hash_shasum() { return 127; }
hash_openssl() { return 127; }
validate_fresh_install && apply_transaction && load_backup && restore_snapshot
""")
        self.assert_ok(r)
        self.assertEqual(self.capture(), self.before)

    def test_backup_volume_requirements(self):
        base = {
            "FilesystemType": "apfs", "GlobalPermissionsEnabled": True,
            "Writable": True, "MountPoint": "/Volumes/LABUSB",
            "VolumeUUID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        }
        cases = [({}, True), ({"GlobalPermissionsEnabled": False}, False),
                 ({"Writable": False}, False), ({"VolumeUUID": UUID}, False),
                 ({"VolumeUUID": ""}, False), ({"MountPoint": "/"}, False),
                 ({"FilesystemType": "exfat"}, False)]
        for changes, expected in cases:
            with self.subTest(changes=changes):
                self.write_plist(self.root / "disk-info.plist", dict(base, **changes))
                r = self.run_bash('validate_backup_parent "$SCRATCH"', real_backup_validation=True)
                self.assertEqual(r.returncode == 0, expected, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

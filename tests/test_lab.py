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
        self.write_plist(self.root / "live-info.plist", {"VolumeUUID": "other-live-volume"})
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
        self.assertIn("already complete", r.stderr)

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
        self.assertIn("Profile store", r.stderr)

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
apply_transaction
""", transaction_cleanup=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.capture(), self.before)
        self.assertNotIn("Changes staged", r.stderr)

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

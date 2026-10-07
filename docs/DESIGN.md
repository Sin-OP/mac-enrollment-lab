# Design and review notes

## Scope

The first version tests one mechanism: a fresh-install local admin plus setup/enrollment markers and three hosts entries. It does not remove organizational ownership records or claim to remove active management agents.

The source is one Bash 3.2-compatible file so Recovery does not need Python, Homebrew, Git, external libraries, or internet access. There is no `eval`, executable configuration, telemetry, downloaded payload, self-update path or daemon installation.

## Boundaries

- `diskutil ... -plist` and PlistBuddy supply structured disk metadata. Volume names are not used to infer APFS roles. The caller explicitly supplies the mount point.
- The live Data-volume UUID is rejected. Mutations also require root and a recognized Recovery boot-volume name. An unfamiliar Recovery environment is refused. If diskutil cannot inspect `/System/Volumes/Data`, the guard allows only a recognized Recovery boot with `df -Pk` confirming `tmpfs` mounted at that exact path. Other lookup failures remain fatal and now report a reason. The target itself still needs a writable APFS Data role and a valid UUID.
- All changed paths live beneath the selected Data volume. Each path component is checked for symlinks. Volume renaming and System/Data pairing are unnecessary because there are no System-volume writes.
- Account names are narrowly validated; existing account paths and home directories are refused. Existing UID records must be readable. Exhausting the bounded UID pool is a hard failure.
- Apple's documented `dscl -f ... localonly` node `/Local/Target` is used for offline Directory Services writes. That path, interactive password behavior, and account bootability still need device validation.
- The hosts change is staged in the same directory and renamed into place. Existing contents and copied metadata are preserved.
- The only domain entries are `deviceenrollment.apple.com`, `mdmenrollment.apple.com` and `iprofiles.apple.com`, with IPv4 and IPv6 entries. No entire IP ranges, update domains, activation domains, or vendor services are blocked.
- A private, new backup directory is required on another persistent APFS/HFS volume with ownership enforcement enabled. Missing volume identity or writability metadata is refused. Paths in the snapshot are reconstructed from a fixed list and a validated account name; metadata is never executed.
- Both the old file checksums and new file checksums are retained. Restore checks old-file integrity and new-file content drift before touching the target. Snapshot files are trusted local artifacts; checksums are corruption detection, not digital signatures.
- An exclusive directory lock prevents concurrent runs of this tool on the target. It is not a general operating-system lock.
- Checksums prefer `shasum`/`openssl` when available. Recovery environments without both use the embedded Bash 3.2 SHA-256 implementation. It hashes bytes, including NULs and high-bit bytes, using only shell builtins. If no method produces a digest, backup preparation stops before target changes. Digest mismatches remain failures.

## Observed profile-store layout

After a complete erase, activation and reinstall, the test device still created a profile store before account setup. v0.1.4-rc1 permits precisely five regular, nonsymlink files: zero-byte `ConfigProfiles.binary` and `Provisioning.binary`; one zero-byte dot marker named with ten hexadecimal characters; a nonempty `MCXPrivate.keychain`; and a readable `MDM_ComputerPrefs.plist` whose only dictionary key is `MDMServerHash` with a nonempty data value. Preferences are parsed by PlistBuddy, then its serialized XML is checked for that single-field structure. Extra keys and different value types fail. An absent or empty store remains accepted.

This is an empirical allowance for a disposable fresh-install experiment, not an Apple-documented enrollment detector. The keychain is opaque and not inspected. The tool explicitly reports enrollment status as UNKNOWN, preserves every profile-store file, and does not infer that management has been removed. The setup-completion marker must still be absent, FileVault must be off, and all account/volume/backup checks remain in force. Populated profile databases or any unrecognized store state stop the operation. No hardware apply has yet validated the new allowance.

## Failure behavior

Every intended mutation checks its return value. An apply failure after the completed snapshot invokes rollback from the EXIT trap. INT, HUP and TERM exit through that trap. There is no unconditional “bypass succeeded” banner; the strongest programmatic success claim is that local file checks passed.

Rollback is best effort, not a filesystem transaction. It cannot recover automatically from power loss, SIGKILL or a failed underlying disk. A failure can leave a partial snapshot or a stale target lock. Failed rollback or restore deliberately retains the lock. Preserve those artifacts and inspect them in Recovery. Never remove a lock while another instance could be running.

Restore is intentionally limited to an unchanged target and an empty newly created account home. It is useful before first reboot, or following an ordinary failed apply. It is not a migration/uninstallation system for an account already in use.

## Tests versus device evidence

The checksum fallback implements the unkeyed SHA-256 algorithm described in [FIPS 180-4](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf). It is not a signature or a NIST-validated cryptographic module. Tests compare known answers, 137 deterministic binary lengths around block/padding boundaries, all byte values, UTF-8, and both delivered scripts against Python hashlib. The fallback's subprocess PATH contains no external programs. Fixture apply/restore and launcher verification also run with the OpenSSL/shasum boundaries disabled.

`lib/sha256.sh` is the maintained source. Run `python3 scripts/bundle.py` after changes to embed it into both standalone scripts, pin the updated core checksum/version, and refresh the Pages copies. CI checks that these generated sections are synchronized. No Python is needed at runtime on the device.

Fixtures exercise target-role/identity rejection, UID collisions and exhaustion, path quoting and symlink guards, backup integrity, rollback, drift refusal, status-query errors, and preservation of hidden marker files. The tests replace only the platform boundaries inside the test process.

Tests do not establish that Apple's enrollment services honor these markers, that `dscl` creates a bootable account in a particular Recovery build, that Secure Token is provisioned, or that the hosts entries remain effective after an upgrade. Those are hardware questions, tracked in the testing protocol.

## Future changes

Add a feature only after a failing, reproducible device test identifies a need. In particular, adding broad network blocks, persistent repair daemons or active-management removal would change the tool's scope and require separate design and testing. Version compatibility must be supported by recorded evidence, not a version-number allowlist.

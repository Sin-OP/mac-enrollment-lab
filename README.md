# mac-enrollment-lab

An original, experimental Bash tool for testing local enrollment suppression on a **fresh macOS installation paused at Remote Management**. The initial hardware target is **macOS Sonoma 14.4**. No successful hardware run has been recorded yet.

This is an enrollment-suppression experiment, not a release from Apple Business/School Manager, an Activation Lock unlocker, or a tool for removing an already-installed MDM profile. Use on devices you own or are authorized to test.

## What the prototype does

From Recovery, on an explicitly selected APFS Data volume, it:

1. Checks the volume's role and identity, rejects the running system's Data volume, and validates the fresh-install state.
2. Saves the exact files it will change, including hidden enrollment markers, to a new private directory on another persistent volume.
3. Creates one administrator account through Apple's documented `dscl localonly` target node. The password is entered at Apple's prompt, not supplied in a command line or printed by this script.
4. Adds IPv4/IPv6 hosts entries for three enrollment-related domains and updates local setup/enrollment marker files.
5. Checks the resulting files. Any checked apply failure triggers an attempt to restore the original files before the script exits.

The CLI includes `plan`, `apply`, `verify`, `restore`, `volumes`, and `status`. Diagnostics go to stderr; values returned by helper functions stay on stdout.

It does not rename volumes, disable SIP, alter the sealed system volume, install a daemon, modify firewall rules, self-update, or contact a third-party service. There are no downloaded executables or runtime dependencies beyond macOS utilities. The network effects of the three hosts entries still need hardware testing.

## Get it onto the test device

For manual typing in **Recovery Terminal**, use the guided launcher:

```bash
curl -fL https://sin-op.github.io/mac-enrollment-lab/go2 -o /tmp/lab &&
bash /tmp/lab
```

Recovery builds without `openssl` or `shasum` use an embedded Bash-only SHA-256 fallback. The launcher downloads and verifies the pinned `v0.1.2-rc1` core, then presents numbered volume selections. Choose option 1 to preview the experiment. It requests `APPLY` before changes; options 2 and 3 verify or restore. An appropriate separate backup volume is still required. The HTTPS launcher is served from this repository's GitHub Pages site; its embedded checksum pins the core, not the launcher itself.

For the first trial, use [v0.1.2-rc1](https://github.com/Sin-OP/mac-enrollment-lab/releases/tag/v0.1.2-rc1). The [deployment guide](docs/DEPLOYMENT.md) includes direct download and checksum verification in Recovery Terminal, as well as USB transfer. Backup storage must have ownership enforcement enabled.

Download a specific Git commit or release on another computer, inspect the script, and copy the repository to an APFS-formatted USB drive. Keep that drive connected for the test. Avoid executing a changing branch directly over the network.

The commands below use `/Volumes/LABUSB/mac-enrollment-lab` as the repository location. Substitute your actual paths. Mount/unlock the target Data volume in Disk Utility first; this script does not guess, rename, or unlock it.

In **Recovery → Utilities → Terminal**:

```bash
cd /Volumes/LABUSB/mac-enrollment-lab
/bin/bash enrollment-lab.sh volumes
```

Identify the intended volume labeled with the **Data** role. Do not assume its name is `Macintosh HD - Data`.

```bash
/bin/bash enrollment-lab.sh plan \
  --data-volume "/Volumes/Macintosh HD - Data" \
  --create-admin labadmin
```

Review the target and plan. Then apply with a **new** backup directory on the USB drive:

```bash
/bin/bash enrollment-lab.sh apply \
  --data-volume "/Volumes/Macintosh HD - Data" \
  --create-admin labadmin \
  --backup-dir /Volumes/LABUSB/lab-backup-001
```

Choose a unique password when `dscl` prompts. The script has no default password. It will not reboot automatically.

```bash
/bin/bash enrollment-lab.sh verify \
  --data-volume "/Volumes/Macintosh HD - Data"
```

**A passed local-file check means only that the intended files are present.** Follow [the hardware test protocol](docs/TESTING.md) before describing enrollment suppression as working.

## Rollback

For an immediate rollback **before the first reboot or use of the new account**, remain in Recovery:

```bash
/bin/bash enrollment-lab.sh restore \
  --data-volume "/Volumes/Macintosh HD - Data" \
  --backup-dir /Volumes/LABUSB/lab-backup-001
```

Restore verifies the target UUID, backup checksums, and that managed file contents have not changed since apply. It also requires the new account's home directory to be empty. It restores file contents and copied metadata and removes only the empty home directory. It never recursively deletes the account's home.

After login, macOS can change account records and populate the home directory. Automated restore will then refuse instead of discarding those changes. For a disposable hardware test, use your lab's reimage procedure for a clean next trial.

An ordinary command failure, Ctrl+C, HUP, or TERM during apply triggers rollback. **Power loss, SIGKILL, storage failure, and a failed rollback cannot be made transactional by a shell script.** Retain the backup, stay in Recovery, and inspect the snapshot before further changes. A failed rollback/restore retains the target lock to prevent an immediate retry. Interrupted snapshots are deliberately not accepted by the normal restore command.

Backups contain private local configuration and account membership information. Keep them private; do not commit or attach them to a public issue.

## Compatibility and limits

| Environment | Status |
|---|---|
| Built-in macOS Bash 3.2 | Local syntax and isolated fixture tests passed |
| Sonoma 14.4, fresh install at Remote Management | Initial device test target; hardware result pending |
| Newer macOS versions | Experimental; no compatibility claim |
| Intel versus Apple silicon | Uses common macOS interfaces; both require separate hardware validation |
| Already-enrolled or completed installation | Refused by this version |
| FileVault-enabled target | Offline account creation refused; no Secure Token/volume ownership claim |
| Activation Lock, firmware/Recovery password | Not addressed |
| Server-side organizational release | Not performed |

The script checks APFS role metadata instead of localized volume names. It intentionally fails when required information is missing. The profile-store guard is conservative: a store containing files stops the operation, even if those files might be harmless. Report that refusal privately/redacted rather than weakening it on an unknown installation.

Apple documents renewed enrollment enforcement on registered Macs running macOS 14 or later. A desktop login, failed query, or local `MDM enrollment: No` result is not proof of permanent removal. The organization can [release a device](https://support.apple.com/guide/apple-business-manager/release-devices-axmec4d28461/web); that server-side action is outside this tool.

## Development

```bash
/bin/bash -n enrollment-lab.sh
python3 -m unittest discover -s tests -v
```

Python is needed only to run the tests on a development computer. The tool itself does not use it. Tests source the functions into a fixture process, replace the hardware/Directory Services boundaries, and write only to temporary directories. There is no production `--test-mode` flag that bypasses volume or Recovery checks.

GitHub Actions runs these checks on `macos-14` and `macos-latest`. These hosted-runner checks do **not** exercise Recovery or prove MDM bypass compatibility.

See [DESIGN.md](docs/DESIGN.md) for the implementation boundaries and [TESTING.md](docs/TESTING.md) for device evidence requirements.

## Prior art

This code was written from scratch after reviewing [assafdori/bypass-mdm](https://github.com/assafdori/bypass-mdm), [eudy97/MDM-bypass](https://github.com/eudy97/MDM-bypass), [mateussiqueira/unleash](https://github.com/mateussiqueira/unleash), and related scripts. The shared enrollment-marker/hosts technique is prior art. This implementation concentrates on explicit targets, narrow changes, error handling, and evidence rather than claiming a new exploit.

MIT licensed. Experimental software; keep hardware test results tied to exact commits and OS builds.

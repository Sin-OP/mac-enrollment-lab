# Deploy the next Recovery trial

Use prerelease **v0.1.10-rc1** for the next trial. It is a fixed test version, not a compatibility certification. Download it in **Recovery → Utilities → Terminal**, or copy the same release from a preparation computer onto an APFS USB drive.

## Short command for manual typing

```bash
curl -4fL https://sin-op.github.io/mac-enrollment-lab/go10 -o /tmp/l10 && /bin/bash /tmp/l10
```

The `&&` prevents launching if the first download fails. The launcher verifies the pinned core's SHA-256, provides a numbered menu, and offers numbered selections for mounted volumes. Option 1 runs a read-only preview and prints `PREVIEW PASSED` or `PREVIEW BLOCKED` with an exit code. After a passing preview, press Enter to stop with no installation changes. Type `Y` only if you want to choose a backup volume; the later `APPLY` prompt is still required before any target changes. A blank account name defaults to `labadmin`; passwords have no default.

Use option 3 for immediate rollback while the new account home is empty. A failed core operation is reported as a failure, and all core preflight checks remain in effect. Backup volumes must be mounted APFS/HFS volumes with ownership enabled. If no appropriate volume appears, mount it first in Disk Utility.

The HTTPS launcher is a small bootstrap served from `docs/go10` (also mirrored at `docs/go`) using GitHub Pages. It tries IPv4 first, then the standard network route if IPv4 DNS or connectivity fails. Both attempts have bounded retries and timeouts. It reports the curl exit code and a short hint for common DNS, HTTP, write, timeout and TLS failures, then checks the core checksum before running it. Its own trust comes from HTTPS and this GitHub account, not an independently verified launcher signature. The longer method below also remains available.

## Diagnose a blocked preview

The normal preview prints an `ERROR:` line and an exit status when a check fails; major target and fresh-install checks also print a blocked-stage code. If more context is needed, the diagnostic verifies the same pinned core and runs only the read-only `plan`. With no arguments, it asks you to select a mounted volume and enter the lab account name; Enter defaults to `labadmin`. You can also supply a Data-volume path and optional account name as arguments. It cannot dispatch apply or restore.

```bash
curl -4fL https://sin-op.github.io/mac-enrollment-lab/check -o /tmp/check && /bin/bash /tmp/check
```

The diagnostic labels the download and preview stages, prints the core's normal errors and exit code, and removes its temporary core copy when it exits. It does not enable Bash tracing, retain a trace log, or print plist values. Normal output can still include local volume paths and account names; review photos before sharing them.

| Blocked code | Check to inspect |
|---|---|
| `T01` | Selected target mount, volume identity, or APFS Data role |
| `T02` | Fresh-install state, requested account, or profile-store layout |
| `A00`–`A07` | Recovery and apply stages, including utility availability, backup preparation, account creation, file writes, and verification |
| `V01` | Local file verification |
| `R00`–`R01` | Recovery environment or backup integrity for restore |

The `ERROR:` line above a code is usually more specific. A blocked preview means no installation changes were made. For an apply failure, read the specific error and any rollback result before retrying; preflight failures occur before target changes and have no rollback to report.

If the preview reports unrecognized profile preferences, it also reports a value-free top-level type such as `array` or `dictionary with unsupported fields`. The separate read-only [store inspector](store2) can show key names and value types without printing values. It finds mounted Data volumes automatically:

```bash
curl -4fL https://sin-op.github.io/mac-enrollment-lab/store2 -o /tmp/store && bash /tmp/store
```

Send only the inspector's summary for review. A different layout remains an unknown enrollment state.

## Optional manual download when a checksum utility is available

Recovery must have an internet connection for the download. The tool itself needs no network connection to execute. Keep the device connected for the later behavioral test as described in TESTING.md.

Some Recovery builds have neither OpenSSL nor shasum. Use the short `go10` command above in that environment; it includes a Bash-only SHA-256 fallback. The longer block below assumes `awk` and at least one checksum utility are available. It downloads and verifies the script, then lists volumes.

```bash
lab_dir=$(mktemp -d /tmp/enrollment-lab.XXXXXXXX) &&
cd "$lab_dir" &&
curl -4fL https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.10-rc1/enrollment-lab.sh -o enrollment-lab.sh &&
curl -4fL https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.10-rc1/enrollment-lab.sh.sha256 -o enrollment-lab.sh.sha256 &&
(
  expected=$(awk '{print $1}' enrollment-lab.sh.sha256)
  actual=$(openssl dgst -sha256 enrollment-lab.sh 2>/dev/null | awk '{print $NF}')
  if [ "${#actual}" -ne 64 ]; then
    actual=$(shasum -a 256 enrollment-lab.sh 2>/dev/null | awk '{print $1}')
  fi
  [ "${#expected}" -eq 64 ] && [ "$actual" = "$expected" ] || {
    echo 'Checksum verification failed. Stop here.' >&2
    exit 1
  }
) &&
/bin/bash enrollment-lab.sh version &&
/bin/bash enrollment-lab.sh volumes
```

Stop on a download or checksum error. Checksums detect corruption; they are not a separate publisher signature. Record the release and commit from the release page in your test results.

## Select the target and backup storage

Identify and mount the intended **Data-role** volume. Names can differ. The sample below assumes it is `/Volumes/Macintosh HD - Data`.

```bash
/bin/bash enrollment-lab.sh plan \
  --data-volume "/Volumes/Macintosh HD - Data" \
  --create-admin labadmin
```

For `apply`, connect or mount a **separate persistent APFS/HFS volume** for backups. The script checks its filesystem, UUID, writability and ownership enforcement. A downloaded script in `/tmp` is fine, but `/tmp` is not suitable for a backup. The selected target Data volume and FAT/exFAT storage are not accepted as backup destinations.

For an already prepared backup volume named `LABUSB`, ownership can be enabled from Recovery with:

```bash
diskutil enableOwnership /Volumes/LABUSB
```

This changes the volume's ownership setting; it does not format it. On a normal preparation Mac, the command requires `sudo`. Substitute the actual backup volume, not the target installation.

After reviewing the plan, use a new backup directory:

```bash
/bin/bash enrollment-lab.sh apply \
  --data-volume "/Volumes/Macintosh HD - Data" \
  --create-admin labadmin \
  --backup-dir /Volumes/LABUSB/lab-backup-001
```

Enter a unique password at the prompt. Run the immediate rollback trial in [TESTING.md](TESTING.md) before the actual reboot trial. Rebooting can erase the downloaded `/tmp` copy; retain or re-download the same release for subsequent checks. Preserve the backup independently.

## Copy via USB instead

Download the release ZIP and `SHA256SUMS` on a preparation computer, verify the ZIP's hash, extract it, and copy the `mac-enrollment-lab` directory to a prepared APFS volume. Enable ownership enforcement on that volume. Run the same commands from that directory in Recovery Terminal.

Do not format an existing disk just to follow the sample names. The examples assume a suitable backup volume has already been prepared.

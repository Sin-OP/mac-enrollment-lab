# Deploy the first hardware test

Use prerelease **v0.1.4-rc1** for the first trial. It is a fixed test version, not a compatibility certification. Download it in **Recovery → Utilities → Terminal**, or copy the same release from a preparation computer onto an APFS USB drive.

## Short command for manual typing

```bash
curl -fL https://sin-op.github.io/mac-enrollment-lab/go4 -o /tmp/lab &&
bash /tmp/lab
```

The `&&` prevents launching if the download fails. Enter the second line when Terminal asks for the continuation. The launcher verifies the pinned core's SHA-256, provides a numbered menu, and offers numbered selections for mounted volumes. Option 1 runs the plan before asking for the exact confirmation `APPLY`. A blank account name defaults to `labadmin`; passwords still have no default.

Use option 3 for immediate rollback while the new account home is empty. A failed core operation is reported as a failure, and all core preflight checks remain in effect. Backup volumes must be mounted APFS/HFS volumes with ownership enabled. If no appropriate volume appears, mount it first in Disk Utility.

The HTTPS launcher is a small bootstrap served from `docs/go4` (also mirrored at `docs/go`) using GitHub Pages. It pins the core release and checksum. Its own trust comes from HTTPS and this GitHub account, not an independently verified launcher signature. The longer method below also remains available.

## Diagnose a silent preview failure

If the menu reports a failed preview without a reason, this diagnostic verifies
the same pinned core and runs only `plan` with Bash tracing. It defaults to
`/Volumes/Data` and the requested test account `epyon`; two optional arguments
can override those values. It cannot dispatch apply or restore.

```bash
curl -4fL https://sin-op.github.io/mac-enrollment-lab/check -o /tmp/check &&
bash /tmp/check
```

The diagnostic prints the last 40 trace lines and keeps the full log in its
private temporary directory until removed or Recovery restarts. It does not
upload the log. The trace can contain local paths, volume IDs and account names.

## Optional manual download when a checksum utility is available

Recovery must have an internet connection for the download. The tool itself needs no network connection to execute. Keep the device connected for the later behavioral test as described in TESTING.md.

Some Recovery builds have neither OpenSSL nor shasum. Use the short `go4` command above in that environment; it includes a Bash-only SHA-256 fallback. The longer block below is only for environments where at least one checksum utility is available. It downloads and verifies the script, then lists volumes.

```bash
lab_dir=$(mktemp -d /tmp/enrollment-lab.XXXXXXXX) &&
cd "$lab_dir" &&
curl -fL https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.4-rc1/enrollment-lab.sh -o enrollment-lab.sh &&
curl -fL https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.4-rc1/enrollment-lab.sh.sha256 -o enrollment-lab.sh.sha256 &&
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

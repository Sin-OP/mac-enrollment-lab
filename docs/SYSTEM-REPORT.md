# Standalone macOS system support report

`system-report.sh` is a Bash 3.2 diagnostic collector for normal macOS and Recovery. It writes a new report folder and makes no configuration changes. It does not invoke the enrollment experiment or infer management status. It can run independently of the core download and its preflight checks.

The versioned standalone download is [system-report-v1.0.0](https://github.com/Sin-OP/mac-enrollment-lab/releases/tag/system-report-v1.0.0). Its Recovery-device trial is pending. Validation includes 14 dedicated fixture tests and a successful local macOS collection with networking disabled. The repository's full 125-test suite passed locally.

## Run it in Recovery

```bash
curl -4fL https://sin-op.github.io/mac-enrollment-lab/report -o /tmp/r && bash /tmp/r
```

The first numbered prompt selects a mounted volume to inspect. Select `0` for system-only diagnostics. The second prompt selects where to create a new report folder. Select a persistent mounted drive to keep it through reboot; `0` saves under `/tmp`, which is temporary. The collector writes only its new report folder to the chosen destination. It does not format, mount, unlock, or change settings on any volume.

The HTTPS download is the standalone collector itself; it performs no second code download. As with the guided launcher, its trust comes from HTTPS and the repository account. `docs/report.sha256` records its SHA-256 for a preparation computer; a checksum fetched from the same publisher is integrity checking, not a separate signature. You can copy the reviewed `system-report.sh` to a USB volume and run it there instead.

For noninteractive collection:

```bash
bash system-report.sh --target "/Volumes/Macintosh HD - Data" --output-parent "/Volumes/LABUSB"
```

To omit network probes:

```bash
bash system-report.sh --target "/Volumes/Macintosh HD - Data" --no-network
```

Only report files are written. There is no automatic upload. A failed download does not execute the script because the launch command uses `&&`.

## What the folder contains

| File | Purpose |
|---|---|
| `summary.txt` | Concise counts and notable probe results, with failures and timeouts first |
| `report.txt` | Allowlisted hardware, OS, volume, storage, utility, and connectivity details |
| `checks.tsv` | One row per check with its ID, status, exit code, elapsed seconds, and description |

Reports include the running OS version/build, which is the Recovery OS when booted into Recovery. Separately, the collector reads version/build fields from directly accessible `SystemVersion.plist` files on mounted installations. It records each mount path and does not guess which System volume pairs with a Data volume.

Disk information includes device identifiers, filesystem type, read-only/locked/FileVault flags, SMART information when available, capacity, and a separate APFS role inventory. Human-readable disk output is filtered by an allowlist. Unrecognized formats are recorded as unknown. This information is diagnostic and is not a substitute for the core's structured validation.

Hardware collection includes model identifier, CPU description, architecture, and memory. It also queries SIP and authenticated-root status. Recovery often lacks some utilities or hardware information keys; those absences remain visible instead of stopping collection.

HTTPS HEAD probes contact GitHub, raw.githubusercontent.com, and Apple. GitHub is tested using IPv4 and the default route. The report includes response codes and DNS/connection/TLS timings. A received HTTP error still establishes that an HTTP response was received; it does not establish that a particular file exists. These checks send no report content and do not change DNS, proxy, certificate, or hosts settings.

## Interpret the results

| Status | Meaning |
|---|---|
| `OK` | The command completed successfully; this is not an overall system-health pass |
| `FAILED` | The command returned a nonzero status; the exact exit code is recorded |
| `TIMEOUT` | The collector terminated a command after its time limit |
| `OUTPUT_LIMIT` | A command exceeded the temporary output limit and exited with the corresponding signal |
| `UNAVAILABLE` | The executable was absent; the probe did not run |
| `UNKNOWN` | A command's data could not be interpreted or a required capability was unavailable |
| `SKIPPED` | Network probes were disabled, or the probe/time inventory budget was reached |

An output-limit failure may also appear as `FAILED` if a program catches its write error and returns its own exit code. Probe output is capped at 128 shell file-size units (at most 128 KiB on the supported Bash builds). Commands have a 12-second deadline; HTTPS requests additionally use curl's 10-second maximum. After a 180-second command budget, remaining probes are recorded as skipped. Report writing and parsing are outside that command budget.

Independent probes continue after a failure. The collector requires working `mktemp`, `mkdir`, and `rm` to prepare and clean up report storage. If it cannot write report files, it returns a failure and labels any retained folder incomplete. An interrupted report also remains incomplete.

## Contents and sharing

The final files omit serial numbers, hardware/volume UUIDs, network addresses, SSIDs, profile payloads, keychains, passwords, and raw system logs. They can contain mounted-volume paths/names and OS/model information; review them before sharing. There is no universal redaction claim for arbitrary future command-output changes.

Raw probe stdout is bounded and kept only in a private scratch directory under `/tmp`; stderr is not retained. Raw output is removed on normal completion and handled interrupts. As with any shell cleanup, power loss or SIGKILL can prevent removal. Only the three final files are written to the selected report destination.

The report can identify a failing probe and narrow down a platform, storage, or connectivity problem. It cannot promise the root cause of a different program's failure. Include the exact error and blocked-stage code from that program alongside this report when requesting help.

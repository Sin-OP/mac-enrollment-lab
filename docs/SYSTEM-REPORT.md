# Standalone macOS system support report

`system-report.sh` is a Bash 3.2 diagnostic collector for normal macOS and Recovery. It writes a new report folder and makes no configuration changes. It does not invoke the enrollment experiment or infer management status. It can run independently of the core download and its preflight checks.

The versioned standalone download is [system-report-v1.1.0](https://github.com/Sin-OP/mac-enrollment-lab/releases/tag/system-report-v1.1.0). Its Recovery-device trial is pending. Validation includes 25 dedicated fixture tests and a successful local macOS 26.6.2 / Apple silicon collection with networking disabled. See the [standalone compatibility workflow](https://github.com/Sin-OP/mac-enrollment-lab/actions/workflows/system-report.yml) for results tied to exact commits.

## Platform coverage

This is a macOS diagnostic collector, not a Windows or Linux program. Its coverage is separate from the enrollment experiment. A report that completes does not establish that another tool works on that OS or remains effective after updates.

| Environment | Evidence / limits |
|---|---|
| macOS 14, Apple silicon | Explicit hosted-runner job: fixture tests and a live read-only collection |
| macOS 15, Intel and Apple silicon | Separate architecture jobs: fixture tests and live collections |
| macOS 26, Intel and Apple silicon | Separate architecture jobs: fixture tests and live collections |
| GitHub's current `macos-latest` | Additional moving-target job; logs record the actual version, build, architecture, and Bash version |
| macOS Recovery, Intel or Apple silicon | Missing-utility and metadata fixtures; physical Recovery trials remain pending |
| Rosetta on Apple silicon | Architecture interpretation fixtures and a successful local macOS 26.6.2 collection from translated Bash |
| Older macOS | Best effort only; legacy version, filesystem, and skipped-probe fixtures are not full OS validation |
| Future macOS | No version ceiling in collection; unknown capabilities/formats stay visible; not certified |
| APFS and HFS+ metadata | Parser fixtures for both; no mounting, unlocking, role inference, or filesystem conversion |
| Windows / Linux | Collection rejected before a report folder is created |

GitHub lists [explicit Intel and arm64 runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners). The standalone workflow verifies the actual architecture instead of assuming `macos-latest` covers both. These are normally booted hosted machines, not Recovery environments.

The collector uses Bash 3.2 syntax and Apple-supplied commands; Python is needed only by the development tests. Missing commands do not terminate independent probes. Known pre-macOS-11 systems skip the authenticated-root query, since [signed system volumes begin with macOS 11](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/web). APFS role inventory is omitted on versions older than 10.13. Unknown/new versions attempt the queries and preserve the results instead of assuming compatibility.

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

Reports include the running OS version/build, which is the Recovery OS when booted into Recovery. `SYSTEM_VERSION_COMPAT=0` is set for version queries. If `sw_vers` is missing or yields unusable metadata, the collector tries the booted system's version plist. Separately, it reads version/build fields from directly accessible `SystemVersion.plist` files on mounted installations. Each plist field tries `PlistBuddy` then `plutil`; an unavailable reader and a successful fallback are both recorded. It records each mount path and does not guess which System volume pairs with a Data volume. A mount without a directly accessible version file is explicitly recorded as skipped; that is expected for many Data volumes.

Disk information includes device identifiers, filesystem type, read-only/locked/FileVault flags, SMART information when available, capacity, and a separate APFS role inventory. Human-readable disk output is filtered by an allowlist. Unrecognized formats are recorded as unknown. This information is diagnostic and is not a substitute for the core's structured validation.

Hardware collection includes model identifier, CPU description, process-visible architecture, hardware arm64 capability, translation flag, and memory. When needed, a kernel-reported CPU vendor provides additional Intel evidence; an absent arm64 key alone never means Intel. Hardware family is inferred from those signals, with conflicting or insufficient evidence kept unknown. The summary separates hardware family from process architecture, so an Intel process under Rosetta does not automatically imply Intel hardware. Apple documents [the translation flag](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment). It also queries SIP and authenticated-root status where applicable. Recovery often lacks some utilities or hardware information keys; those absences remain visible instead of stopping collection.

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
| `SKIPPED` | Disabled, known inapplicable, unavailable installation version file, or probe/time inventory budget reached |

An output-limit failure may also appear as `FAILED` if a program catches its write error and returns its own exit code. Probe output is capped at 128 shell file-size units (at most 128 KiB on the supported Bash builds). Commands have a 12-second deadline; HTTPS requests additionally use curl's 10-second maximum. After a 180-second command budget, remaining probes are recorded as skipped. Report writing and parsing are outside that command budget.

Independent probes continue after a failure. The collector requires working `mktemp`, `mkdir`, and `rm` to prepare and clean up report storage. If it cannot write report files, it returns a failure and labels any retained folder incomplete. An interrupted report also remains incomplete.

## Contents and sharing

The final files omit serial numbers, hardware/volume UUIDs, network addresses, SSIDs, profile payloads, keychains, passwords, and raw system logs. They can contain mounted-volume paths/names and OS/model information; review them before sharing. There is no universal redaction claim for arbitrary future command-output changes.

Raw probe stdout is bounded and kept only in a private scratch directory under `/tmp`; stderr is not retained. Raw output is removed on normal completion and handled interrupts. As with any shell cleanup, power loss or SIGKILL can prevent removal. Only the three final files are written to the selected report destination.

The report can identify a failing probe and narrow down a platform, storage, or connectivity problem. It cannot promise the root cause of a different program's failure. Include the exact error and blocked-stage code from that program alongside this report when requesting help.

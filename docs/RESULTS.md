# Validation results

## Hardware

### Second device diagnostic: 2026-10-10

On a different Mac in Recovery, the public `go5` launcher downloaded successfully (10,386 bytes) but stopped before fetching the core: `/usr/bin/uname` was absent, and the launcher misreported that macOS was required. No core command or installation change ran. v0.1.6-rc1 uses Bash's built-in `OSTYPE` for the launcher, diagnostic, and core platform checks. On retry, the mirrored `go5` launcher downloaded and verified v0.1.6-rc1, then its read-only plan selected `/Volumes/HDD - Data` and stopped at `Unrecognized profile preferences; enrollment status unknown.` No application was attempted. This second device's profile-preferences layout needs inspection before any validation-rule change. Its model and installed OS build are not yet recorded.

The first read-only inspector run reported no XML keys from both `/Volumes/HDD - Data` and `/Volumes/HDD`, despite PlistBuddy returning success. This was inconclusive about the plist's contents; the inspector's original output treated non-XML serialization as though the hash key were absent. A second run confirmed PlistBuddy returned XML for both volumes but the parser saw an unexpected dictionary wrapper, zero key tags, and no `MDMServerHash` key. A local empty-dictionary plist reproduces that output, but other root types could too. The revised inspector reports the top-level XML type without printing values. In parallel, v0.1.7-rc1 adds a narrow empty-dictionary allowance under the same five-file store checks. The device retest is pending; no installation has been attempted on this Mac.

### Current evidence: 2026-10-07

The user reported reaching the desktop without a forced enrollment prompt after applying the v0.1.5-rc1 trial. An authorized SSH audit then observed the following on one Mac15,11 (arm64), running macOS 14.8.9, build 23J631. This is the reinstalled OS, not the originally reported 14.4 build. Release source commit: `734dc3ecdac164cdbe9ae17d8e6607381ec20503`; the Recovery apply exit status was not independently captured over SSH.

| Check | Before additional restarts | After restart 1 | After restart 2 |
|---|---|---|---|
| `profiles status -type enrollment` | DEP: No; MDM: No; exit 0 | Same; exit 0 | Same; exit 0 |
| System configuration profiles | None reported | None reported | None reported |
| Hosts and three setup/enrollment marker hashes | Baseline recorded | Identical | Identical |
| Activation-record/found markers | Absent | Absent | Absent |
| SSH authentication | Passed | Passed | Passed |

The restarts were initiated over SSH; distinct kernel boot times confirmed both occurred. A console session belonging to the test account was observed after each. SSH state checks do not independently inspect every graphical prompt; the initial no-prompt desktop result is user-reported.

Additional observations: the account has admin membership, Secure Token enabled, and volume ownership. FileVault is off. SIP and authenticated root are enabled. The rollback snapshot state is `applied`; restore was not tested. The standard system resolver returns the configured IPv4/IPv6 hosts entries for all three domains. This does not prove every Apple component uses that resolution path. The bootstrap-token query declined because the device is not supervised/DEP enrolled; no bootstrap-token result is inferred.

Software Update successfully listed Safari 26.6.1 and macOS 27.0.1 (26A434). The audit did not request or install an update payload. Update listing is not proof of successful installation. The user chose further investigation before upgrading.

Still untested: 24 hours online, sleep/wake, network changes, updates/upgrades, FileVault enablement, Apple service sign-in, immediate rollback, erase/reinstall persistence, and organizational release. No claim of compatibility with all Sonoma or newer builds is made.

### Earlier diagnostic history

Recovery feedback, 2026-10-05: the launcher download completed on the test device, but neither `openssl` nor `shasum` was installed, so v0.1.1-rc1 stopped before executing the core. This is a confirmed compatibility defect, not a successful bypass trial. v0.1.2-rc1 adds an embedded Bash-only checksum fallback; the later device retry confirmed checksum verification succeeds.

Recovery feedback, 2026-10-06: the read-only trace identified a silent failure querying `/System/Volumes/Data` with diskutil. The same device reported that path as Recovery tmpfs via df. v0.1.3-rc1 recognizes that specific case while preserving the live macOS Data-volume check. No installation changes were made by the preview. Device retest of this fix is pending.

Recovery feedback, 2026-10-07: the user erased, activated and reinstalled macOS, then returned to Recovery before account setup. v0.1.3-rc1 recognized Recovery tmpfs and stopped on the nonempty profile store. Photos showed zero-byte ConfigProfiles.binary and Provisioning.binary, a zero-byte hexadecimal marker, a keychain, and a preferences dictionary containing only binary MDMServerHash data. That evidence does not establish completed enrollment. v0.1.4-rc1 adds a narrow experimental allowance for this layout while preserving all store files and reporting enrollment status UNKNOWN. Device apply test remains pending.

The earlier diagnostic failures below preceded the current partial hardware trial.

| Target | State | Result |
|---|---|---|
| macOS 14.4; model/chip not yet provided | Original Remote Management baseline | Erased/reinstalled before successful trial; no success on 14.4 established |
| macOS 14.8.9 (23J631); Mac15,11 / arm64 | Fresh reinstall, then trial account login | Initial user-reported desktop success; two SSH-verified restart checks passed |
| Newer macOS releases | Not tested | Unverified |

## Offline checks

The repository includes syntax checks and isolated fixture tests, also configured for GitHub Actions. These results establish behavior of the script against fixtures, not effectiveness against MDM on a real device.

Local development validation, 2026-10-05: Bash 3.2 syntax check passed; all 30 isolated tests passed. No bypass operation was run against a real installation during development.

Prerelease v0.1.1-rc1: Bash 3.2 syntax check passed; all 35 isolated tests passed locally, including checksum-backend failure, backup ownership enforcement, and retained locks after failed rollback. Hardware validation is still pending.

Prerelease v0.1.2-rc1: all 57 isolated tests passed locally on Bash 3.2, including known SHA-256 answers, binary/padding cases, downloaded-script integrity, and fixture backup/restore with both external checksum utilities unavailable. Device retest remains pending.

Prerelease v0.1.3-rc1: 66 isolated tests passed locally (65-test suite plus the additional full-preview regression). Tests reproduce a failed live-path diskutil query followed by verified Recovery tmpfs, and retain rejection of a matching live Data UUID, missing UUIDs, unknown filesystems and failed queries. Hardware retest remains pending.

Prerelease v0.1.4-rc1: all 75 isolated tests passed locally, including XML/binary preferences, strict schema rejection, populated/unknown store rejection, and preservation of every store file through fixture apply and restore.

Candidate v0.1.7-rc1: all 89 isolated tests passed locally, including XML/binary empty-dictionary preferences, rejection of arrays/extra keys/malformed preferences, and fixture apply/restore preserving the empty-dictionary store. The second device has not yet confirmed its root type or run this candidate.

Recovery feedback, 2026-10-07, follow-up: the filename was misread in the earlier photo as a ten-hex-character marker. The clearer listing shows `.fl8FC95EC6` with a lowercase L. v0.1.4-rc1 therefore rejected the unchanged store during the read-only preview. v0.1.5-rc1 corrects the prefix to `.fl` plus eight hexadecimal characters and includes the rejected filename in errors. At that point no hardware apply had succeeded; the later trial is recorded above.

Add exact commits, build numbers, trial stages and redacted results following [TESTING.md](TESTING.md). Do not replace “unverified” with “supported” on the basis of CI alone.

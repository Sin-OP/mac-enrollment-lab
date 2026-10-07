# Validation results

## Hardware

Recovery feedback, 2026-10-05: the launcher download completed on the test device, but neither `openssl` nor `shasum` was installed, so v0.1.1-rc1 stopped before executing the core. This is a confirmed compatibility defect, not a successful bypass trial. v0.1.2-rc1 adds an embedded Bash-only checksum fallback; the later device retry confirmed checksum verification succeeds.

Recovery feedback, 2026-10-06: the read-only trace identified a silent failure querying `/System/Volumes/Data` with diskutil. The same device reported that path as Recovery tmpfs via df. v0.1.3-rc1 recognizes that specific case while preserving the live macOS Data-volume check. No installation changes were made by the preview. Device retest of this fix is pending.

No completed hardware trials yet.

| Target | State | Result |
|---|---|---|
| macOS 14.4; model/chip not yet provided | Remote Management screen, not enrolled | Awaiting first lab run |
| Newer macOS releases | Not tested | Unverified |

## Offline checks

The repository includes syntax checks and isolated fixture tests, also configured for GitHub Actions. These results establish behavior of the script against fixtures, not effectiveness against MDM on a real device.

Local development validation, 2026-10-05: Bash 3.2 syntax check passed; all 30 isolated tests passed. No bypass operation was run against a real installation during development.

Prerelease v0.1.1-rc1: Bash 3.2 syntax check passed; all 35 isolated tests passed locally, including checksum-backend failure, backup ownership enforcement, and retained locks after failed rollback. Hardware validation is still pending.

Prerelease v0.1.2-rc1: all 57 isolated tests passed locally on Bash 3.2, including known SHA-256 answers, binary/padding cases, downloaded-script integrity, and fixture backup/restore with both external checksum utilities unavailable. Device retest remains pending.

Prerelease v0.1.3-rc1: 66 isolated tests passed locally (65-test suite plus the additional full-preview regression). Tests reproduce a failed live-path diskutil query followed by verified Recovery tmpfs, and retain rejection of a matching live Data UUID, missing UUIDs, unknown filesystems and failed queries. Hardware retest remains pending.

Add exact commits, build numbers, trial stages and redacted results following [TESTING.md](TESTING.md). Do not replace “unverified” with “supported” on the basis of CI alone.

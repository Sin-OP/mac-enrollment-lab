# Validation results

## Hardware

Recovery feedback, 2026-10-05: the launcher download completed on the test device, but neither `openssl` nor `shasum` was installed, so v0.1.1-rc1 stopped before executing the core. This is a confirmed compatibility defect, not a successful bypass trial. v0.1.2-rc1 adds an embedded Bash-only checksum fallback; device retest pending.

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

Add exact commits, build numbers, trial stages and redacted results following [TESTING.md](TESTING.md). Do not replace “unverified” with “supported” on the basis of CI alone.

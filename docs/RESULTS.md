# Validation results

## Hardware

No completed hardware trials yet.

| Target | State | Result |
|---|---|---|
| macOS 14.4; model/chip not yet provided | Remote Management screen, not enrolled | Awaiting first lab run |
| Newer macOS releases | Not tested | Unverified |

## Offline checks

The repository includes syntax checks and isolated fixture tests, also configured for GitHub Actions. These results establish behavior of the script against fixtures, not effectiveness against MDM on a real device.

Local development validation, 2026-10-05: Bash 3.2 syntax check passed; all 30 isolated tests passed. No bypass operation was run against a real installation during development.

Add exact commits, build numbers, trial stages and redacted results following [TESTING.md](TESTING.md). Do not replace “unverified” with “supported” on the basis of CI alone.

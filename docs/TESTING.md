# Hardware test protocol

The first desktop login and two subsequent restart checks are recorded for one Mac15,11 running macOS 14.8.9 (23J631). The originally reported 14.4 installation was erased and reinstalled before this trial. See [RESULTS.md](RESULTS.md) for the evidence and remaining gaps, and [UPDATE-VALIDATION.md](UPDATE-VALIDATION.md) before testing an update.

## Baseline and preparation

1. Use the designated disposable lab device. Keep any needed data separately backed up.
2. Record the tested Git commit, installed macOS version/build, architecture and model identifier. The Recovery OS build may differ from the installed OS; distinguish them.
3. Confirm that a clean, network-connected installation shows the Remote Management enrollment screen. If it does not, this is not a meaningful bypass test.
4. Confirm the device is not already enrolled and the test concerns enrollment, not Activation Lock.
5. Copy the reviewed checkout to persistent APFS storage, with room for a backup. Keep the backup and any organization/device identifiers out of the public repository.
6. Boot Recovery and mount the intended Data volume. Run `plan` and inspect the selected path/device. A refused preflight is a test result; do not work around it without understanding the cause.

## Trial A: apply and immediate rollback

1. Run `apply` with a unique new lab account and unused backup directory.
2. Record exit status immediately (`echo $?`). A nonzero exit is a failure even if earlier steps printed progress.
3. Run `verify`; record its exit status. This tests local files, not enrollment effectiveness.
4. Before reboot, run `restore` with the same backup. It should return zero and remove the empty new home directory.
5. Confirm the original enrollment screen still appears after reboot with the original network available. This trial validates reversibility, not suppression.

## Trial B: actual device behavior

Start from a fresh baseline again, using a new backup directory.

1. Run `plan`, `apply`, and `verify` from Recovery.
2. Reboot manually, keeping the test network available. Record whether the new account can sign in and whether Remote Management appears.
3. In the running macOS installation, run `sudo /bin/bash /path/to/enrollment-lab.sh status`. Record the output and exit status. A failed query is **UNKNOWN**, never “not enrolled.”
4. Reboot twice and repeat the checks.
5. Leave the device network-connected for at least 24 hours and check again. Apple's documented eight-hour deferral makes an immediate desktop login weak evidence by itself. Do not run an enrollment-renewal command during this observation.
6. Check App Store access, software-update availability and any Apple services needed by the lab. Record unintended network effects. Do not claim these passed merely because the desktop works.
7. Record the result as **initial setup suppression**, **survived two reboots**, and **survived 24 hours**, separately. None of those demonstrates organizational release or survival of an erase.

Do not put personal data on the temporary account. The script does not provision Secure Token, bootstrap token or volume ownership. FileVault activation, startup-security changes, and migration are outside the first trial.

## Newer versions

Validate each newer macOS build as its own trial with a fresh installation and exact commit recorded. An in-place upgrade is a different experiment; label it separately. A passing shell test on a GitHub-hosted newer macOS runner is not a Recovery or enrollment test.

## Public result template

Copy this into an issue or a reviewed entry in `docs/RESULTS.md`:

```text
Commit:
Mac model identifier / chip (no serial number):
Installed macOS version and build:
Recovery OS version and build:
Baseline: Remote Management visible with network? yes/no
FileVault on target: off/on/unknown
Plan: pass/refused + redacted reason
Apply exit status:
Local verification exit status:
Immediate rollback trial: pass/fail/not tested
First login: pass/fail
Running-OS enrollment status query: result + exit status
After two reboots: pass/fail/not tested
After 24h online: pass/fail/not tested
Apple services checked and result:
Unexpected behavior:
```

Never include a serial number, hardware UUID, password, organization name, enrollment URL, credential, backup snapshot, or unredacted screenshot in a public issue.

Reference: [Apple's Automated Device Enrollment documentation](https://support.apple.com/guide/deployment/automated-device-enrollment-management-dep73069dd57/web).

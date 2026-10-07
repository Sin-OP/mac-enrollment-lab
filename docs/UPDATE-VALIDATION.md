# Update validation

## What is established

On 2026-10-07, one Mac15,11 running macOS 14.8.9 (23J631) retained its tracked local state and reported no current enrollment through two additional restarts. No update has been installed during testing. Detailed evidence is in [RESULTS.md](RESULTS.md).

## What could change

The following are risks inferred from this implementation, not observed update failures:

| Dependency | Possible change | How to detect it |
|---|---|---|
| Local hosts entries | File rewritten, resolver behavior changed, or enrollment uses other endpoints | Compare file and system resolver results; separately query actual enrollment |
| Setup/enrollment markers | Files regenerated or their meaning changed | Compare marker presence and hashes; observe login and enrollment behavior |
| Local account | Permissions, Secure Token, or volume ownership change | Check account membership, token status, and ownership before/after |
| Enrollment behavior | Delayed enforcement or new checks despite unchanged files | Repeat status queries and observe the GUI while online |
| Recovery rollback | Backup no longer matches current account/home or updated OS | Do not treat the immediate pre-login snapshot as an OS downgrade mechanism |

The script has no service that rewrites files after boot. Adding one without a reproducible failure would conceal evidence and could race macOS's own state updates. An observation-only before/after checker is the preferred next tooling improvement. File immutability, disabling SIP, and blocking all updates are not part of this experiment.

## Before choosing an update

1. Record the exact installed and proposed builds. Treat app updates, minor macOS updates, and major upgrades as separate trials. A Safari update does not validate a macOS upgrade.
2. Complete the online observation trial first. Apple's documented macOS 14+ enrollment enforcement can appear after initial setup, with a one-time eight-hour deferral. Twenty-four hours without a prompt remains bounded evidence, not a universal guarantee. [Apple enrollment documentation](https://support.apple.com/guide/deployment/automated-device-enrollment-management-dep73069dd57/web).
3. Keep a reviewed copy of the tested release and the original snapshot. If preserving the post-login system matters, make a separate current backup. The lab's automatic restore deliberately rejects a populated new home or changed managed files; an APFS volume on the same disk is not protection against disk loss or an erase of the container.
4. Check Secure Token and volume ownership. The test account had both. Apple documents volume ownership as necessary to authorize macOS updates/upgrades on Apple silicon. [Apple volume-ownership documentation](https://support.apple.com/guide/deployment/use-secure-and-bootstrap-tokens-dep24dbdcf9e/web).
5. Use external power and retain local access for any selected update. Do not depend on SSH being available throughout installation.

## Capture and compare

Capture the following privately before and after each chosen update, then again after two restarts:

- OS version/build, model identifier, and kernel boot time; omit serial numbers.
- Enrollment query output **and exit status** (`sudo profiles status -type enrollment`); failed queries mean UNKNOWN.
- System profile listing (`sudo profiles list -type configuration`); redact identifiers before publication.
- SHA-256 of `/etc/hosts`, `/var/db/.AppleSetupDone`, and the two lab markers in `/var/db/ConfigurationProfiles/Settings`.
- Presence or absence of activation-record/found markers, plus actual login-screen behavior.
- Resolver results for the three configured domains, account admin membership, Secure Token, and volume ownership.

The read-only [live audit script](../scripts/live-audit.sh) captures most of these without writing to the test Mac. From a trusted preparation computer with authorized SSH access:

```bash
ssh TESTUSER@TESTHOST /bin/bash -s < scripts/live-audit.sh > before-update.txt
```

Run it again after the event, save the output privately, and compare the two files. Each enrollment query includes its exit status; a failed query is UNKNOWN. The script does not query volume ownership or inspect the graphical screen, so record those separately. Do not publish raw audit output until it has been reviewed for device and organization identifiers.

Do not run enrollment renewal as a diagnostic. Do not silently reapply changes before collecting a failing result: that would erase the distinction between surviving an update and repairing after one. If behavior changes, retain the evidence and stop the update trial before deciding on a code change.

## Limits

Unchanged files do not establish unchanged OS behavior. A passing tested build does not establish survival of future builds, an erase, or reassignment. Local suppression does not release the device from the organization's Apple enrollment inventory. The documented administrative release process is separate. [Apple device-release documentation](https://support.apple.com/guide/business/release-devices-axmec4d28461/web).

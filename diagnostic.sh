# Bundled after the launcher's verified-download helpers by scripts/bundle.py.
# This entry point invokes only the read-only plan command, never apply/restore.
# Do not enable Bash xtrace here: variable assignments can contain plist values.
diagnostic_plan() {
    local rc=0
    say 'Diagnostic stage 2/2: read-only core preview.'
    /bin/bash "$CORE" plan --data-volume "$1" --create-admin "$2" || rc=$?
    if [ "$rc" -eq 0 ]; then
        say 'PREVIEW PASSED (exit 0). No installation changes were made.'
    else
        say "PREVIEW BLOCKED (exit $rc). No installation changes were made."
    fi
    return "$rc"
}

diagnostic_choose_target() {
    local -a choices=()
    local path answer index=0
    for path in /Volumes/*; do
        [ -d "$path" ] && [ ! -L "$path" ] || continue
        choices[${#choices[@]}]=$path
    done
    [ "${#choices[@]}" -gt 0 ] || { say 'No mounted volumes found under /Volumes.'; return 2; }
    say 'Select the mounted installation Data volume (the core will validate its role):'
    for path in "${choices[@]}"; do
        index=$((index + 1))
        say "  $index) $path"
    done
    while true; do
        say 'Enter a number, or q to cancel:'
        reply answer || return 3
        case "$answer" in q|Q) return 1 ;; esac
        if [[ "$answer" =~ ^[1-9][0-9]{0,3}$ ]] && [ "$answer" -le "${#choices[@]}" ]; then
            printf '%s\n' "${choices[$((answer - 1))]}"
            return 0
        fi
        say 'Invalid selection.'
    done
}

diagnostic_cleanup() {
    local rc=$?
    trap - EXIT INT TERM HUP
    if [ -n "$LAB_TMP" ] && [ -d "$LAB_TMP" ]; then /bin/rm -rf "$LAB_TMP"; fi
    exit "$rc"
}

diagnostic_main() {
    [ "$#" -le 2 ] || { say 'Usage: check [Data-volume-path [account-name]]'; return 2; }
    launcher_is_macos || { say 'This check requires macOS.'; return 1; }
    umask 077
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin
    local target admin rc
    if [ "$#" -eq 0 ]; then
        [ -t 0 ] && [ -t 1 ] || { say 'Supply a Data-volume path when not using an interactive Terminal.'; return 2; }
        target=$(diagnostic_choose_target) || {
            rc=$?
            [ "$rc" -eq 1 ] && { say 'Diagnostic cancelled before preview.'; return 0; }
            say "Diagnostic could not select a target (exit $rc)."
            return "$rc"
        }
        say 'Lab account name (Enter for labadmin):'
        reply admin || { say 'Diagnostic stopped: could not read the account name.'; return 1; }
        admin=${admin:-labadmin}
    else
        target=$1
        admin=${2:-labadmin}
    fi
    LAB_TMP=$(/usr/bin/mktemp -d /tmp/enrollment-check.XXXXXXXX) || {
        say 'Cannot create temporary storage under /tmp in Recovery.'
        return 1
    }
    trap diagnostic_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    CORE="$LAB_TMP/core.sh"
    say 'Read-only diagnostic: no account creation or installation changes.'
    say 'Diagnostic stage 1/2: download and verify fixed core.'
    download_verified_core || { say 'Diagnostic stopped before preview. No installation changes were made.'; return 1; }
    diagnostic_plan "$target" "$admin"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then diagnostic_main "$@"; fi

# Bundled after the launcher's verified-download helpers by scripts/bundle.py.
# This entry point invokes only the read-only plan command, never apply/restore.
diagnostic_plan() {
    local rc=0
    PS4='+ line ${LINENO}: ' /bin/bash -x "$CORE" plan \
        --data-volume "$1" --create-admin "$2" > "$LAB_TMP/preview.log" 2>&1 || rc=$?
    say "Read-only preview exit code: $rc"
    say 'Last 40 trace lines (installation unchanged by this preview):'
    /usr/bin/tail -n 40 "$LAB_TMP/preview.log"
    say "Full trace: $LAB_TMP/preview.log"
    return "$rc"
}

diagnostic_main() {
    [ "$#" -le 2 ] || { say 'Usage: check [Data-volume-path [account-name]]'; return 2; }
    launcher_is_macos || { say 'This check requires macOS.'; return 1; }
    umask 077
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin
    LAB_TMP=$(/usr/bin/mktemp -d /tmp/enrollment-check.XXXXXXXX) || return 1
    CORE="$LAB_TMP/core.sh"
    say 'Read-only diagnostic: no account creation or installation changes.'
    download_verified_core || return 1
    diagnostic_plan "${1:-/Volumes/Data}" "${2:-epyon}"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then diagnostic_main "$@"; fi

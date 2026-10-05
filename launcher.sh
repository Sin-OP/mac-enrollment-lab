#!/bin/bash
# Interactive download launcher. The core release and checksum are fixed.
CORE_VERSION=0.1.1-rc1
CORE_URL=https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.1-rc1/enrollment-lab.sh
CORE_SHA=1b880d067ac2cb8e70d4d9d4f3f0d5b010894df47ec2289b323331c94d041c3f
LAB_TMP=''
CORE=''
CHOICES=()

say() { printf '%s\n' "$*" >&2; }
reply() { IFS= read -r "$1" </dev/tty; }
fetch_core() { /usr/bin/curl -fL --connect-timeout 15 --max-time 120 "$CORE_URL" -o "$CORE"; }
core_hash() {
    local output hash
    if output=$(/usr/bin/openssl dgst -sha256 "$CORE" 2>/dev/null); then
        hash=${output##* }
        if [[ "$hash" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$hash"; return 0; fi
    fi
    if output=$(/usr/bin/shasum -a 256 "$CORE" 2>/dev/null); then
        hash=${output%% *}
        if [[ "$hash" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$hash"; return 0; fi
    fi
    return 1
}

download_verified_core() {
    say "Downloading fixed core release $CORE_VERSION..."
    fetch_core || { say 'Download failed. Nothing will run.'; return 1; }
    local hash
    hash=$(core_hash) || { say 'Cannot verify SHA-256. Stopping.'; return 1; }
    [ "$hash" = "$CORE_SHA" ] || { say 'Checksum mismatch. Nothing will run.'; return 1; }
    /bin/bash -n "$CORE" || return 1
    say 'Checksum verified.'
}

run_core() { /bin/bash "$CORE" "$@"; }

collect_volumes() {
    CHOICES=()
    local path
    for path in /Volumes/*; do
        [ -d "$path" ] && [ ! -L "$path" ] || continue
        CHOICES[${#CHOICES[@]}]=$path
    done
}

# UI text goes to stderr; the selected path is the only stdout value.
choose() {
    local title=$1 index=0 answer
    [ "${#CHOICES[@]}" -gt 0 ] || { say 'No matching mounted volumes or backups found.'; return 1; }
    say "$title"
    for answer in "${CHOICES[@]}"; do
        index=$((index + 1))
        say "  $index) $answer"
    done
    while true; do
        say 'Enter a number, or q to cancel:'
        reply answer || return 1
        case "$answer" in q|Q) return 1 ;; esac
        if [[ "$answer" =~ ^[1-9][0-9]{0,3}$ ]] && [ "$answer" -le "${#CHOICES[@]}" ]; then
            printf '%s\n' "${CHOICES[$((answer - 1))]}"
            return 0
        fi
        say 'Invalid selection.'
    done
}

choose_target() {
    collect_volumes
    choose 'Select the installation’s mounted Data volume (the core will validate its role):'
}

choose_backup() {
    local target=$1 selected
    collect_volumes
    selected=$(choose 'Select the separate backup volume (APFS/HFS, ownership enabled):') || return 1
    [ "$selected" != "$target" ] || { say 'The target cannot also be the backup volume.'; return 1; }
    printf '%s\n' "$selected/enrollment-lab-backup-$(/bin/date +%Y%m%d-%H%M%S)-$$"
}

find_backups() {
    CHOICES=()
    local path
    for path in /Volumes/*/enrollment-lab-backup-* /Volumes/*/lab-backup-*; do
        [ -d "$path" ] && [ ! -L "$path" ] || continue
        [ -f "$path/format" ] || continue
        CHOICES[${#CHOICES[@]}]=$path
    done
}

guided_apply() {
    local target admin backup answer
    target=$(choose_target) || return 1
    say 'New lab account name (Enter for labadmin):'
    reply admin || return 1
    admin=${admin:-labadmin}
    run_core plan --data-volume "$target" --create-admin "$admin" || return 1
    backup=$(choose_backup "$target") || return 1
    say "Target: $target"
    say "New account: $admin"
    say "Backup: $backup"
    say 'Type APPLY to make these changes, or press Enter to cancel:'
    reply answer || return 1
    [ "$answer" = APPLY ] || { say 'Cancelled.'; return 1; }
    run_core apply --data-volume "$target" --create-admin "$admin" --backup-dir "$backup"
}

guided_verify() {
    local target
    target=$(choose_target) || return 1
    run_core verify --data-volume "$target"
}

guided_restore() {
    local target backup answer
    target=$(choose_target) || return 1
    find_backups
    backup=$(choose 'Select the immediate rollback snapshot:') || return 1
    say "Restore target: $target"
    say "Snapshot: $backup"
    say 'Type RESTORE to request rollback, or press Enter to cancel:'
    reply answer || return 1
    [ "$answer" = RESTORE ] || { say 'Cancelled.'; return 1; }
    run_core restore --data-volume "$target" --backup-dir "$backup"
}

launcher_cleanup() {
    local rc=$?
    trap - EXIT INT TERM HUP
    if [ -n "$LAB_TMP" ] && [ -d "$LAB_TMP" ]; then /bin/rm -rf "$LAB_TMP"; fi
    exit "$rc"
}

launcher_main() {
    set -o pipefail
    umask 077
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin
    [ "$(/usr/bin/uname -s)" = Darwin ] || { say 'This launcher requires macOS.'; return 1; }
    [ -t 0 ] && [ -t 1 ] || { say 'Run from an interactive Terminal.'; return 1; }
    LAB_TMP=$(/usr/bin/mktemp -d /tmp/enrollment-lab-menu.XXXXXXXX) || return 1
    trap launcher_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    CORE="$LAB_TMP/enrollment-lab.sh"
    download_verified_core || return 1
    say "Enrollment Lab — guided launcher for $CORE_VERSION"
    say 'Hardware effectiveness remains unverified. Apply and restore require Recovery.'
    local action
    while true; do
        say ''
        say '1) Preview and apply fresh-install experiment'
        say '2) Verify local file changes'
        say '3) Restore immediate backup (before first login)'
        say '4) Show mounted APFS volumes'
        say '5) Query running macOS enrollment status'
        say 'q) Quit'
        reply action || return 1
        case "$action" in
            1) guided_apply || say 'Operation cancelled or failed; see the message above.' ;;
            2) guided_verify || say 'Local verification did not pass.' ;;
            3) guided_restore || say 'Restore cancelled or failed; retain the backup.' ;;
            4) run_core volumes || say 'Volume listing failed.' ;;
            5) run_core status || say 'Status query failed; result is unknown.' ;;
            q|Q) return 0 ;;
            *) say 'Choose 1–5 or q.' ;;
        esac
    done
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then launcher_main "$@"; fi

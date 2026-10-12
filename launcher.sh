#!/bin/bash
# Interactive download launcher. The core release and checksum are fixed.
CORE_VERSION=0.1.8-rc1
CORE_URL=https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v0.1.8-rc1/enrollment-lab.sh
CORE_SHA=deee18f3539078533ba9f0a897c0554af540802b6ccd7c04105ac0995e63024f
LAB_TMP=''
CORE=''
CHOICES=()
# BEGIN EMBEDDED SHA256
# SHA-256 file checksum using only Bash 3.2 builtins. No Perl, Python, OpenSSL,
# od, awk or external program is needed. Embedded into both delivered scripts.
# Implements the unkeyed algorithm in FIPS 180-4 sections 4–6, not a signature.
# This implementation is not a NIST-validated cryptographic module.
sha256_bash() (
    local LC_ALL=C
    export LC_ALL
    [ "$#" -eq 1 ] && [ -f "$1" ] && [ -r "$1" ] || return 1
    # Supported macOS Bash builds use 64-bit arithmetic; refuse narrower builds.
    [ "$((0xffffffff >> 31))" -eq 1 ] || return 1
    local -a h k w
    h=(0x6a09e667 0xbb67ae85 0x3c6ef372 0xa54ff53a
       0x510e527f 0x9b05688c 0x1f83d9ab 0x5be0cd19)
    k=(
        0x428a2f98 0x71374491 0xb5c0fbcf 0xe9b5dba5 0x3956c25b 0x59f111f1 0x923f82a4 0xab1c5ed5
        0xd807aa98 0x12835b01 0x243185be 0x550c7dc3 0x72be5d74 0x80deb1fe 0x9bdc06a7 0xc19bf174
        0xe49b69c1 0xefbe4786 0x0fc19dc6 0x240ca1cc 0x2de92c6f 0x4a7484aa 0x5cb0a9dc 0x76f988da
        0x983e5152 0xa831c66d 0xb00327c8 0xbf597fc7 0xc6e00bf3 0xd5a79147 0x06ca6351 0x14292967
        0x27b70a85 0x2e1b2138 0x4d2c6dfc 0x53380d13 0x650a7354 0x766a0abb 0x81c2c92e 0x92722c85
        0xa2bfe8a1 0xa81a664b 0xc24b8b70 0xc76c51a3 0xd192e819 0xd6990624 0xf40e3585 0x106aa070
        0x19a4c116 0x1e376c08 0x2748774c 0x34b0bcb5 0x391c0cb3 0x4ed8aa4a 0x5b9cca4f 0x682e6ff3
        0x748f82ee 0x78a5636f 0x84c87814 0x8cc70208 0x90befffa 0xa4506ceb 0xbef9a3f7 0xc67178f2
    )
    w=(0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0)
    local position=0 length=0 byte value shift bits

    # Nested helpers share the function's local arrays through Bash dynamic scope.
    # The enclosing subshell prevents helpers, locale and arrays leaking out.
    _sha256_block() {
        local t x y s0 s1 a b c d e f g z t1 t2
        for ((t=16; t<64; t++)); do
            x=${w[t-15]}; y=${w[t-2]}
            s0=$(( ((x >> 7 | x << 25) ^ (x >> 18 | x << 14) ^ (x >> 3)) & 0xffffffff ))
            s1=$(( ((y >> 17 | y << 15) ^ (y >> 19 | y << 13) ^ (y >> 10)) & 0xffffffff ))
            w[t]=$(( (w[t-16] + s0 + w[t-7] + s1) & 0xffffffff ))
        done
        a=${h[0]}; b=${h[1]}; c=${h[2]}; d=${h[3]}
        e=${h[4]}; f=${h[5]}; g=${h[6]}; z=${h[7]}
        for ((t=0; t<64; t++)); do
            s1=$(( ((e >> 6 | e << 26) ^ (e >> 11 | e << 21) ^ (e >> 25 | e << 7)) & 0xffffffff ))
            t1=$(( (z + s1 + ((e & f) ^ (~e & g)) + k[t] + w[t]) & 0xffffffff ))
            s0=$(( ((a >> 2 | a << 30) ^ (a >> 13 | a << 19) ^ (a >> 22 | a << 10)) & 0xffffffff ))
            t2=$(( (s0 + ((a & b) ^ (a & c) ^ (b & c))) & 0xffffffff ))
            z=$g; g=$f; f=$e; e=$(( (d + t1) & 0xffffffff ))
            d=$c; c=$b; b=$a; a=$(( (t1 + t2) & 0xffffffff ))
        done
        h[0]=$(( (h[0] + a) & 0xffffffff )); h[1]=$(( (h[1] + b) & 0xffffffff ))
        h[2]=$(( (h[2] + c) & 0xffffffff )); h[3]=$(( (h[3] + d) & 0xffffffff ))
        h[4]=$(( (h[4] + e) & 0xffffffff )); h[5]=$(( (h[5] + f) & 0xffffffff ))
        h[6]=$(( (h[6] + g) & 0xffffffff )); h[7]=$(( (h[7] + z) & 0xffffffff ))
        w=(0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0)
        position=0
    }
    _sha256_byte() {
        w[position/4]=$(( w[position/4] | ($1 << (24 - (position % 4) * 8)) ))
        position=$((position + 1))
        if [ "$position" -eq 64 ]; then _sha256_block; fi
    }

    # A NUL delimiter with -n 1 preserves newlines; an empty successful read is
    # one NUL byte. LC_ALL=C makes each read consume one byte, including UTF-8.
    while IFS= read -r -d '' -n 1 byte; do
        if [ -z "$byte" ]; then value=0; else printf -v value '%d' "'$byte" || return 1; fi
        # Apple Bash 3.2 printf can return signed values for bytes 128–255.
        _sha256_byte "$((value & 255))"
        length=$((length + 1))
    done < "$1"
    bits=$((length * 8))
    _sha256_byte 128
    while [ "$position" -ne 56 ]; do _sha256_byte 0; done
    for ((shift=56; shift>=0; shift-=8)); do _sha256_byte "$(( (bits >> shift) & 255 ))"; done
    printf '%08x%08x%08x%08x%08x%08x%08x%08x\n' "${h[@]}"
)
# END EMBEDDED SHA256

say() { printf '%s\n' "$*" >&2; }
reply() { IFS= read -r "$1" </dev/tty; }
launcher_curl() { /usr/bin/curl "$@"; }
fetch_core() {
    local rc
    if launcher_curl -4fL --connect-timeout 12 --max-time 45 \
        --retry 1 --retry-delay 2 --retry-max-time 90 "$CORE_URL" -o "$CORE"; then
        return 0
    else
        rc=$?
    fi
    case "$rc" in
        6|7|28)
            say 'IPv4 route unavailable; trying the standard network route.'
            /bin/rm -f "$CORE" || return 23
            launcher_curl -fL --connect-timeout 12 --max-time 45 \
                --retry 1 --retry-delay 2 --retry-max-time 90 "$CORE_URL" -o "$CORE"
            ;;
        *) return "$rc" ;;
    esac
}
explain_curl_error() {
    case "$1" in
        6) say 'DNS lookup failed. Check the network connection and host name.' ;;
        7) say 'Could not connect to the download host. Check the network connection.' ;;
        22) say 'The release URL returned an HTTP error. Check that this version is published.' ;;
        23) say 'Could not write the download. Check that temporary storage is writable and has space.' ;;
        28) say 'The download timed out. Check the connection and try again.' ;;
        35|60) say 'TLS verification or negotiation failed. Check the Mac date and network trust.' ;;
        *) say 'The download did not complete. Check the curl error above.' ;;
    esac
}
launcher_openssl() { /usr/bin/openssl dgst -sha256 "$CORE"; }
launcher_shasum() { /usr/bin/shasum -a 256 "$CORE"; }
core_hash() {
    local output hash
    if output=$(launcher_openssl 2>/dev/null); then
        hash=${output##* }
        if [[ "$hash" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$hash"; return 0; fi
    fi
    if output=$(launcher_shasum 2>/dev/null); then
        hash=${output%% *}
        if [[ "$hash" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$hash"; return 0; fi
    fi
    say 'Using built-in Bash SHA-256 for Recovery; this may take a moment...'
    sha256_bash "$CORE"
}

download_verified_core() {
    say "Downloading fixed core release $CORE_VERSION..."
    local rc
    fetch_core || {
        rc=$?
        say "Core download failed (curl exit $rc). The core was not run."
        explain_curl_error "$rc"
        return 1
    }
    local hash
    hash=$(core_hash) || { say 'Cannot verify SHA-256. Stopping.'; return 1; }
    [ "$hash" = "$CORE_SHA" ] || { say 'Checksum mismatch. Nothing will run.'; return 1; }
    /bin/bash -n "$CORE" || return 1
    say 'Checksum verified.'
}

launcher_is_macos() {
    case ${OSTYPE:-} in darwin*) return 0 ;; *) return 1 ;; esac
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
    [ "${#CHOICES[@]}" -gt 0 ] || { say 'No matching mounted volumes or backups found.'; return 2; }
    say "$title"
    for answer in "${CHOICES[@]}"; do
        index=$((index + 1))
        say "  $index) $answer"
    done
    while true; do
        say 'Enter a number, or q to cancel:'
        reply answer || return 3
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
    selected=$(choose 'Select the separate backup volume (APFS/HFS, ownership enabled):') || return $?
    [ "$selected" != "$target" ] || { say 'The target cannot also be the backup volume.'; return 2; }
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
    local target admin backup answer rc
    target=$(choose_target) || {
        rc=$?
        if [ "$rc" -eq 1 ]; then say 'Preview cancelled before changes.'; return 0; fi
        say "Preview could not start (selection exit $rc). No changes made."
        return "$rc"
    }
    say 'New lab account name (Enter for labadmin):'
    reply admin || { say 'Preview stopped: could not read the account name.'; return 1; }
    admin=${admin:-labadmin}
    say 'Stage: read-only preview.'
    run_core plan --data-volume "$target" --create-admin "$admin" || {
        rc=$?
        say "PREVIEW BLOCKED (exit $rc). No installation changes were made."
        return "$rc"
    }
    say 'PREVIEW PASSED. No installation changes were made.'
    say 'Continue to backup selection and apply? Type Y, or press Enter to stop after preview:'
    reply answer || { say 'Preview finished; apply was not requested.'; return 0; }
    case "$answer" in Y|y) ;; *) say 'Preview finished; apply was not requested.'; return 0 ;; esac
    backup=$(choose_backup "$target") || {
        rc=$?
        if [ "$rc" -eq 1 ]; then say 'Apply cancelled before changes.'; return 0; fi
        say "Backup selection blocked (exit $rc). No changes made."
        return "$rc"
    }
    say "Target: $target"
    say "New account: $admin"
    say "Backup: $backup"
    say 'Type APPLY to make these changes, or press Enter to cancel:'
    reply answer || { say 'Apply cancelled before changes.'; return 0; }
    [ "$answer" = APPLY ] || { say 'Apply cancelled before changes.'; return 0; }
    say 'Stage: apply with backup and rollback checks.'
    run_core apply --data-volume "$target" --create-admin "$admin" --backup-dir "$backup" || {
        rc=$?
        say "APPLY FAILED (exit $rc). Check the rollback result above before proceeding."
        return "$rc"
    }
    say 'Apply completed. Verify local files with menu option 2 before reboot.'
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
    launcher_is_macos || { say 'This launcher requires macOS.'; return 1; }
    [ -t 0 ] && [ -t 1 ] || { say 'Run from an interactive Terminal.'; return 1; }
    LAB_TMP=$(/usr/bin/mktemp -d /tmp/enrollment-lab-menu.XXXXXXXX) || {
        say 'Cannot create temporary storage under /tmp in Recovery.'
        return 1
    }
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
            1) guided_apply ;;
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

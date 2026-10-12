#!/bin/bash
# Standalone, read-only macOS/Recovery diagnostics. Requires Bash 3.2.
# Only new report files are written; no installation configuration is changed.
SYSTEM_REPORT_VERSION=1.0.0
SR_DIR=''
SR_WORK=''
SR_ACTIVE_PID=''
SR_COMPLETE=false
SR_PROBE_SECONDS=12
SR_DEADLINE=0
SR_OK=0
SR_FAILED=0
SR_UNAVAILABLE=0
SR_UNKNOWN=0
SR_SEQUENCE=0
SR_WRITE_FAILED=false
SR_VOLUMES=()

sr_say() { printf '%s\n' "$*" >&2; }
sr_reply() { IFS= read -r "$1" </dev/tty; }
sr_safe() {
    local value=${1:0:2048} pattern='[! -~]' LC_ALL=C
    value=${value//$pattern/?}
    printf '%s' "$value"
}
sr_field() {
    printf '  %s: %s\n' "$(sr_safe "$1")" "$(sr_safe "$2")" >> "$SR_DIR/report.txt" || {
        SR_WRITE_FAILED=true; return 1;
    }
}
sr_record() {
    local id=$1 title=$2 status=$3 rc=$4 elapsed=$5
    printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$status" "$rc" "$elapsed" "$(sr_safe "$title")" >> "$SR_DIR/checks.tsv" || { SR_WRITE_FAILED=true; return 1; }
    printf '\n[%s] %s — %s (exit %s, %ss)\n' "$status" "$id" "$(sr_safe "$title")" "$rc" "$elapsed" >> "$SR_DIR/report.txt" || { SR_WRITE_FAILED=true; return 1; }
    case "$status" in
        OK) SR_OK=$((SR_OK + 1)) ;;
        UNAVAILABLE) SR_UNAVAILABLE=$((SR_UNAVAILABLE + 1)) ;;
        UNKNOWN|SKIPPED) SR_UNKNOWN=$((SR_UNKNOWN + 1)) ;;
        *) SR_FAILED=$((SR_FAILED + 1)) ;;
    esac
    if [ "$status" != OK ]; then
        local list=findings
        case "$status" in UNAVAILABLE|UNKNOWN|SKIPPED) list=notes ;; esac
        printf '%s: %s (exit %s)\n' "$id" "$status" "$rc" >> "$SR_WORK/$list" || { SR_WRITE_FAILED=true; return 1; }
    fi
}

# Execute a fixed read-only command. Raw output is temporary, capped by ulimit,
# never copied to the final bundle, and only exposed through allowlisted fields.
sr_probe() {
    local id=$1 title=$2 started=$SECONDS rc=0 timed_out=false limit=$SR_PROBE_SECONDS remaining
    shift 2
    SR_SEQUENCE=$((SR_SEQUENCE + 1))
    SR_OUTPUT="$SR_WORK/probe-$SR_SEQUENCE"
    : > "$SR_OUTPUT" || return 1
    SR_STATUS=UNAVAILABLE
    SR_RC=127
    if [ "$SR_DEADLINE" -gt 0 ]; then
        remaining=$((SR_DEADLINE - SECONDS))
        if [ "$remaining" -le 0 ]; then
            SR_STATUS=SKIPPED; SR_RC=124
            sr_record "$id" "$title (collection time budget reached)" "$SR_STATUS" "$SR_RC" 0
            return
        fi
        [ "$remaining" -ge "$limit" ] || limit=$remaining
    fi
    if [ ! -x "$1" ]; then
        sr_record "$id" "$title" "$SR_STATUS" "$SR_RC" 0
        return
    fi
    if [ ! -x /bin/sleep ]; then
        SR_STATUS=UNKNOWN
        SR_RC=125
        sr_record "$id" "$title (timeout support unavailable)" "$SR_STATUS" "$SR_RC" 0
        return
    fi
    sr_say "Checking: $title"
    (ulimit -f 128 || exit 125; exec "$@") > "$SR_OUTPUT" 2>/dev/null &
    SR_ACTIVE_PID=$!
    while kill -0 "$SR_ACTIVE_PID" 2>/dev/null; do
        if [ "$((SECONDS - started))" -ge "$limit" ]; then
            timed_out=true
            kill -TERM "$SR_ACTIVE_PID" 2>/dev/null || true
            /bin/sleep 0.2
            kill -KILL "$SR_ACTIVE_PID" 2>/dev/null || true
            break
        fi
        /bin/sleep 0.1
    done
    wait "$SR_ACTIVE_PID" 2>/dev/null || rc=$?
    SR_ACTIVE_PID=''
    SR_RC=$rc
    if [ "$timed_out" = true ]; then
        SR_STATUS=TIMEOUT
    elif [ "$rc" -eq 0 ]; then
        SR_STATUS=OK
    elif [ "$rc" -eq 153 ]; then
        SR_STATUS=OUTPUT_LIMIT
    else
        SR_STATUS=FAILED
    fi
    sr_record "$id" "$title" "$SR_STATUS" "$rc" "$((SECONDS - started))"
}

sr_first_line() {
    local value=''
    IFS= read -r value < "$SR_OUTPUT" || true
    sr_safe "$value"
}
sr_scalar() {
    local id=$1 title=$2 value
    shift 2
    sr_probe "$id" "$title" "$@" || return 1
    if [ "$SR_STATUS" = OK ]; then
        value=$(sr_first_line)
        if [ -n "$value" ]; then sr_field "$title" "$value"
        else sr_record "$id.parse" 'Command returned no value' UNKNOWN 0 0; fi
    fi
}
sr_trim() {
    local value=$1
    value=${value#"${value%%[![:space:]]*}"}
    value=${value%"${value##*[![:space:]]}"}
    printf '%s' "$value"
}
sr_disk_fields() {
    local id=$1 key value line recognized=0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in *:*) ;; *) continue ;; esac
        key=$(sr_trim "${line%%:*}")
        value=$(sr_trim "${line#*:}")
        case "$key" in
            'Device Identifier'|'Whole'|'Mounted'|'File System Personality'|'Type (Bundle)'|\
            'Owners'|'SMART Status'|'Disk Size'|'Volume Total Space'|'Volume Used Space'|\
            'Container Total Space'|'Container Free Space'|'Volume Free Space'|\
            'Media Read-Only'|'Volume Read-Only'|'Read-Only Media'|'Read-Only Volume'|\
            'FileVault'|'Locked'|'Sealed'|'Solid State'|'Protocol')
                sr_field "$key" "$value"
                recognized=$((recognized + 1)) ;;
            'Volume Name')
                case "$value" in
                    'macOS Base System'|'OS X Base System'|'Recovery'|'macOS Recovery')
                        sr_field 'Recognized Recovery volume name' yes ;;
                esac ;;
        esac
    done < "$SR_OUTPUT"
    if [ "$recognized" -eq 0 ]; then
        sr_field 'Metadata interpretation' 'UNKNOWN: no recognized fields; raw disk output omitted.'
        sr_record "$id.parse" 'No recognized disk metadata fields' UNKNOWN 0 0
    fi
}
sr_space() {
    local id=$1 source total used available percent rest found=false
    while read -r source total used available percent rest; do
        if [[ "$total" =~ ^[0-9]+$ ]] && [[ "$used" =~ ^[0-9]+$ ]] && [[ "$available" =~ ^[0-9]+$ ]]; then
            sr_field '1024-byte blocks total / used / available' "$total / $used / $available"
            sr_field 'Capacity used' "$percent"
            found=true
        fi
    done < "$SR_OUTPUT"
    if [ "$found" != true ]; then
        sr_field 'Space interpretation' UNKNOWN
        sr_record "$id.parse" 'No recognized capacity fields' UNKNOWN 0 0
    fi
}
sr_os_file() {
    local label=$1 root=$2 value path="$2/System/Library/CoreServices/SystemVersion.plist"
    [ ! -L "$root/System" ] && [ ! -L "$root/System/Library" ] &&
        [ ! -L "$root/System/Library/CoreServices" ] && [ ! -L "$path" ] && [ -f "$path" ] || return 0
    sr_probe "$label.version" 'Mounted installation OS version' /usr/libexec/PlistBuddy -c 'Print :ProductVersion' "$path" || return 1
    if [ "$SR_STATUS" = OK ]; then
        value=$(sr_first_line)
        if [[ "$value" =~ ^[0-9]+(\.[0-9]+){1,3}$ ]]; then sr_field 'ProductVersion' "$value"
        else sr_record "$label.version.parse" 'Unexpected OS version format' UNKNOWN 0 0; fi
    fi
    sr_probe "$label.build" 'Mounted installation OS build' /usr/libexec/PlistBuddy -c 'Print :ProductBuildVersion' "$path" || return 1
    if [ "$SR_STATUS" = OK ]; then
        value=$(sr_first_line)
        if [[ "$value" =~ ^[A-Za-z0-9.]{1,30}$ ]]; then sr_field 'ProductBuildVersion' "$value"
        else sr_record "$label.build.parse" 'Unexpected OS build format' UNKNOWN 0 0; fi
    fi
    sr_field 'Installation mount' "$root"
}
sr_network() {
    local id=$1 url=$2 mode=$3 key value http_seen=false args=()
    [ "$mode" != ipv4 ] || args=(-4)
    sr_probe "$id.$mode" "$id HTTPS ($mode)" /usr/bin/curl -q "${args[@]}" -sS -I -L \
        --proto '=https' --proto-redir '=https' --max-redirs 3 --connect-timeout 5 --max-time 10 \
        -o /dev/null -w 'http_code=%{http_code}\ndns_seconds=%{time_namelookup}\nconnect_seconds=%{time_connect}\ntls_seconds=%{time_appconnect}\ntotal_seconds=%{time_total}\n' "$url" || return 1
    if [ "$SR_STATUS" = OK ]; then
        while IFS='=' read -r key value; do
            case "$key" in http_code|dns_seconds|connect_seconds|tls_seconds|total_seconds)
                [[ "$value" =~ ^[0-9.]+$ ]] && sr_field "$key" "$value"
                if [ "$key" = http_code ] && [[ "$value" =~ ^[1-5][0-9][0-9]$ ]]; then http_seen=true; fi ;;
            esac
        done < "$SR_OUTPUT"
        if [ "$http_seen" = true ]; then
            sr_field 'Interpretation' 'HTTP response received. HTTP status and service availability are separate from connectivity.'
        else
            sr_record "$id.$mode.parse" 'HTTP response code unavailable' UNKNOWN 0 0
        fi
    else
        case "$SR_RC" in
            6) sr_field 'Failure detail' 'DNS lookup failed' ;;
            7) sr_field 'Failure detail' 'Connection failed' ;;
            28) sr_field 'Failure detail' 'curl timed out' ;;
            35) sr_field 'Failure detail' 'TLS negotiation failed' ;;
            60) sr_field 'Failure detail' 'TLS certificate verification failed; check clock and network trust' ;;
            47) sr_field 'Failure detail' 'Too many HTTPS redirects' ;;
            *) sr_field 'Failure detail' 'Probe did not complete; consult status and exit code' ;;
        esac
    fi
}

sr_find_volumes() {
    local path
    SR_VOLUMES=()
    for path in /Volumes/*; do
        [ -d "$path" ] && [ ! -L "$path" ] || continue
        SR_VOLUMES[${#SR_VOLUMES[@]}]=$path
    done
}

sr_collect() {
    local target=$1 network=$2 tool path index=0 line roles=0
    sr_field 'Report version' "$SYSTEM_REPORT_VERSION"
    sr_field 'Bash version' "$BASH_VERSION"
    sr_field 'Shell platform' "${OSTYPE:-unknown} / ${MACHTYPE:-unknown}"
    sr_field 'Effective UID' "$EUID"
    sr_field 'Selected target' "${target:-none; system-only report}"
    sr_field 'Network probes' "$network"
    sr_scalar clock.utc 'UTC clock' /bin/date -u '+%Y-%m-%dT%H:%M:%SZ' || return 1
    sr_scalar boot.os.version 'Running OS version (Recovery when booted there)' /usr/bin/sw_vers -productVersion || return 1
    sr_scalar boot.os.build 'Running OS build' /usr/bin/sw_vers -buildVersion || return 1
    sr_scalar hardware.model 'Hardware model' /usr/sbin/sysctl -n hw.model || return 1
    sr_scalar hardware.arch 'Kernel architecture' /usr/bin/uname -m || return 1
    sr_scalar hardware.cpu 'CPU description' /usr/sbin/sysctl -n machdep.cpu.brand_string || return 1
    sr_scalar hardware.memory 'Memory bytes' /usr/sbin/sysctl -n hw.memsize || return 1
    sr_scalar security.sip 'System Integrity Protection' /usr/bin/csrutil status || return 1
    sr_scalar security.seal 'Authenticated root policy' /usr/bin/csrutil authenticated-root status || return 1
    for tool in /usr/sbin/diskutil /usr/libexec/PlistBuddy /usr/bin/plutil /usr/bin/curl \
        /usr/bin/openssl /usr/bin/shasum /usr/bin/mktemp /bin/df /bin/cp /bin/mkdir /bin/rm /bin/sleep; do
        if [ -x "$tool" ]; then sr_record "utility.${tool##*/}" "$tool executable" OK 0 0
        else sr_record "utility.${tool##*/}" "$tool executable" UNAVAILABLE 127 0; fi || return 1
    done
    sr_probe storage.boot 'Boot volume metadata' /usr/sbin/diskutil info / || return 1
    [ "$SR_STATUS" != OK ] || sr_disk_fields storage.boot
    sr_probe storage.tmp 'Temporary storage capacity' /bin/df -Pk /tmp || return 1
    [ "$SR_STATUS" != OK ] || sr_space storage.tmp
    if [ -n "$target" ]; then
        if [ -d "$target" ]; then
            sr_probe storage.target 'Selected target metadata' /usr/sbin/diskutil info "$target" || return 1
            [ "$SR_STATUS" != OK ] || sr_disk_fields storage.target
            sr_probe storage.target.space 'Selected target capacity' /bin/df -Pk "$target" || return 1
            [ "$SR_STATUS" != OK ] || sr_space storage.target.space
            sr_os_file selected "$target" || return 1
        else
            sr_record storage.target 'Selected target is not a mounted directory' UNKNOWN 2 0 || return 1
        fi
    fi
    sr_probe storage.roles 'Mounted APFS role inventory' /usr/sbin/diskutil apfs list || return 1
    if [ "$SR_STATUS" = OK ]; then
        while IFS= read -r line; do
            case "$line" in *'APFS Volume Disk (Role):'*)
                line=$(sr_trim "${line#*'APFS Volume Disk (Role):'}")
                if [[ "$line" =~ ^disk[0-9]+s[0-9]+[[:space:]]+\([A-Za-z,[:space:]]+\)$ ]]; then
                    sr_field 'APFS volume / role' "$line"
                    roles=$((roles + 1))
                fi ;;
            esac
        done < "$SR_OUTPUT"
        if [ "$roles" -eq 0 ]; then sr_record storage.roles.parse 'No recognized APFS role entries' UNKNOWN 0 0; fi
    fi
    sr_find_volumes
    for path in "${SR_VOLUMES[@]}"; do
        index=$((index + 1))
        [ "$index" -le 32 ] || { sr_record storage.inventory 'Mounted-volume inventory capped at 32' SKIPPED 0 0; break; }
        [ "$path" = "$target" ] || sr_os_file "installation.$index" "$path" || return 1
    done
    sr_field 'Installation version interpretation' 'Versions above are tied to their mount paths; no System/Data pairing is guessed.'
    if [ "$network" = yes ]; then
        sr_network github https://github.com/ ipv4 || return 1
        sr_network github https://github.com/ automatic || return 1
        sr_network github_raw https://raw.githubusercontent.com/ automatic || return 1
        sr_network apple https://www.apple.com/ automatic || return 1
    else
        sr_record network 'HTTPS probes disabled by --no-network' SKIPPED 0 0 || return 1
    fi
}

sr_cleanup() {
    local rc=$?
    trap - EXIT INT TERM HUP
    if [ -n "$SR_ACTIVE_PID" ]; then
        kill -TERM "$SR_ACTIVE_PID" 2>/dev/null || true
        kill -KILL "$SR_ACTIVE_PID" 2>/dev/null || true
        wait "$SR_ACTIVE_PID" 2>/dev/null || true
    fi
    if [ -n "$SR_WORK" ] && [ -d "$SR_WORK" ]; then /bin/rm -rf "$SR_WORK"; fi
    if [ "$SR_COMPLETE" != true ] && [ -n "$SR_DIR" ]; then
        printf 'INCOMPLETE REPORT: collection stopped (exit %s).\n' "$rc" >> "$SR_DIR/summary.txt"
        sr_say "Partial report retained at: $SR_DIR"
    fi
    exit "$rc"
}

sr_choose() {
    local title=$1 zero=$2 index=0 answer path
    sr_find_volumes
    sr_say "$title"
    sr_say "  0) $zero (default)"
    for path in "${SR_VOLUMES[@]}"; do index=$((index + 1)); sr_say "  $index) $(sr_safe "$path")"; done
    while true; do
        sr_reply answer || return 1
        answer=${answer:-0}
        case "$answer" in 0) return 0 ;; q|Q) return 1 ;; esac
        if [[ "$answer" =~ ^[1-9][0-9]{0,3}$ ]] && [ "$answer" -le "${#SR_VOLUMES[@]}" ]; then
            printf '%s\n' "${SR_VOLUMES[$((answer - 1))]}"
            return 0
        fi
        sr_say 'Enter a listed number, or q to cancel.'
    done
}

system_report_main() {
    set +x
    umask 077
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin LC_ALL=C
    local target='' parent=/tmp network=yes interactive=false line list shown=0
    [ "$#" -ne 0 ] || interactive=true
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --target|--output-parent)
                [ "$#" -ge 2 ] && [ -n "$2" ] || { sr_say "Missing value for $1"; return 2; }
                case "$1" in --target) target=$2 ;; --output-parent) parent=$2 ;; esac
                shift 2 ;;
            --no-network) network=no; shift ;;
            --version) printf '%s\n' "$SYSTEM_REPORT_VERSION"; return 0 ;;
            --help|-h)
                sr_say 'Usage: bash system-report.sh [--target MOUNT] [--output-parent DIRECTORY] [--no-network]'
                sr_say 'With no arguments, numbered prompts select a target and report destination.'
                sr_say 'Read-only diagnostics; writes only a new report folder. No uploads or installation changes.'
                return 0 ;;
            *) sr_say "Unknown option: $1"; return 2 ;;
        esac
    done
    case ${OSTYPE:-} in darwin*) ;; *) sr_say 'This report is for macOS and macOS Recovery.'; return 1 ;; esac
    for line in /usr/bin/mktemp /bin/mkdir /bin/rm; do
        [ -x "$line" ] || { sr_say "Cannot prepare report storage; missing $line"; return 1; }
    done
    if [ "$interactive" = true ]; then
        [ -t 0 ] && [ -t 1 ] || { sr_say 'Use --no-network or --target PATH for noninteractive collection.'; return 2; }
        target=$(sr_choose 'Select the mounted volume to inspect:' 'System-only report') || return 1
        parent=$(sr_choose 'Where should the new report folder be saved?' 'Temporary /tmp; lost on reboot') || return 1
        parent=${parent:-/tmp}
    fi
    parent=$(cd -P "$parent" 2>/dev/null && pwd -P) || { sr_say 'Report destination must be an existing writable directory.'; return 1; }
    SR_DIR=$(/usr/bin/mktemp -d "$parent/mac-support.XXXXXXXX") || { sr_say 'Cannot create the report folder; check destination permissions and free space.'; return 1; }
    trap sr_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    SR_WORK=$(/usr/bin/mktemp -d /tmp/mac-support-work.XXXXXXXX) || { sr_say 'Cannot create private scratch storage under /tmp.'; return 1; }
    : > "$SR_WORK/findings" || return 1
    : > "$SR_WORK/notes" || return 1
    printf 'macOS support report %s\n\nOK means the probe completed, not that the whole system is healthy.\nMissing information remains UNKNOWN. Raw command output is not retained.\n' "$SYSTEM_REPORT_VERSION" > "$SR_DIR/report.txt" || return 1
    printf 'check_id\tstatus\texit_code\telapsed_seconds\tdescription\n' > "$SR_DIR/checks.tsv" || return 1
    sr_say "Collecting report into: $SR_DIR"
    SR_DEADLINE=$((SECONDS + 180))
    sr_collect "$target" "$network" || { sr_say 'Report writing failed; check destination storage.'; return 1; }
    [ "$SR_WRITE_FAILED" = false ] || { sr_say 'Report writing failed; results are incomplete.'; return 1; }
    {
        printf 'macOS support report %s\n' "$SYSTEM_REPORT_VERSION"
        printf 'Probes: %s completed; %s failed/timed out; %s unavailable; %s unknown/skipped.\n' "$SR_OK" "$SR_FAILED" "$SR_UNAVAILABLE" "$SR_UNKNOWN"
        printf 'Unavailable or unsupported probes do not by themselves establish a fault.\n'
        for list in "$SR_WORK/findings" "$SR_WORK/notes"; do
            while IFS= read -r line; do
                shown=$((shown + 1))
                [ "$shown" -le 18 ] || break
                printf '%s\n' "$line"
            done < "$list"
        done
        [ "$shown" -le 18 ] || printf 'Additional findings are listed in checks.tsv.\n'
        printf 'See report.txt for allowlisted details and checks.tsv for every probe.\n'
        printf 'This report does not establish a root cause or management status.\n'
    } > "$SR_DIR/summary.txt" || return 1
    /bin/rm -rf "$SR_WORK" || return 1
    SR_WORK=''
    SR_COMPLETE=true
    sr_say 'Report complete. No report was uploaded.'
    while IFS= read -r line; do sr_say "$line"; done < "$SR_DIR/summary.txt"
    sr_say "Folder: $SR_DIR"
    case "$parent/" in /tmp/*|/private/tmp/*) sr_say 'Save this folder to a persistent volume before rebooting.' ;; esac
    printf '%s\n' "$SR_DIR"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then system_report_main "$@"; fi

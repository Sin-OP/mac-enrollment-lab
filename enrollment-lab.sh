#!/bin/bash
# Original implementation. macOS ships Bash 3.2; do not use newer Bash features.

VERSION=0.1.3-rc1
TARGET=''
BACKUP=''
ADMIN=''
VOLUME_UUID=''
DEVICE_ID=''
SCRATCH=''
LOCK=''
STAGED_HOSTS=''
TRANSACTION=false
CREATED_HOME=false
PATHS=()
DOMAINS=(deviceenrollment.apple.com mdmenrollment.apple.com iprofiles.apple.com)
BEGIN_BLOCK='# BEGIN mac-enrollment-lab'
END_BLOCK='# END mac-enrollment-lab'

log() { printf '%s\n' "$*" >&2; }
fail() { log "ERROR: $*"; return 1; }
plist_get() { /usr/libexec/PlistBuddy -c "Print :$2" "$1" 2>/dev/null; }
hash_shasum() { /usr/bin/shasum -a 256 "$1"; }
hash_openssl() { /usr/bin/openssl dgst -sha256 "$1"; }
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
digest() {
    local output value
    if output=$(hash_shasum "$1" 2>/dev/null); then
        value=${output%% *}
        if [[ "$value" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$value"; return 0; fi
    fi
    if output=$(hash_openssl "$1" 2>/dev/null); then
        value=${output##* }
        if [[ "$value" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$value"; return 0; fi
    fi
    if value=$(sha256_bash "$1"); then
        if [[ "$value" =~ ^[a-fA-F0-9]{64}$ ]]; then printf '%s\n' "$value"; return 0; fi
    fi
    fail 'Cannot calculate SHA-256; no checksum accepted.'
}
disk_info() { /usr/sbin/diskutil info -plist "$1"; }
apfs_inventory() { /usr/sbin/diskutil apfs list -plist; }
live_data_filesystem() { LC_ALL=C /bin/df -Pk /System/Volumes/Data; }
profiles_status() { /usr/bin/profiles status -type enrollment; }
valid_name() { [[ "$1" =~ ^[a-z][a-z0-9_]{0,30}$ ]] && [ "$1" != root ]; }
valid_uuid() { [[ "$1" =~ ^[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$ ]]; }

usage() {
    cat <<'USAGE'
mac-enrollment-lab: experimental fresh-install enrollment-suppression test

  enrollment-lab.sh volumes
  enrollment-lab.sh plan --data-volume PATH --create-admin NAME
  enrollment-lab.sh apply --data-volume PATH --create-admin NAME --backup-dir NEW_PATH
  enrollment-lab.sh verify --data-volume PATH
  enrollment-lab.sh restore --data-volume PATH --backup-dir PATH
  enrollment-lab.sh status
  enrollment-lab.sh version

plan is read-only. apply/restore require Recovery and root. Select an already
mounted, unlocked APFS Data volume explicitly. Backup must be on persistent
APFS/HFS storage, outside the target. apply requires an unfinished fresh setup.
dscl prompts for the new admin password; no password is accepted as an argument.
restore requires unchanged managed files and an empty new account home directory.
verify checks local file state only; status queries the running OS only.
Neither command establishes release from Apple Business/School Manager.
USAGE
}

init_scratch() {
    SCRATCH=$(/usr/bin/mktemp -d /tmp/mac-enrollment-lab.XXXXXXXX) || return 1
}

cleanup() {
    local rc=$?
    trap - EXIT INT TERM HUP
    if [ "$TRANSACTION" = true ]; then
        log 'Operation interrupted or failed; restoring the pre-change snapshot.'
        if restore_snapshot; then
            log 'Managed files restored. No reboot was performed.'
        else
            log "ROLLBACK INCOMPLETE. Keep the device in Recovery. Backup: $BACKUP"
            log "Target lock retained for inspection: $LOCK"
            LOCK=''
        fi
        rc=1
    fi
    if [ -n "$LOCK" ]; then /bin/rmdir "$LOCK" 2>/dev/null || true; fi
    if [ -n "$STAGED_HOSTS" ]; then /bin/rm -f "$STAGED_HOSTS"; fi
    if [ -n "$SCRATCH" ] && [ -d "$SCRATCH" ]; then /bin/rm -rf "$SCRATCH"; fi
    exit "$rc"
}

require_macos() { [ "$(/usr/bin/uname -s)" = Darwin ] || fail 'macOS is required.'; }

require_recovery() {
    [ "$EUID" -eq 0 ] || { fail 'Run from the root Terminal in Recovery.'; return 1; }
    local root_name
    disk_info / > "$SCRATCH/root.plist" || return 1
    root_name=$(plist_get "$SCRATCH/root.plist" VolumeName) || return 1
    case "$root_name" in
        'macOS Base System'|'OS X Base System'|'Recovery'|'macOS Recovery') ;;
        *) fail 'The boot volume is not a recognized Recovery environment.'; return 1 ;;
    esac
}

canonical_dir() { (cd -P "$1" 2>/dev/null && pwd -P); }

# Recovery can mount tmpfs here. diskutil cannot describe that RAM filesystem.
# Accept that specific case only after both Recovery and tmpfs are verified.
validate_live_data() {
    local live_uuid output filesystem size used available capacity mountpoint
    if disk_info /System/Volumes/Data > "$SCRATCH/live.plist"; then
        live_uuid=$(plist_get "$SCRATCH/live.plist" VolumeUUID) || {
            fail 'Cannot read the running Data volume UUID.'; return 1;
        }
        valid_uuid "$live_uuid" || { fail 'Invalid running Data volume UUID.'; return 1; }
        [ "$live_uuid" != "$VOLUME_UUID" ] || { fail 'Refusing the running system Data volume.'; return 1; }
        return 0
    fi
    require_recovery || { fail 'Cannot identify the running Data filesystem outside verified Recovery.'; return 1; }
    output=$(live_data_filesystem) || { fail 'Cannot inspect the Recovery Data filesystem.'; return 1; }
    while read -r filesystem size used available capacity mountpoint; do
        if [ "$filesystem" = tmpfs ] && [ "$mountpoint" = /System/Volumes/Data ]; then
            log 'Recognized Recovery temporary Data filesystem (tmpfs).'
            return 0
        fi
    done <<< "$output"
    fail 'Unrecognized running Data filesystem; expected verified Recovery tmpfs.'
    return 1
}

# Reject symlinks in every component, not only the leaf. No path is evaluated.
safe_path() {
    local rel=$1 part cursor=$TARGET remaining=$1
    case "$rel" in ''|/*|*'..'*) fail "Unsafe relative path: $rel"; return 1 ;; esac
    while [ -n "$remaining" ]; do
        part=${remaining%%/*}
        cursor="$cursor/$part"
        [ ! -L "$cursor" ] || { fail "Symlink refused: $cursor"; return 1; }
        if [ "$remaining" = "$part" ]; then break; fi
        [ -d "$cursor" ] || { fail "Missing parent directory: $cursor"; return 1; }
        remaining=${remaining#*/}
    done
    if [ -e "$cursor" ] && [ ! -f "$cursor" ]; then
        fail "Expected regular file: $cursor"; return 1
    fi
}

validate_target() {
    [ -n "$TARGET" ] && [ -d "$TARGET" ] || { fail 'Specify a mounted Data volume.'; return 1; }
    TARGET=$(canonical_dir "$TARGET") || return 1
    [ "$TARGET" != / ] || { fail 'The boot filesystem cannot be a target.'; return 1; }
    disk_info "$TARGET" > "$SCRATCH/target.plist" || return 1
    [ "$(plist_get "$SCRATCH/target.plist" MountPoint)" = "$TARGET" ] || {
        fail 'The target must be the volume mount point, not a directory inside it.'; return 1;
    }
    [ "$(plist_get "$SCRATCH/target.plist" FilesystemType)" = apfs ] || { fail 'APFS required.'; return 1; }
    [ "$(plist_get "$SCRATCH/target.plist" Writable)" = true ] || { fail 'Target is not writable/unlocked.'; return 1; }
    VOLUME_UUID=$(plist_get "$SCRATCH/target.plist" VolumeUUID) || return 1
    valid_uuid "$VOLUME_UUID" || { fail 'Invalid volume UUID.'; return 1; }
    DEVICE_ID=$(plist_get "$SCRATCH/target.plist" DeviceIdentifier) || return 1
    [[ "$DEVICE_ID" =~ ^disk[0-9]+s[0-9]+$ ]] || { fail 'Unexpected device identifier.'; return 1; }

    # Never accept the running system's Data volume, even through another mount path.
    if [ -d /System/Volumes/Data ]; then
        validate_live_data || return 1
    fi

    apfs_inventory > "$SCRATCH/apfs.plist" || return 1
    local ci=0 vi ri dev role found=false
    while plist_get "$SCRATCH/apfs.plist" "Containers:$ci:ContainerReference" >/dev/null; do
        vi=0
        while dev=$(plist_get "$SCRATCH/apfs.plist" "Containers:$ci:Volumes:$vi:DeviceIdentifier"); do
            if [ "$dev" = "$DEVICE_ID" ]; then
                ri=0
                while role=$(plist_get "$SCRATCH/apfs.plist" "Containers:$ci:Volumes:$vi:Roles:$ri"); do
                    [ "$role" != Data ] || found=true
                    ri=$((ri + 1))
                done
            fi
            vi=$((vi + 1))
        done
        ci=$((ci + 1))
    done
    [ "$found" = true ] || { fail 'Selected volume does not have APFS Data role.'; return 1; }
    local rel
    for rel in private/etc/hosts private/var/db/.AppleSetupDone \
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigRecordFound \
        private/var/db/dslocal/nodes/Default/groups/admin.plist; do
        safe_path "$rel" || return 1
    done
    [ -f "$TARGET/private/etc/hosts" ] || { fail 'Target hosts file missing.'; return 1; }
    [ -f "$TARGET/private/var/db/dslocal/nodes/Default/groups/admin.plist" ] || {
        fail 'Target local Directory Services database missing.'; return 1;
    }
}

build_paths() {
    PATHS=(
        private/etc/hosts
        private/var/db/.AppleSetupDone
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigHasActivationRecord
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigRecordFound
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigProfileInstalled
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigRecordNotFound
        "private/var/db/dslocal/nodes/Default/users/$ADMIN.plist"
        private/var/db/dslocal/nodes/Default/groups/admin.plist
    )
}

validate_fresh_install() {
    valid_name "$ADMIN" || { fail 'Admin name: 1–31 lowercase letters/digits/underscores, starting with a letter; root forbidden.'; return 1; }
    [ ! -e "$TARGET/private/var/db/.AppleSetupDone" ] || { fail 'Setup is already complete. This version only handles fresh installations.'; return 1; }
    # An offline-created account does not automatically acquire a Secure Token.
    [ "$(plist_get "$SCRATCH/target.plist" FileVault)" = false ] || {
        fail 'New offline accounts on FileVault-enabled/unknown volumes are unsupported.'; return 1;
    }
    build_paths
    local rel
    for rel in "${PATHS[@]}"; do safe_path "$rel" || return 1; done
    [ ! -e "$TARGET/${PATHS[6]}" ] || { fail 'Admin account already exists.'; return 1; }
    # A record can have aliases that differ from its filename. Do not let dscl
    # resolve the requested new name to an existing, unsnapshotted account.
    local user_file alias index
    for user_file in "$TARGET/private/var/db/dslocal/nodes/Default/users/"*.plist; do
        [ -f "$user_file" ] && [ ! -L "$user_file" ] || { fail 'Invalid existing user record.'; return 1; }
        alias=$(plist_get "$user_file" name:0) || { fail 'Cannot read existing account names.'; return 1; }
        index=0
        while alias=$(plist_get "$user_file" "name:$index"); do
            [ "$(printf '%s' "$alias" | /usr/bin/tr '[:upper:]' '[:lower:]')" != "$ADMIN" ] || {
                fail 'Admin name matches an existing account or alias.'; return 1;
            }
            index=$((index + 1))
        done
    done
    [ ! -e "$TARGET/Users/$ADMIN" ] && [ ! -L "$TARGET/Users/$ADMIN" ] || {
        fail 'Requested home directory already exists.'; return 1;
    }
    [ -d "$TARGET/Users" ] && [ ! -L "$TARGET/Users" ] || { fail 'Invalid Users directory.'; return 1; }
    # Do not interpret an installed MDM profile as a setup-only enrollment record.
    local store="$TARGET/private/var/db/ConfigurationProfiles/Store"
    if [ -L "$store" ]; then fail 'Profile store symlink refused.'; return 1; fi
    if [ -d "$store" ]; then
        local first_file
        first_file=$(/usr/bin/find "$store" -type f -print -quit) || return 1
        if [ -n "$first_file" ]; then
            fail 'Profile store contains files. Already-configured devices are outside this prototype’s scope.'; return 1
        fi
    fi
    /usr/bin/grep -Fq "$BEGIN_BLOCK" "$TARGET/private/etc/hosts" && {
        fail 'A previous lab block exists; restore its snapshot before another apply.'; return 1;
    }
    return 0
}

validate_backup_parent() {
    local parent=$1 fs backup_uuid mount_point
    disk_info "$parent" > "$SCRATCH/backup-volume.plist" || return 1
    fs=$(plist_get "$SCRATCH/backup-volume.plist" FilesystemType) || return 1
    case "$fs" in apfs|hfs) ;; *) fail 'Backup storage must preserve Unix permissions (APFS/HFS).'; return 1 ;; esac
    [ "$(plist_get "$SCRATCH/backup-volume.plist" GlobalPermissionsEnabled)" = true ] || {
        fail 'Backup volume ownership enforcement must be enabled. See docs/DEPLOYMENT.md.'; return 1;
    }
    [ "$(plist_get "$SCRATCH/backup-volume.plist" Writable)" = true ] || {
        fail 'Backup volume must be writable.'; return 1;
    }
    mount_point=$(plist_get "$SCRATCH/backup-volume.plist" MountPoint) || return 1
    [ -n "$mount_point" ] && [ "$mount_point" != / ] || {
        fail 'Backup cannot reside on the temporary Recovery boot filesystem.'; return 1;
    }
    backup_uuid=$(plist_get "$SCRATCH/backup-volume.plist" VolumeUUID) || return 1
    valid_uuid "$backup_uuid" || { fail 'Cannot verify backup volume identity.'; return 1; }
    [ "$backup_uuid" != "$VOLUME_UUID" ] || {
        fail 'Use a different persistent volume for the backup.'; return 1;
    }
}

prepare_backup() {
    [ -n "$BACKUP" ] && [ ! -e "$BACKUP" ] && [ ! -L "$BACKUP" ] || {
        fail 'Choose a new, nonexistent backup directory.'; return 1;
    }
    local parent base
    parent=$(canonical_dir "$(/usr/bin/dirname "$BACKUP")") || { fail 'Backup parent must already exist.'; return 1; }
    base=$(/usr/bin/basename "$BACKUP")
    case "$base" in ''|.|..) fail 'Invalid backup directory name.'; return 1 ;; esac
    BACKUP="$parent/$base"
    case "$BACKUP/" in "$TARGET/"*) fail 'Backup must be outside the target.'; return 1 ;; esac
    validate_backup_parent "$parent" || return 1
    /bin/mkdir -m 700 "$BACKUP" || return 1
    printf '%s\n' 1 > "$BACKUP/format" || return 1
    printf '%s\n' "$VOLUME_UUID" > "$BACKUP/volume-uuid" || return 1
    printf '%s\n' "$ADMIN" > "$BACKUP/admin-name" || return 1
    local i=0 src sum
    for src in "${PATHS[@]}"; do
        if [ -f "$TARGET/$src" ]; then
            /bin/cp -p "$TARGET/$src" "$BACKUP/$i.original" || return 1
            sum=$(digest "$BACKUP/$i.original") || return 1
            printf '%s\n' "$sum" > "$BACKUP/$i.before" || return 1
        else
            printf '%s\n' absent > "$BACKUP/$i.before" || return 1
        fi
        i=$((i + 1))
    done
    printf '%s\n' snapshot-complete > "$BACKUP/state" || return 1
}

acquire_lock() {
    local candidate="$TARGET/private/var/db/mac-enrollment-lab.lock"
    /bin/mkdir -m 700 "$candidate" 2>/dev/null || {
        fail 'Target lock exists. Check for an active or interrupted operation before removing it.'; return 1;
    }
    LOCK=$candidate
}

choose_uid() {
    local node="$TARGET/private/var/db/dslocal/nodes/Default" file uid candidate=501
    : > "$SCRATCH/uids" || return 1
    for file in "$node/users/"*.plist; do
        [ -f "$file" ] && [ ! -L "$file" ] || { fail 'Unreadable/symlinked user record.'; return 1; }
        uid=$(plist_get "$file" uid:0) || { fail 'Cannot read an existing UID.'; return 1; }
        [[ "$uid" =~ ^-?[0-9]+$ ]] || { fail 'Malformed existing UID.'; return 1; }
        printf '%s\n' "$uid" >> "$SCRATCH/uids" || return 1
    done
    while [ "$candidate" -le 599 ]; do
        if ! /usr/bin/grep -qx "$candidate" "$SCRATCH/uids"; then
            printf '%s\n' "$candidate"; return 0
        fi
        candidate=$((candidate + 1))
    done
    fail 'No free UID in 501–599; refusing to reuse one.'
}

ds_target() {
    /usr/bin/dscl -f "$TARGET/private/var/db/dslocal/nodes/Default" localonly "$@"
}

create_admin() {
    local uid guid record="/Local/Target/Users/$ADMIN"
    uid=$(choose_uid) || return 1
    guid=$(/usr/bin/uuidgen) || return 1
    ds_target -create "$record" || return 1
    ds_target -create "$record" UserShell /bin/zsh || return 1
    ds_target -create "$record" RealName 'Enrollment Lab Admin' || return 1
    ds_target -create "$record" UniqueID "$uid" || return 1
    ds_target -create "$record" PrimaryGroupID 20 || return 1
    ds_target -create "$record" GeneratedUID "$guid" || return 1
    ds_target -create "$record" NFSHomeDirectory "/Users/$ADMIN" || return 1
    log 'Set a unique lab password at the dscl prompt. Input is not logged by this script.'
    ds_target -passwd "$record" </dev/tty || return 1
    ds_target -append /Local/Target/Groups/admin GroupMembership "$ADMIN" || return 1
    ds_target -append /Local/Target/Groups/admin GroupMembers "$guid" || return 1
    /bin/mkdir -m 700 "$TARGET/Users/$ADMIN" || return 1
    CREATED_HOME=true
    /usr/sbin/chown "$uid:20" "$TARGET/Users/$ADMIN" || return 1
    ds_target -read "$record" UniqueID | /usr/bin/grep -qx "UniqueID: $uid" || return 1
}

replace_hosts() {
    local dest="$TARGET/private/etc/hosts" staged="$TARGET/private/etc/.mac-enrollment-lab.hosts.$$" domain
    [ ! -e "$staged" ] && [ ! -L "$staged" ] || return 1
    STAGED_HOSTS=$staged
    /bin/cp -p "$dest" "$staged" || return 1
    {
        printf '\n%s\n' "$BEGIN_BLOCK"
        for domain in "${DOMAINS[@]}"; do
            printf '0.0.0.0 %s\n:: %s\n' "$domain" "$domain"
        done
        printf '%s\n' "$END_BLOCK"
    } >> "$staged" || { /bin/rm -f "$staged"; return 1; }
    /bin/mv -f "$staged" "$dest" || { /bin/rm -f "$staged"; return 1; }
    STAGED_HOSTS=''
}

write_markers() {
    local cfg="$TARGET/private/var/db/ConfigurationProfiles/Settings"
    /bin/rm -f "$cfg/.cloudConfigHasActivationRecord" "$cfg/.cloudConfigRecordFound" || return 1
    /usr/bin/touch "$cfg/.cloudConfigProfileInstalled" "$cfg/.cloudConfigRecordNotFound" || return 1
    /usr/bin/touch "$TARGET/private/var/db/.AppleSetupDone" || return 1
}

verify_local() {
    local cfg="$TARGET/private/var/db/ConfigurationProfiles/Settings" domain
    safe_path private/etc/hosts || return 1
    for domain in "${DOMAINS[@]}"; do
        /usr/bin/grep -Fxq "0.0.0.0 $domain" "$TARGET/private/etc/hosts" || { fail "Missing IPv4 entry: $domain"; return 1; }
        /usr/bin/grep -Fxq ":: $domain" "$TARGET/private/etc/hosts" || { fail "Missing IPv6 entry: $domain"; return 1; }
    done
    [ ! -e "$cfg/.cloudConfigHasActivationRecord" ] && [ ! -e "$cfg/.cloudConfigRecordFound" ] || {
        fail 'An enrollment record is present.'; return 1;
    }
    local rel
    for rel in private/var/db/.AppleSetupDone \
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigProfileInstalled \
        private/var/db/ConfigurationProfiles/Settings/.cloudConfigRecordNotFound; do
        safe_path "$rel" && [ -f "$TARGET/$rel" ] || { fail "Missing/invalid marker: $rel"; return 1; }
    done
    log 'LOCAL FILE CHECKS PASSED. Enrollment effectiveness and server-side release remain unverified.'
}

record_after() {
    local i=0 rel sum
    for rel in "${PATHS[@]}"; do
        if [ -f "$TARGET/$rel" ]; then sum=$(digest "$TARGET/$rel") || return 1; else sum=absent; fi
        printf '%s\n' "$sum" > "$BACKUP/$i.after" || return 1
        i=$((i + 1))
    done
    printf '%s\n' applied > "$BACKUP/state" || return 1
}

restore_snapshot() {
    local i=0 rel before rc=0
    # Validate the complete snapshot before restoring anything.
    for rel in "${PATHS[@]}"; do
        safe_path "$rel" || return 1
        before=$(/bin/cat "$BACKUP/$i.before") || return 1
        if [ "$before" != absent ]; then
            [ -f "$BACKUP/$i.original" ] && [ ! -L "$BACKUP/$i.original" ] || return 1
            [ "$(digest "$BACKUP/$i.original")" = "$before" ] || { fail 'Backup checksum mismatch.'; return 1; }
        fi
        i=$((i + 1))
    done
    i=0
    for rel in "${PATHS[@]}"; do
        before=$(/bin/cat "$BACKUP/$i.before") || return 1
        if [ "$before" = absent ]; then
            /bin/rm -f "$TARGET/$rel" || rc=1
        else
            /bin/cp -p "$BACKUP/$i.original" "$TARGET/$rel" || rc=1
        fi
        i=$((i + 1))
    done
    if [ "$CREATED_HOME" = true ]; then /bin/rmdir "$TARGET/Users/$ADMIN" || rc=1; fi
    [ "$rc" -eq 0 ] || return 1
    printf '%s\n' restored > "$BACKUP/state" || return 1
}

apply_transaction() {
    prepare_backup || return 1
    TRANSACTION=true
    create_admin || return 1
    replace_hosts || return 1
    write_markers || return 1
    verify_local || return 1
    record_after || return 1
    TRANSACTION=false
    log "Changes staged; backup: $BACKUP"
    log 'Hardware result: NOT TESTED. Reboot manually when ready and follow docs/TESTING.md.'
}

load_backup() {
    [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] || { fail 'Backup directory missing/symlinked.'; return 1; }
    BACKUP=$(canonical_dir "$BACKUP") || return 1
    local entry
    for entry in "$BACKUP/"*; do
        [ -f "$entry" ] && [ ! -L "$entry" ] || { fail 'Backup contains a non-regular entry.'; return 1; }
    done
    [ "$(/bin/cat "$BACKUP/format")" = 1 ] || { fail 'Unsupported backup format.'; return 1; }
    [ "$(/bin/cat "$BACKUP/volume-uuid")" = "$VOLUME_UUID" ] || { fail 'Backup belongs to another volume.'; return 1; }
    [ "$(/bin/cat "$BACKUP/state")" = applied ] || { fail 'Backup is not a completed application snapshot. Inspect an interrupted snapshot manually.'; return 1; }
    ADMIN=$(/bin/cat "$BACKUP/admin-name") || return 1
    valid_name "$ADMIN" || { fail 'Invalid backup account name.'; return 1; }
    build_paths
    local i=0 rel now expected
    for rel in "${PATHS[@]}"; do
        safe_path "$rel" || return 1
        expected=$(/bin/cat "$BACKUP/$i.after") || return 1
        if [ -f "$TARGET/$rel" ]; then now=$(digest "$TARGET/$rel") || return 1; else now=absent; fi
        [ "$now" = "$expected" ] || { fail "Managed file changed since apply; restore refused: $rel"; return 1; }
        i=$((i + 1))
    done
    local home="$TARGET/Users/$ADMIN"
    [ ! -L "$home" ] || { fail 'Home directory symlink refused.'; return 1; }
    if [ -d "$home" ]; then
        local first_entry
        first_entry=$(/usr/bin/find "$home" -mindepth 1 -print -quit) || return 1
        [ -z "$first_entry" ] || {
            fail 'The new account home contains data. Automated account rollback is refused.'; return 1;
        }
        CREATED_HOME=true
    fi
}

running_status() {
    local output rc=0
    output=$(profiles_status 2>&1) || rc=$?
    if [ "$rc" -ne 0 ]; then
        log "Enrollment query failed (exit $rc). Result: UNKNOWN, never interpreted as success."
        return 2
    fi
    printf '%s\n' "$output"
    log 'This describes the running OS. It does not prove release from server-side enrollment.'
}

main() {
    set -u
    set -o pipefail
    umask 077
    export PATH=/usr/bin:/bin:/usr/sbin:/sbin
    local command=${1:-help}
    [ "$#" -eq 0 ] || shift
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --data-volume|--create-admin|--backup-dir)
                [ "$#" -ge 2 ] && [ -n "$2" ] || { fail "Missing value for $1"; return 2; }
                case "$1" in --data-volume) TARGET=$2 ;; --create-admin) ADMIN=$2 ;; --backup-dir) BACKUP=$2 ;; esac
                shift 2 ;;
            *) fail "Unknown option: $1"; return 2 ;;
        esac
    done
    case "$command" in
        help|--help|-h) usage; return 0 ;;
        version|--version) printf '%s\n' "$VERSION"; return 0 ;;
        volumes|plan|apply|verify|restore|status) ;;
        *) fail "Unknown command: $command"; return 2 ;;
    esac
    require_macos || return 1
    case "$command" in
        volumes) /usr/sbin/diskutil apfs list; return $? ;;
        status) running_status; return $? ;;
    esac
    init_scratch || return 1
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    validate_target || return 1
    case "$command" in
        plan|apply)
            validate_fresh_install || return 1
            log "Target: $TARGET (APFS Data, $DEVICE_ID)"
            log "Plan: create admin '$ADMIN'; add three enrollment-domain entries; change four enrollment markers and setup-completion state."
            log 'No compatibility claim is made until device testing.'
            if [ "$command" = plan ]; then return 0; fi
            require_recovery || return 1
            [ -t 0 ] && [ -t 1 ] || { fail 'An interactive terminal is required for password entry.'; return 1; }
            acquire_lock || return 1
            apply_transaction || return 1 ;;
        verify) verify_local || return 1 ;;
        restore)
            require_recovery || return 1
            acquire_lock || return 1
            load_backup || return 1
            restore_snapshot || {
                fail "Restore incomplete. Keep the device in Recovery; backup and lock retained: $BACKUP; $LOCK"
                LOCK=''
                return 1
            }
            log 'Pre-change managed files restored. No reboot was performed.' ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main "$@"; fi

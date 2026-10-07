#!/bin/bash
# Read-only snapshot for comparison before/after a reboot, prompt, or update.
set -u

probe() {
    local label=$1 rc
    shift
    printf '\n--- %s ---\n' "$label"
    "$@" 2>&1
    rc=$?
    printf 'exit=%s\n' "$rc"
}

probe 'macOS version' /usr/bin/sw_vers
probe 'model' /usr/sbin/sysctl -n hw.model
probe 'boot time' /usr/sbin/sysctl kern.boottime
probe 'account' /usr/bin/id
probe 'enrollment status' /usr/bin/profiles status -type enrollment
probe 'installed system profiles' /usr/bin/profiles list -type configuration
probe 'Secure Token' /usr/sbin/sysadminctl -secureTokenStatus "$(/usr/bin/id -un)"
probe 'FileVault' /usr/bin/fdesetup status
probe 'hosts checksum' /usr/bin/shasum -a 256 /etc/hosts

printf '\n--- lab hosts block ---\n'
/usr/bin/grep -n -E 'mac-enrollment-lab|deviceenrollment\.apple\.com|mdmenrollment\.apple\.com|iprofiles\.apple\.com' /etc/hosts 2>&1
printf 'exit=%s\n' "$?"

printf '\n--- setup and enrollment markers ---\n'
for path in \
    /var/db/.AppleSetupDone \
    /var/db/ConfigurationProfiles/Settings/.cloudConfigProfileInstalled \
    /var/db/ConfigurationProfiles/Settings/.cloudConfigRecordNotFound \
    /var/db/ConfigurationProfiles/Settings/.cloudConfigHasActivationRecord \
    /var/db/ConfigurationProfiles/Settings/.cloudConfigRecordFound; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        /usr/bin/stat -f '%N size=%z modified=%m type=%HT' "$path" 2>&1
        printf 'stat_exit=%s\n' "$?"
    else
        printf '%s ABSENT\n' "$path"
    fi
done

printf '\n--- system resolver ---\n'
for host in deviceenrollment.apple.com mdmenrollment.apple.com iprofiles.apple.com; do
    printf 'name=%s\n' "$host"
    /usr/bin/dscacheutil -q host -a name "$host" 2>&1
    printf 'resolver_exit=%s\n' "$?"
done

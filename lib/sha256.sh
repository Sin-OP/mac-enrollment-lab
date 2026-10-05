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

"""Embed the checksum fallback, pin the core and refresh the Pages launcher.

Development-only: Python is not needed on the Recovery device.
"""
import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
START = '# BEGIN EMBEDDED SHA256'
END = '# END EMBEDDED SHA256'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    library = (ROOT / 'lib/sha256.sh').read_text().rstrip()
    block = START + '\n' + library + '\n' + END
    pattern = re.compile(re.escape(START) + r'.*?' + re.escape(END), re.S)
    core = (ROOT / 'enrollment-lab.sh').read_text()
    launcher = (ROOT / 'launcher.sh').read_text()
    assert len(pattern.findall(core)) == len(pattern.findall(launcher)) == 1
    core = pattern.sub(lambda _: block, core)
    launcher = pattern.sub(lambda _: block, launcher)
    version = re.search(r'^VERSION=([a-zA-Z0-9.-]+)$', core, re.M).group(1)
    checksum = hashlib.sha256(core.encode()).hexdigest()
    launcher = re.sub(r'^CORE_VERSION=.*$', 'CORE_VERSION=' + version, launcher, flags=re.M)
    launcher = re.sub(r'^CORE_URL=.*$',
                      f'CORE_URL=https://github.com/Sin-OP/mac-enrollment-lab/releases/download/v{version}/enrollment-lab.sh',
                      launcher, flags=re.M)
    launcher = re.sub(r'^CORE_SHA=.*$', 'CORE_SHA=' + checksum, launcher, flags=re.M)
    diagnostic = launcher.split('\nrun_core() {', 1)[0] + '\n' + (ROOT / 'diagnostic.sh').read_text()
    for relative, data in [('enrollment-lab.sh', core), ('launcher.sh', launcher),
                           ('docs/go', launcher), ('docs/go2', launcher), ('docs/go3', launcher),
                           ('docs/go4', launcher), ('docs/go5', launcher), ('docs/go6', launcher),
                           ('docs/go7', launcher),
                           ('docs/check', diagnostic)]:
        path = ROOT / relative
        if args.check:
            if path.read_text() != data:
                raise SystemExit(f'{relative} is stale; run python3 scripts/bundle.py')
        else:
            path.write_text(data)


if __name__ == '__main__':
    main()

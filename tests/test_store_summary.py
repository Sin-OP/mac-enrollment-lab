"""The Recovery store inspector reports structure without plist values."""
import plistlib
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs/store"


@unittest.skipUnless(Path('/usr/libexec/PlistBuddy').exists(), 'macOS PlistBuddy')
class StoreSummaryTests(unittest.TestCase):
    def inspect(self, fields):
        with tempfile.TemporaryDirectory() as td:
            volume = Path(td)
            store = volume / 'private/var/db/ConfigurationProfiles/Store'
            store.mkdir(parents=True)
            (store / 'MDM_ComputerPrefs.plist').write_bytes(plistlib.dumps(fields))
            return subprocess.run(['/bin/bash', str(SCRIPT), str(volume)],
                                  capture_output=True, text=True)

    def test_binary_data_shape_without_value(self):
        result = self.inspect({'MDMServerHash': b'private-server-hash'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Key count: 1', result.stdout)
        self.assertIn('MDMServerHash type: data', result.stdout)
        self.assertIn('MDMServerHash data: nonempty', result.stdout)
        self.assertNotIn('private-server-hash', result.stdout)
        self.assertNotIn('cHJpdmF0ZS1zZXJ2ZXItaGFzaA==', result.stdout)

    def test_extra_key_name_but_not_value(self):
        result = self.inspect({'MDMServerHash': b'abc', 'ExtraKey': 'private-value'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Key count: 2', result.stdout)
        self.assertIn('Other key name: ExtraKey', result.stdout)
        self.assertNotIn('private-value', result.stdout)

    def test_wrong_hash_type_without_value(self):
        result = self.inspect({'MDMServerHash': 'private-string'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MDMServerHash type: string', result.stdout)
        self.assertNotIn('private-string', result.stdout)


if __name__ == '__main__':
    unittest.main()

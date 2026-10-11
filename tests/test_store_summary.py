"""The Recovery store inspector reports structure without plist values."""
import plistlib
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs/store"


@unittest.skipUnless(Path('/usr/libexec/PlistBuddy').exists(), 'macOS PlistBuddy')
class StoreSummaryTests(unittest.TestCase):
    def inspect(self, fields, override=''):
        with tempfile.TemporaryDirectory() as td:
            volume = Path(td)
            store = volume / 'private/var/db/ConfigurationProfiles/Store'
            store.mkdir(parents=True)
            (store / 'MDM_ComputerPrefs.plist').write_bytes(plistlib.dumps(fields))
            if override:
                body = (f'source {shlex.quote(str(SCRIPT))}\n' + override + '\n'
                        f'inspect_store {shlex.quote(str(volume))}')
                command = ['/bin/bash', '-c', body]
            else:
                command = ['/bin/bash', str(SCRIPT), str(volume)]
            return subprocess.run(command, capture_output=True, text=True)

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

    def test_plain_plistbuddy_output_uses_read_only_plutil_fallback(self):
        result = self.inspect({'MDMServerHash': b'private-server-hash'},
                              "plistbuddy_xml() { printf 'Dict { private-server-hash }'; }")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('XML source: plutil XML', result.stdout)
        self.assertIn('MDMServerHash type: data', result.stdout)
        self.assertNotIn('private-server-hash', result.stdout)

    def test_missing_xml_reports_unknown_instead_of_absent(self):
        override = "plistbuddy_xml() { printf plain; }; plutil_xml() { return 1; }"
        result = self.inspect({'MDMServerHash': b'private-server-hash'}, override)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('key count and type UNKNOWN', result.stdout)
        self.assertNotIn('MDMServerHash type: absent', result.stdout)

    def test_empty_dictionary_is_identified_without_guessing_enrollment(self):
        result = self.inspect({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Top-level type: empty dictionary', result.stdout)
        self.assertIn('Key count: 0', result.stdout)
        self.assertIn('MDMServerHash type: absent', result.stdout)

    def test_empty_array_is_distinguished_from_empty_dictionary(self):
        result = self.inspect([])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Top-level type: empty array', result.stdout)
        self.assertIn('Key count: 0', result.stdout)


if __name__ == '__main__':
    unittest.main()

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from ml.data.release import content_digest, file_inventory, safe_path, verify_release


class ReleaseTests(unittest.TestCase):
    def seal(self, root):
        manifest = {'format_version': 1, 'files': file_inventory(root), 'training_approved': False}
        (root / 'release_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_relative_paths_cannot_escape_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ['../outside', 'a/../../outside', 'C:/outside', '/outside']:
                with self.assertRaises(ValueError):
                    safe_path(root, path)
            self.assertEqual(safe_path(root, 'stages/data.csv'), root / 'stages/data.csv')

    def test_content_hash_ignores_gzip_timestamp_but_preserves_values(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / 'a.csv.gz', Path(directory) / 'b.csv.gz'
            a.write_bytes(gzip.compress(b'value\n6\n', mtime=1))
            b.write_bytes(gzip.compress(b'value\n6\n', mtime=2))
            self.assertEqual(content_digest(a), content_digest(b))
            b.write_bytes(gzip.compress(b'value\n7\n', mtime=2))
            self.assertNotEqual(content_digest(a), content_digest(b))

    def test_verifier_detects_changed_missing_and_added_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data.csv'
            data.write_text('value\n6\n', encoding='utf-8')
            self.seal(root)
            verify_release(root)
            data.write_text('value\n7\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_release(root)
            data.unlink()
            with self.assertRaises(ValueError):
                verify_release(root)
            data.write_text('value\n6\n', encoding='utf-8')
            (root / 'unexpected.csv').write_text('extra', encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_release(root)

    def test_manifest_cannot_redirect_verifier_outside_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'release_manifest.json').write_text(json.dumps({'format_version': 1,
                'files': {'../outside': {'sha256': '0' * 64, 'bytes': 0}}}), encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_release(root)


if __name__ == '__main__':
    unittest.main()

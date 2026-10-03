import importlib.util
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('submission', pathlib.Path(__file__).parents[1] / 'scripts/submit_database.py')
submission = importlib.util.module_from_spec(spec)
spec.loader.exec_module(submission)


class Submission(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def init(self, root):
        root.mkdir()
        self.git(root, 'init', '-q')
        self.git(root, 'config', 'user.name', 'Test')
        self.git(root, 'config', 'user.email', 'test@example.org')
        return root

    def test_preview_and_stable_channel_selection(self):
        for version in ('0.1.3', '1.0.0', '1.0.0+preview-build'):
            self.assertEqual(submission.channel(version), 'main')
        for version in ('0.1.4-preview.1', '1.0.0-alpha', '1.0.0-beta.2', '1.0.0-rc.1'):
            self.assertEqual(submission.channel(version), 'testing')
        for version in ('v1.0.0', 'preview', '../1.0.0', '1.0'):
            with self.assertRaises(ValueError):
                submission.channel(version)

    def test_pins_release_commit_preserves_other_modules_and_retries_without_diff(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'GIT_ALLOW_PROTOCOL': 'file'}):
            root = pathlib.Path(temporary)
            plugin = self.init(root / 'plugin')
            (plugin / 'manifest.json').write_text('{}')
            self.git(plugin, 'add', '.')
            self.git(plugin, 'commit', '-qm', 'Release')
            released = self.git(plugin, 'rev-parse', 'HEAD')
            (plugin / 'manifest.json').write_text('{"new":true}')
            self.git(plugin, 'commit', '-qam', 'Unreleased changes')
            newer = self.git(plugin, 'rev-parse', 'HEAD')
            database = self.init(root / 'database')
            (database / 'README.md').write_text('Development only')
            self.git(database, 'submodule', 'add', str(plugin), 'plugins/other.plugin')
            self.git(database, 'add', '.')
            self.git(database, 'commit', '-qm', 'Other plugin')
            unrelated = self.git(database, 'rev-parse', 'HEAD:plugins/other.plugin')
            path = submission.prepare(database, str(plugin), released, 'tooru.passthrough-color')
            self.assertEqual(self.git(database, 'rev-parse', ':' + path), released)
            self.assertEqual(self.git(database, 'rev-parse', ':plugins/other.plugin'), unrelated)
            self.assertEqual(self.git(database, 'diff', '--cached', '--name-only').splitlines(), ['.gitmodules', path])
            self.git(database, 'commit', '-qm', 'Register release')
            submission.prepare(database, str(plugin), released, 'tooru.passthrough-color')
            self.assertEqual(self.git(database, 'diff', '--cached', '--name-only'), '')
            submission.prepare(database, str(plugin), newer, 'tooru.passthrough-color')
            self.assertEqual(self.git(database, 'diff', '--cached', '--name-only'), path)
            self.assertEqual(self.git(database, 'rev-parse', ':' + path), newer)
            with self.assertRaises(ValueError):
                submission.prepare(database, str(root / 'foreign'), released, 'tooru.passthrough-color')


if __name__ == '__main__':
    unittest.main()

"""Packaging invariants shared by Codex, Claude Code, and a copied plugin cache."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PluginPackageTest(unittest.TestCase):
    def load(self, path):
        return json.loads((ROOT / path).read_text())

    def test_hosts_share_the_same_identity_and_release(self):
        manifests = [self.load(p) for p in ['plugin.json', '.codex-plugin/plugin.json', '.claude-plugin/plugin.json']]
        self.assertEqual({m['name'] for m in manifests}, {'pr-visual-review'})
        self.assertEqual(len({m['version'] for m in manifests}), 1)
        self.assertRegex(manifests[0]['version'], r'^\d+\.\d+\.\d+$')
        self.assertEqual(manifests[0]['$schema'], 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json')
        for manifest in manifests:
            self.assertNotIn('hooks', manifest)
            self.assertNotIn('mcpServers', manifest)

    def test_both_catalogs_resolve_this_plugin_not_an_external_directory(self):
        codex = self.load('.agents/plugins/marketplace.json')
        claude = self.load('.claude-plugin/marketplace.json')
        self.assertEqual(codex['name'], claude['name'])
        self.assertEqual(len(codex['plugins']), 1)
        self.assertEqual(len(claude['plugins']), 1)
        for entry in [codex['plugins'][0], claude['plugins'][0]]:
            self.assertEqual(entry['name'], 'pr-visual-review')
            path = entry['source']['path'] if isinstance(entry['source'], dict) else entry['source']
            self.assertEqual((ROOT / path).resolve(), ROOT)
        self.assertEqual(codex['plugins'][0]['policy']['installation'], 'AVAILABLE')
        self.assertNotIn('version', claude['plugins'][0])

    def test_plugin_skill_is_a_real_directory(self):
        skill = ROOT / 'skills/pr-visual-review'
        self.assertFalse(skill.is_symlink())
        self.assertTrue((skill / 'SKILL.md').is_file())
        self.assertFalse((ROOT / 'pr-visual-review').exists(), 'the old root-level alias was removed in 0.1.2')

    def test_copied_package_can_load_the_skill_helpers_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            # Codex cache copying skips symlinks. Required resources must be real files.
            def ignore_links(directory, names):
                return [name for name in names if name == '__pycache__' or (Path(directory) / name).is_symlink()]
            for name in ['.codex-plugin', '.claude-plugin', 'skills']:
                shutil.copytree(ROOT / name, cache / name, ignore=ignore_links)
            shutil.copy2(ROOT / 'plugin.json', cache / 'plugin.json')
            skill = cache / 'skills/pr-visual-review'
            self.assertTrue(skill.resolve().is_relative_to(cache.resolve()))
            for relative in ['assets/labels.en.json', 'assets/report.css', 'references/annotations.md',
                             'scripts/image_annotations.py', 'requirements-annotations.txt']:
                self.assertTrue((skill / relative).is_file(), relative)
            process = subprocess.run([sys.executable, str(skill / 'scripts/review.py'), '--help'],
                                     cwd=cache, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == '__main__': unittest.main()

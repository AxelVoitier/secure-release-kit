# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Check that maintenance services can discover the pins in both layouts."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaintenanceConfigTests(unittest.TestCase):
    def test_original_and_deployed_configs_discover_every_manual_pin(self) -> None:
        original = json.loads((ROOT / '.github/renovate.json').read_text())
        deployed = json.loads((ROOT / 'template/_github/renovate.json').read_text())
        self.assertEqual(original, deployed)
        self.assertFalse(original['automerge'])

        expected = {
            'python': 2,
            'uv': 3,
            'cyclonedx-bom': 1,
            'pypi-attestations': 1,
        }
        for prefix in ('template/_github', '.github'):
            found = dict.fromkeys(expected, 0)
            for name in ('build', 'release', 'ci'):
                relative = f'{prefix}/workflows/{name}.yml'
                source = (ROOT / 'template/_github/workflows' / f'{name}.yml').read_text()
                for manager in original['customManagers']:
                    pattern = manager['managerFilePatterns'][0].strip('/')
                    if not re.search(pattern, relative):
                        continue
                    for match_string in manager['matchStrings']:
                        python_pattern = match_string.replace(
                            '(?<currentValue>', '(?P<currentValue>'
                        )
                        matches = re.findall(python_pattern, source)
                        found[manager['depNameTemplate']] += len(matches)
            self.assertEqual(found, expected, prefix)

    def test_uv_managers_accept_bare_release_tags(self) -> None:
        config = json.loads((ROOT / '.github/renovate.json').read_text())
        for manager in config['customManagers']:
            if manager['depNameTemplate'] != 'uv':
                continue
            # github-releases supplies the bare tag as the version.
            extractor = manager.get('extractVersionTemplate', '(?<version>.*)')
            match = re.fullmatch(extractor.replace('(?<version>', '(?P<version>'), '0.8.17')
            if match is None:
                self.fail('uv manager rejected a bare release tag')
            self.assertEqual(match['version'], '0.8.17')

    def test_nested_actions_match_renovate_builtin_file_pattern(self) -> None:
        config = json.loads((ROOT / '.github/renovate.json').read_text())
        nested_pattern = config['github-actions']['managerFilePatterns'][0].strip('/')
        self.assertRegex('template/_github/workflows/build.yml', nested_pattern)
        # Renovate's built-in manager finds the deployed .github layout.
        deployed_pattern = (
            r'(^|/)(workflow-templates|\.(?:github|gitea|forgejo)/(?:workflows|actions))/.+\.ya?ml$'
        )
        self.assertRegex('.github/workflows/build.yml', deployed_pattern)
        source = (ROOT / 'template/_github/workflows/build.yml').read_text()
        self.assertRegex(source, r'uses: actions/checkout@[0-9a-f]{40}')


if __name__ == '__main__':
    unittest.main()

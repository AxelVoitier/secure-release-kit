# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Exercise real workflow steps with local inputs and the gh test double."""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_testpypi_only as prepare  # noqa: E402

WORKFLOW = ROOT / 'template/_github/workflows/release.yml'
RUNSTEP = ROOT / 'tools/runstep.py'


class PortableStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'
        self.work = self.base / 'work'
        self.work.mkdir()
        self.fix = self.base / 'fix'
        self.fix.mkdir()

    def step(self, job: str, name: str, **values: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            STATE=str(self.state),
            WORKDIR=str(self.work),
            FIX=str(self.fix),
            GHLOG=str(self.base / 'gh.log'),
            PATH=f'{ROOT / "tests/bin"}:{env["PATH"]}',
        )
        return subprocess.run(
            [
                sys.executable,
                str(RUNSTEP),
                str(WORKFLOW),
                job,
                name,
                *(f'{key}={value}' for key, value in values.items()),
            ],
            check=False,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_canonical_tag_accepts_prerelease(self) -> None:
        result = self.step(
            'origin-check',
            'tag',
            TAG='v1.2rc3',
            GITHUB_REF='refs/tags/v1.2rc3',
            GH_TOKEN='fixture',
            DEFAULT_BRANCH='main',
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('version=1.2rc3', (self.state / 'outputs').read_text())
        self.assertIn('prerelease=true', (self.state / 'outputs').read_text())

    def test_noncanonical_tag_fails(self) -> None:
        result = self.step(
            'origin-check',
            'tag',
            TAG='v01.2',
            GITHUB_REF='refs/tags/v01.2',
            GH_TOKEN='fixture',
            DEFAULT_BRANCH='main',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not v + a canonical PEP 440 version', result.stdout)

    def compare_ci_wheel(
        self, runs: str, wheel: str, digest: str
    ) -> subprocess.CompletedProcess[str]:
        return self.step(
            'publish-testpypi',
            'Check CI tested these wheel bytes',
            CI_RUNS=runs,
            WHEEL=wheel,
            WHEEL_SHA256=digest,
            GITHUB_REPOSITORY='example/repo',
            GH_TOKEN='fixture',
            INDEX='https://test.pypi.org',
            UPLOAD_URL='https://test.pypi.org/legacy/',
            SDIST='example-1.tar.gz',
            SDIST_SHA256=digest,
            VERSION='1',
        )

    def test_ci_wheel_bytes_match(self) -> None:
        wheel = 'example-1-py3-none-any.whl'
        contents = b'wheel bytes'
        fixture = self.fix / 'run-123-wheel'
        fixture.mkdir()
        (fixture / wheel).write_bytes(contents)
        digest = hashlib.sha256(contents).hexdigest()
        result = self.compare_ci_wheel('123', wheel, digest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_wheel_mismatch_fails(self) -> None:
        wheel = 'example-1-py3-none-any.whl'
        fixture = self.fix / 'run-123-wheel'
        fixture.mkdir()
        (fixture / wheel).write_bytes(b'wrong wheel')
        result = self.compare_ci_wheel('123', wheel, '0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('tested a different', result.stdout)

    def test_ci_missing_run_fails(self) -> None:
        result = self.compare_ci_wheel('', 'example-1-py3-none-any.whl', '0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no CI run', result.stdout)

    def test_act_expansion_changes_only_self_repository_calls(self) -> None:
        for source in sorted(WORKFLOW.parent.glob('*.yml')):
            with self.subTest(workflow=source.name):
                expanded = self.base / source.name
                shutil.copy2(source, expanded)
                subprocess.run(
                    [sys.executable, str(ROOT / 'tools/expand_anchors.py'), str(expanded)],
                    check=True,
                )
                original_yaml = yaml.safe_load(source.read_text())
                # Reverse only the self-repository syntax rewrite before comparing the documents.
                expanded_source = expanded.read_text().replace(
                    'uses: ./.github/workflows/build.yml', 'uses: $/.github/workflows/build.yml'
                )
                self.assertEqual(yaml.safe_load(expanded_source), original_yaml)

    def test_failed_hosted_copy_leaves_destination_available_for_retry(self) -> None:
        target = self.base / 'hosted'
        with patch.object(sys, 'argv', ['prepare', str(target)]):
            with (
                patch.object(prepare.shutil, 'copy2', side_effect=OSError('copy failed')),
                self.assertRaises(OSError),
            ):
                prepare.main()
            self.assertFalse(target.exists())
            with (
                patch.object(prepare.yaml, 'safe_load', side_effect=yaml.YAMLError('bad YAML')),
                self.assertRaises(yaml.YAMLError),
            ):
                prepare.main()
            self.assertFalse(target.exists())

    def test_checkout_stub_requires_an_empty_workspace(self) -> None:
        action = yaml.safe_load((ROOT / 'tests/stubs/checkout/action.yml').read_text())
        script = action['runs']['steps'][0]['run']
        # A local tagged fixture supplies the history required by git describe.
        subprocess.run(['git', 'init', '-q', str(self.fix)], check=True)
        subprocess.run(
            ['git', 'fetch', '--quiet', '--no-tags', str(ROOT), 'HEAD:refs/tags/v1'],
            cwd=self.fix,
            check=True,
        )
        revision = subprocess.check_output(
            ['git', 'rev-parse', 'refs/tags/v1'], cwd=self.fix, text=True
        ).strip()
        env = dict(os.environ, ACT_SRC=str(self.fix), GITHUB_SHA=revision)
        sentinel = self.work / 'local-work'
        sentinel.write_text('keep')
        command = ['bash', '-eo', 'pipefail', '-c', script]
        result = subprocess.run(command, check=False, cwd=self.work, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.assertFalse((self.work / '.git').exists())
        fresh = self.base / 'empty'
        fresh.mkdir()
        result = subprocess.run(command, check=False, cwd=fresh, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=fresh, text=True).strip(),
            revision,
        )

    def test_gh_double_rejects_unknown_commands_and_failed_downloads(self) -> None:
        gh = str(ROOT / 'tests/bin/gh')
        env = dict(os.environ, FIX=str(self.fix), GHLOG=str(self.base / 'gh.log'))
        result = subprocess.run([gh, 'unsupported'], check=False, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        (self.fix / 'run-123-wheel').mkdir()
        occupied = self.work / 'file'
        occupied.touch()
        result = subprocess.run(
            [gh, 'run', 'download', '123', '--name', 'wheel', '--dir', str(occupied)],
            check=False,
            env=env,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_testpypi_copy_is_separate_and_has_no_pypi_upload(self) -> None:
        original = WORKFLOW.read_bytes()
        target = self.base / 'hosted'
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools/prepare_testpypi_only.py'), str(target)],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(WORKFLOW.read_bytes(), original)
        jobs = yaml.safe_load((target / '.github/workflows/release.yml').read_text())['jobs']
        self.assertFalse(jobs['publish-testpypi']['if'])
        self.assertFalse(jobs['verify-testpypi']['if'])
        self.assertEqual(jobs['publish-pypi']['env']['UPLOAD_URL'], 'https://test.pypi.org/legacy/')
        self.assertEqual(jobs['verify-pypi']['env']['INDEX'], 'https://test.pypi.org')


if __name__ == '__main__':
    unittest.main()

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
from unittest.mock import patch
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "template/_github/workflows/release.yml"
RUNSTEP = ROOT / "tools/runstep.py"


class PortableStepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / "state"
        self.work = self.base / "work"
        self.work.mkdir()
        self.fix = self.base / "fix"
        self.fix.mkdir()

    def step(self, job, name, **values):
        env = os.environ.copy()
        env.update(STATE=str(self.state), WORKDIR=str(self.work), FIX=str(self.fix),
                   GHLOG=str(self.base / "gh.log"), PATH=f"{ROOT / 'tests/bin'}:{env['PATH']}")
        return subprocess.run(
            [sys.executable, str(RUNSTEP), str(WORKFLOW), job, name,
             *(f"{key}={value}" for key, value in values.items())],
            cwd=ROOT, env=env, text=True, capture_output=True,
        )

    def test_canonical_tag_accepts_prerelease(self):
        result = self.step("origin-check", "tag", TAG="v1.2rc3", GITHUB_REF="refs/tags/v1.2rc3",
                           GH_TOKEN="fixture", DEFAULT_BRANCH="main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("version=1.2rc3", (self.state / "outputs").read_text())
        self.assertIn("prerelease=true", (self.state / "outputs").read_text())

    def test_noncanonical_tag_fails(self):
        result = self.step("origin-check", "tag", TAG="v01.2", GITHUB_REF="refs/tags/v01.2",
                           GH_TOKEN="fixture", DEFAULT_BRANCH="main")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not v + a canonical PEP 440 version", result.stdout)

    def test_ci_wheel_bytes_match(self):
        wheel = "example-1-py3-none-any.whl"
        contents = b"wheel bytes"
        fixture = self.fix / "run-123-wheel"
        fixture.mkdir()
        (fixture / wheel).write_bytes(contents)
        digest = hashlib.sha256(contents).hexdigest()
        result = self.step("publish-testpypi", "Check CI tested these wheel bytes",
                           CI_RUNS="123", WHEEL=wheel, WHEEL_SHA256=digest,
                           GITHUB_REPOSITORY="example/repo", GH_TOKEN="fixture",
                           INDEX="https://test.pypi.org", UPLOAD_URL="https://test.pypi.org/legacy/",
                           SDIST="example-1.tar.gz", SDIST_SHA256=digest, VERSION="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ci_wheel_mismatch_fails(self):
        wheel = "example-1-py3-none-any.whl"
        fixture = self.fix / "run-123-wheel"
        fixture.mkdir()
        (fixture / wheel).write_bytes(b"wrong wheel")
        result = self.step("publish-testpypi", "Check CI tested these wheel bytes",
                           CI_RUNS="123", WHEEL=wheel, WHEEL_SHA256="0" * 64,
                           GITHUB_REPOSITORY="example/repo", GH_TOKEN="fixture",
                           INDEX="https://test.pypi.org", UPLOAD_URL="https://test.pypi.org/legacy/",
                           SDIST="example-1.tar.gz", SDIST_SHA256="0" * 64, VERSION="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tested a different", result.stdout)

    def test_ci_missing_run_fails(self):
        result = self.step("publish-testpypi", "Check CI tested these wheel bytes",
                           CI_RUNS="", WHEEL="example-1-py3-none-any.whl", WHEEL_SHA256="0" * 64,
                           GITHUB_REPOSITORY="example/repo", GH_TOKEN="fixture",
                           INDEX="https://test.pypi.org", UPLOAD_URL="https://test.pypi.org/legacy/",
                           SDIST="example-1.tar.gz", SDIST_SHA256="0" * 64, VERSION="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no CI run", result.stdout)

    def test_act_expansion_changes_only_self_repository_calls(self):
        expanded = self.base / "release.yml"
        shutil.copy2(WORKFLOW, expanded)
        subprocess.run([sys.executable, str(ROOT / "tools/expand_anchors.py"), str(expanded)],
                       check=True)
        original_yaml = yaml.safe_load(WORKFLOW.read_text())
        expanded_yaml = yaml.safe_load(expanded.read_text())

        def normalise(value):
            if isinstance(value, dict):
                return {key: normalise(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalise(item) for item in value]
            if isinstance(value, str):
                return value.replace("./.github/workflows/build.yml", "$/.github/workflows/build.yml")
            return value

        self.assertEqual(normalise(expanded_yaml), original_yaml)

    def test_failed_hosted_copy_leaves_destination_available_for_retry(self):
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import prepare_testpypi_only as prepare
        finally:
            sys.path.pop(0)
        target = self.base / "hosted"
        with patch.object(sys, "argv", ["prepare", str(target)]):
            with patch.object(prepare.shutil, "copy2", side_effect=OSError("copy failed")):
                with self.assertRaises(OSError):
                    prepare.main()
            self.assertFalse(target.exists())
            with patch.object(prepare.yaml, "safe_load", side_effect=yaml.YAMLError("bad YAML")):
                with self.assertRaises(yaml.YAMLError):
                    prepare.main()
            self.assertFalse(target.exists())

    def test_checkout_stub_requires_an_empty_workspace(self):
        action = yaml.safe_load((ROOT / "tests/stubs/checkout/action.yml").read_text())
        script = action["runs"]["steps"][0]["run"]
        # A local tagged fixture supplies the history required by git describe.
        subprocess.run(["git", "init", "-q", str(self.fix)], check=True)
        subprocess.run(["git", "fetch", "--quiet", "--no-tags", str(ROOT), "HEAD:refs/tags/v1"],
                       cwd=self.fix, check=True)
        revision = subprocess.check_output(["git", "rev-parse", "refs/tags/v1"], cwd=self.fix,
                                           text=True).strip()
        env = dict(os.environ, ACT_SRC=str(self.fix), GITHUB_SHA=revision)
        sentinel = self.work / "local-work"
        sentinel.write_text("keep")
        command = ["bash", "-eo", "pipefail", "-c", script]
        result = subprocess.run(command, cwd=self.work, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertFalse((self.work / ".git").exists())
        fresh = self.base / "empty"
        fresh.mkdir()
        result = subprocess.run(command, cwd=fresh, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fresh,
                                                 text=True).strip(), revision)

    def test_gh_double_rejects_unknown_commands_and_failed_downloads(self):
        gh = str(ROOT / "tests/bin/gh")
        env = dict(os.environ, FIX=str(self.fix), GHLOG=str(self.base / "gh.log"))
        result = subprocess.run([gh, "unsupported"], env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        (self.fix / "run-123-wheel").mkdir()
        occupied = self.work / "file"
        occupied.touch()
        result = subprocess.run([gh, "run", "download", "123", "--name", "wheel", "--dir", str(occupied)],
                                env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_testpypi_copy_is_separate_and_has_no_pypi_upload(self):
        original = WORKFLOW.read_bytes()
        target = self.base / "hosted"
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/prepare_testpypi_only.py"), str(target)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(WORKFLOW.read_bytes(), original)
        jobs = yaml.safe_load((target / ".github/workflows/release.yml").read_text())["jobs"]
        self.assertFalse(jobs["publish-testpypi"]["if"])
        self.assertFalse(jobs["verify-testpypi"]["if"])
        self.assertEqual(jobs["publish-pypi"]["env"]["UPLOAD_URL"],
                         "https://test.pypi.org/legacy/")
        self.assertEqual(jobs["verify-pypi"]["env"]["INDEX"], "https://test.pypi.org")


if __name__ == "__main__":
    unittest.main()

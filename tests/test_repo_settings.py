# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""The setup preview and audit must preserve their mutation boundary."""

import base64
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import repo_settings as settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.signer = b"alice public key\n"

    def fake_api(self, path: str, method: str = "GET", data=None):
        self.calls.append((method, path))
        if method != "GET":
            raise AssertionError("preview and validation tried to write")
        if path == "repos/acme/widget":
            return {"full_name": "acme/widget", "default_branch": "main", "permissions": {"admin": True}}
        if path.startswith("users/"):
            return {"id": 42}
        if "/deployment-branch-policies" in path:
            return {"branch_policies": [{"id": 7, "type": "branch", "name": "main"}]}
        if path.endswith("/environments/testpypi") or path.endswith("/environments/pypi"):
            return {"deployment_branch_policy": {"custom_branch_policies": False},
                    "can_admins_bypass": True, "protection_rules": []}
        if path == "repos/acme/widget/contents/.github?ref=main":
            return [{"name": "release-signers.asc"}]
        if path == "repos/acme/widget/contents/.github/release-signers.asc?ref=main":
            return {"type": "file", "encoding": "base64",
                    "content": base64.b64encode(self.signer).decode()}
        if path == "repos/acme/widget/actions/variables/RELEASE_SIGNERS_SHA256":
            raise settings.SetupError("HTTP 404: Not Found")
        raise AssertionError(path)

    def test_preview_lists_only_future_mutations(self) -> None:
        with patch.object(settings, "api", side_effect=self.fake_api), \
             patch.object(settings, "rulesets", return_value=[]):
            changes, operations = settings.settings_report(
                "acme/widget", reviewer=["alice"], prevent_self_review=False)
        self.assertTrue(any("DELETE" in change and "/7" in change for change in changes))
        self.assertTrue(any("RELEASE_SIGNERS_SHA256" in change for change in changes))
        self.assertEqual(len(changes), len(operations))
        self.assertTrue(all(method == "GET" for method, _ in self.calls))

    def test_audit_reports_missing_controls_without_writes(self) -> None:
        with patch.object(settings, "api", side_effect=self.fake_api), \
             patch.object(settings, "gh", return_value=[[]]) as read_rules, \
             patch.object(settings, "rulesets", return_value=[]):
            failures = settings.validate("acme/widget")
        read_rules.assert_called_once_with("api", "repos/acme/widget/rules/branches/main", "--paginate", "--slurp")
        self.assertTrue(any("reviewers" in failure for failure in failures))
        self.assertTrue(any("default branch" in failure for failure in failures))
        self.assertTrue(any("immutability" in failure for failure in failures))
        self.assertTrue(all(method == "GET" for method, _ in self.calls))

    def test_invalid_target_is_rejected_before_api(self) -> None:
        for repo in ("widget", "acme/widget/other", "acme/../widget"):
            with self.assertRaises(settings.SetupError):
                settings.require_repo(repo)

    def test_complete_audit_passes(self) -> None:
        current_env = {"deployment_branch_policy": {"custom_branch_policies": True},
                       "can_admins_bypass": False,
                       "protection_rules": [{"type": "required_reviewers",
                                             "reviewers": [{"reviewer": {"id": 42}}]}]}
        policies = [{"type": "tag", "name": "v*"}]
        rules = [dict(settings.desired_rule(name), enforcement="active") for name in settings.RULE_NAMES]
        with patch.object(settings, "repo_info", return_value={"default_branch": "main",
                                                               "permissions": {"admin": True}}), \
             patch.object(settings, "environment", return_value=(current_env, policies)), \
             patch.object(settings, "rulesets", return_value=rules), \
             patch.object(settings, "gh", return_value=[[{"type": "pull_request"}]]), \
             patch.object(settings, "remote_signers", return_value="digest  .github/release-signers"), \
             patch.object(settings, "variable", return_value="digest  .github/release-signers"):
            self.assertEqual(settings.validate("acme/widget"), [])

    def test_missing_gh_is_a_prerequisite_error(self) -> None:
        with patch.object(settings.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(settings.SetupError, "gh is missing"):
                settings.gh("api", "repos/acme/widget")


if __name__ == "__main__":
    unittest.main()

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Preview, apply, and inspect the GitHub settings used by the release kit."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from typing import Any
from urllib.parse import quote


REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
RULE_NAMES = ("release tags: creation", "release tags: immutable")


class SetupError(Exception):
    """An input, prerequisite, or remote setting prevents the requested work."""


def gh(*args: str, data: dict[str, Any] | None = None) -> Any:
    command = ["gh", *args]
    if data is not None:
        command += ["--input", "-"]
    try:
        result = subprocess.run(
            command, input=json.dumps(data) if data is not None else None,
            text=True, capture_output=True, check=False,
        )
    except FileNotFoundError as exc:
        raise SetupError("gh is missing; install GitHub CLI first") from exc
    if result.returncode:
        raise SetupError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError(f"gh {' '.join(args)} returned invalid JSON") from exc


def api(path: str, method: str = "GET", data: dict[str, Any] | None = None) -> Any:
    return gh("api", "-X", method, path, data=data)


def require_repo(repo: str) -> str:
    if not REPO.fullmatch(repo) or ".." in repo:
        raise SetupError("--repo must be OWNER/REPO")
    return repo


def repo_info(repo: str) -> dict[str, Any]:
    info = api(f"repos/{repo}")
    if info.get("full_name", "").casefold() != repo.casefold():
        raise SetupError(f"GitHub returned a different repository for {repo}")
    return info


def environment(repo: str, name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    path = f"repos/{repo}/environments/{name}"
    try:
        current = api(path)
    except SetupError as exc:
        if "HTTP 404" in str(exc):
            return None, []
        raise
    if not (current.get("deployment_branch_policy") or {}).get("custom_branch_policies"):
        return current, []
    pages = gh("api", f"{path}/deployment-branch-policies", "--paginate", "--slurp")
    return current, [policy for page in pages for policy in page["branch_policies"]]


def rulesets(repo: str, *, include_parents: bool = True) -> list[dict[str, Any]]:
    query = f"?includes_parents={str(include_parents).lower()}"
    summary = gh("api", f"repos/{repo}/rulesets{query}", "--paginate", "--slurp")
    rows = [item for page in summary for item in page]
    return [api(f"repos/{repo}/rulesets/{row['id']}") for row in rows]


def desired_rule(name: str) -> dict[str, Any]:
    creation = name == RULE_NAMES[0]
    return {
        "name": name, "target": "tag", "enforcement": "active",
        "bypass_actors": ([{"actor_id": 5, "actor_type": "RepositoryRole",
                            "bypass_mode": "always"}] if creation else []),
        "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
        "rules": [{"type": kind} for kind in
                  (["creation"] if creation else ["update", "deletion", "non_fast_forward"])],
    }


def remote_signers(repo: str, branch: str) -> str:
    prefix = f"repos/{repo}/contents/.github"
    entries = api(f"{prefix}?ref={quote(branch, safe='')}")
    names = sorted(item["name"] for item in entries if item["name"].startswith("release-signers"))
    if not names or any(name not in ("release-signers", "release-signers.asc") for name in names):
        raise SetupError("default branch needs only .github/release-signers and/or .github/release-signers.asc")
    lines = []
    for name in names:
        item = api(f"{prefix}/{name}?ref={quote(branch, safe='')}")
        if item.get("type") != "file" or item.get("encoding") != "base64":
            raise SetupError(f"cannot read committed signer file {name}")
        digest = hashlib.sha256(base64.b64decode(item["content"])).hexdigest()
        lines.append(f"{digest}  .github/{name}")
    return "\n".join(lines)


def variable(repo: str) -> str | None:
    try:
        return api(f"repos/{repo}/actions/variables/RELEASE_SIGNERS_SHA256").get("value")
    except SetupError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def reviewer_id(login: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9-]+", login):
        raise SetupError(f"invalid reviewer login: {login}")
    return int(api(f"users/{login}")["id"])


def settings_report(repo: str, *, reviewer: list[str], prevent_self_review: bool) -> tuple[list[str], list[tuple[str, Any]]]:
    """Return readable changes and operations; this function does not write settings."""
    info = repo_info(repo)
    if not info.get("permissions", {}).get("admin"):
        raise SetupError("the gh account needs repository admin access")
    changes: list[str] = []
    operations: list[tuple[str, Any]] = []
    for name in ("testpypi", "pypi"):
        current, policies = environment(repo, name)
        reviewers = ([{"type": "User", "id": reviewer_id(login)} for login in reviewer]
                     if name == "pypi" else [])
        body: dict[str, Any] = {
            "deployment_branch_policy": {"protected_branches": False,
                                         "custom_branch_policies": True},
        }
        if name == "pypi":
            body.update(reviewers=reviewers, prevent_self_review=prevent_self_review,
                        can_admins_bypass=False)
        review_rules = [rule for rule in (current or {}).get("protection_rules", [])
                        if rule.get("type") == "required_reviewers"]
        existing_reviewers = [r for rule in review_rules for r in rule.get("reviewers", [])]
        existing_ids = sorted((r.get("type"), r.get("reviewer", {}).get("id"))
                              for r in existing_reviewers)
        wanted_ids = sorted((r["type"], r["id"]) for r in reviewers)
        existing_self_review = (review_rules[0].get("prevent_self_review", False)
                                if review_rules else False)
        needs_update = (current is None or
                        current.get("deployment_branch_policy") != body["deployment_branch_policy"] or
                        (name == "pypi" and (existing_ids != wanted_ids or
                         existing_self_review != prevent_self_review or
                         current.get("can_admins_bypass") is not False)))
        path = f"repos/{repo}/environments/{name}"
        if needs_update:
            changes.append(f"PUT {path}: {json.dumps(body, sort_keys=True)}")
            operations.append(("api", (path, "PUT", body)))
        keep = [p for p in policies if p.get("type") == "tag" and p.get("name") == "v*"]
        for policy in policies:
            if policy not in keep or policy is not keep[0]:
                target = f"{path}/deployment-branch-policies/{policy['id']}"
                changes.append(f"DELETE {target}: {policy.get('type')} {policy.get('name')}")
                operations.append(("api", (target, "DELETE", None)))
        if not keep:
            target = f"{path}/deployment-branch-policies"
            body_policy = {"name": "v*", "type": "tag"}
            changes.append(f"POST {target}: {json.dumps(body_policy)}")
            operations.append(("api", (target, "POST", body_policy)))
    existing = [r for r in rulesets(repo, include_parents=False) if r.get("target") == "tag"]
    for name in RULE_NAMES:
        matches = [r for r in existing if r.get("name") == name]
        if len(matches) > 1:
            raise SetupError(f"more than one active ruleset named {name}")
        desired = desired_rule(name)
        current = matches[0] if matches else None
        fields = desired.keys()
        if current is None or any(current.get(key) != desired[key] for key in fields):
            method = "PUT" if current else "POST"
            path = f"repos/{repo}/rulesets" + (f"/{current['id']}" if current else "")
            changes.append(f"{method} {path}: {json.dumps(desired, sort_keys=True)}")
            operations.append(("api", (path, method, desired)))
    expected = remote_signers(repo, info["default_branch"])
    if variable(repo) != expected:
        changes.append(f"SET RELEASE_SIGNERS_SHA256 in {repo} to:\n{expected}")
        operations.append(("variable", expected))
    return changes, operations


def validate(repo: str) -> list[str]:
    failures: list[str] = []
    info = repo_info(repo)
    if not info.get("permissions", {}).get("admin"):
        raise SetupError("the gh account needs repository admin access to audit bypass lists")
    for name in ("testpypi", "pypi"):
        current, policies = environment(repo, name)
        if current is None or (current.get("deployment_branch_policy") or {}).get("custom_branch_policies") is not True:
            failures.append(f"{name}: custom deployment policy missing")
        if len(policies) != 1 or policies[0].get("type") != "tag" or policies[0].get("name") != "v*":
            failures.append(f"{name}: expected exactly one v* tag policy")
        if name == "pypi" and current:
            required = [rule for rule in current.get("protection_rules", [])
                        if rule.get("type") == "required_reviewers" and rule.get("reviewers")]
            if not required:
                failures.append("pypi: required reviewers missing")
            if current.get("can_admins_bypass") is not False:
                failures.append("pypi: administrator bypass must be disabled")
    all_rules = [r for r in rulesets(repo) if r.get("enforcement") == "active"]
    # GitHub resolves ref patterns, exclusions and inherited rules for this branch.
    branch = quote(info["default_branch"], safe="")
    pages = gh("api", f"repos/{repo}/rules/branches/{branch}", "--paginate", "--slurp")
    if not any(pages):
        failures.append("default branch has no effective ruleset rules; inspect branch protection manually")
    relevant = [r for r in all_rules if r.get("target") == "tag" and "refs/tags/v*" in
                r.get("conditions", {}).get("ref_name", {}).get("include", [])]
    for rule in relevant:
        if rule.get("conditions", {}).get("ref_name", {}).get("exclude"):
            failures.append(f"{rule['name']}: excluded release tags")
        if "bypass_actors" not in rule:
            failures.append(f"{rule['name']}: bypass list is unreadable with this token")
    creation = [r for r in relevant if "creation" in {x.get("type") for x in r.get("rules", [])}]
    protection = [r for r in relevant if {"update", "deletion", "non_fast_forward"} <=
                  {x.get("type") for x in r.get("rules", [])}]
    if not creation:
        failures.append("release tag creation ruleset missing")
    if not protection:
        failures.append("release tag immutability ruleset missing")
    if any(r.get("bypass_actors") for r in protection):
        failures.append("release tag protection has bypass actors")
    for rule in creation:
        actors = rule.get("bypass_actors", [])
        if not actors:
            failures.append(f"{rule['name']}: no named release manager or admin role bypass")
        for actor in actors:
            if not (actor.get("actor_type") == "Team" or
                    actor.get("actor_type") == "RepositoryRole" and actor.get("actor_id") == 5):
                failures.append(f"{rule['name']}: unsupported creation bypass actor")
    try:
        expected = remote_signers(repo, info["default_branch"])
        if variable(repo) != expected:
            failures.append("RELEASE_SIGNERS_SHA256 differs from default-branch signer files")
    except SetupError as exc:
        failures.append(str(exc))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "apply"))
    parser.add_argument("--repo", required=True, help="GitHub OWNER/REPO; never inferred from git")
    parser.add_argument("--reviewer", action="append", default=[], help="pypi reviewer login; repeat for teams")
    parser.add_argument("--prevent-self-review", action="store_true", help="require another reviewer for a team")
    args = parser.parse_args()
    try:
        repo = require_repo(args.repo)
        if not args.reviewer:
            raise SetupError("preview/apply requires at least one --reviewer")
        changes, operations = settings_report(repo, reviewer=args.reviewer,
                                              prevent_self_review=args.prevent_self_review)
        if not changes:
            print(f"{repo}: no settings changes needed")
            return 0
        print("\n".join(changes))
        if args.command == "preview":
            print("PREVIEW ONLY: no settings changed")
            return 0
        for kind, payload in operations:
            if kind == "api":
                api(*payload)
            else:
                result = subprocess.run(["gh", "variable", "set", "RELEASE_SIGNERS_SHA256",
                                         "-R", repo, "--body", payload], check=False)
                if result.returncode:
                    raise SetupError("could not set RELEASE_SIGNERS_SHA256")
        failures = validate(repo)
        if failures:
            raise SetupError("settings changed, but validation failed: " + "; ".join(failures))
        print(f"PASS {repo}: applied and validated")
        return 0
    except SetupError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

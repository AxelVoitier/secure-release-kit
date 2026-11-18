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
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
CREATION_RULE = 'release tags: creation'
IMMUTABILITY_RULE = 'release tags: immutable'
RULE_NAMES = (CREATION_RULE, IMMUTABILITY_RULE)
ADMIN_ROLE_ID = 5
IMMUTABILITY_CONTROLS = ('update', 'deletion', 'non_fast_forward')


class SetupError(Exception):
    """An input, prerequisite, or remote setting prevents the requested work."""


class MissingSignersError(SetupError):
    """The default branch lacks the required signer file set."""


def gh(*args: str, data: dict[str, Any] | None = None) -> Any:
    command = ['gh', *args]
    if data is not None:
        command += ['--input', '-']
    try:
        result = subprocess.run(
            command,
            input=json.dumps(data) if data is not None else None,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SetupError('gh is missing; install GitHub CLI first') from exc
    if result.returncode:
        raise SetupError(f'gh {" ".join(args)} failed: {result.stderr.strip()}')
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SetupError(f'gh {" ".join(args)} returned invalid JSON') from exc


def api(path: str, method: str = 'GET', data: dict[str, Any] | None = None) -> Any:
    return gh('api', '-X', method, path, data=data)


def require_repo(repo: str) -> str:
    if not REPO.fullmatch(repo) or '..' in repo:
        raise SetupError('--repo must be OWNER/REPO')
    return repo


def repo_info(repo: str) -> dict[str, Any]:
    info = api(f'repos/{repo}')
    if info.get('full_name', '').casefold() != repo.casefold():
        raise SetupError(f'GitHub returned a different repository for {repo}')
    return info


def environment(repo: str, name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    path = f'repos/{repo}/environments/{name}'
    try:
        current = api(path)
    except SetupError as exc:
        if 'HTTP 404' in str(exc):
            return None, []
        raise
    policy = current.get('deployment_branch_policy')
    if not policy or not policy.get('custom_branch_policies'):
        return current, []
    pages = gh('api', f'{path}/deployment-branch-policies', '--paginate', '--slurp')
    return current, [policy for page in pages for policy in page['branch_policies']]


def rulesets(repo: str, *, include_parents: bool = True) -> list[dict[str, Any]]:
    query = f'?includes_parents={str(include_parents).lower()}'
    summary = gh('api', f'repos/{repo}/rulesets{query}', '--paginate', '--slurp')
    rows = [item for page in summary for item in page]
    return [api(f'repos/{repo}/rulesets/{row["id"]}') for row in rows]


def desired_rule(name: str) -> dict[str, Any]:
    if name == CREATION_RULE:
        controls = ('creation',)
        bypass = [
            {'actor_id': ADMIN_ROLE_ID, 'actor_type': 'RepositoryRole', 'bypass_mode': 'always'}
        ]
    else:
        controls = IMMUTABILITY_CONTROLS
        bypass = []
    return {
        'name': name,
        'target': 'tag',
        'enforcement': 'active',
        'conditions': {'ref_name': {'include': ['refs/tags/v*'], 'exclude': []}},
        'rules': [{'type': control} for control in controls],
        'bypass_actors': bypass,
    }


def creation_bypass_error(rule: dict[str, Any]) -> str | None:
    actors = rule.get('bypass_actors')
    if actors is None:
        return f'{rule["name"]}: creation bypass list is unreadable'
    if not actors:
        return f'{rule["name"]}: no named release manager or admin role bypass'
    for actor in actors:
        if actor.get('actor_type') == 'Team' and isinstance(actor.get('actor_id'), int):
            continue
        if actor.get('actor_type') == 'RepositoryRole' and actor.get('actor_id') == ADMIN_ROLE_ID:
            continue
        return f'{rule["name"]}: unsupported creation bypass actor'
    return None


def remote_signers(repo: str, branch: str) -> str:
    prefix = f'repos/{repo}/contents/.github'
    try:
        entries: list[dict[str, Any]] = api(f'{prefix}?ref={quote(branch, safe="")}')
    except SetupError as exc:
        if 'HTTP 404' not in str(exc):
            raise
        entries = []
    names = sorted(item['name'] for item in entries if item['name'].startswith('release-signers'))
    if not names or any(name not in ('release-signers', 'release-signers.asc') for name in names):
        raise MissingSignersError(
            'default branch needs only .github/release-signers and/or .github/release-signers.asc'
        )
    lines: list[str] = []
    for name in names:
        item = api(f'{prefix}/{name}?ref={quote(branch, safe="")}')
        if item.get('type') != 'file' or item.get('encoding') != 'base64':
            raise SetupError(f'cannot read committed signer file {name}')
        digest = hashlib.sha256(base64.b64decode(item['content'])).hexdigest()
        lines.append(f'{digest}  .github/{name}')
    return '\n'.join(lines)


def variable(repo: str) -> str | None:
    try:
        return api(f'repos/{repo}/actions/variables/RELEASE_SIGNERS_SHA256').get('value')
    except SetupError as exc:
        if 'HTTP 404' in str(exc):
            return None
        raise


def reviewer_id(login: str) -> int:
    if not re.fullmatch(r'[A-Za-z0-9-]+', login):
        raise SetupError(f'invalid reviewer login: {login}')
    return int(api(f'users/{login}')['id'])


@dataclass(frozen=True)
class ApiChange:
    path: str
    method: str
    body: dict[str, Any] | None = None
    description: str = ''

    def preview(self) -> str:
        detail = self.description or json.dumps(self.body, sort_keys=True)
        return f'{self.method} {self.path}: {detail}'

    def apply(self) -> None:
        api(self.path, self.method, self.body)


@dataclass(frozen=True)
class SignerVariableChange:
    repo: str
    value: str

    def preview(self) -> str:
        return f'SET RELEASE_SIGNERS_SHA256 in {self.repo} to:\n{self.value}'

    def apply(self) -> None:
        command = [
            'gh',
            'variable',
            'set',
            'RELEASE_SIGNERS_SHA256',
            '-R',
            self.repo,
            '--body',
            self.value,
        ]
        if subprocess.run(command, check=False).returncode:
            raise SetupError('could not set RELEASE_SIGNERS_SHA256')


def environment_needs_update(current: dict[str, Any] | None, desired: dict[str, Any]) -> bool:
    if (
        current is None
        or current.get('deployment_branch_policy') != desired['deployment_branch_policy']
    ):
        return True
    if 'reviewers' not in desired:
        return False  # Only the production environment manages reviewer settings.
    review_rules = [
        rule
        for rule in current.get('protection_rules', [])
        if rule.get('type') == 'required_reviewers'
    ]
    existing_reviewers = [r for rule in review_rules for r in rule.get('reviewers', [])]
    existing_ids = sorted(
        (r.get('type'), r.get('reviewer', {}).get('id')) for r in existing_reviewers
    )
    wanted_ids = sorted((r['type'], r['id']) for r in desired['reviewers'])
    existing_self_review = (
        review_rules[0].get('prevent_self_review', False) if review_rules else False
    )
    return (
        existing_ids != wanted_ids
        or existing_self_review != desired['prevent_self_review']
        or current.get('can_admins_bypass') is not False
    )


def environment_changes(
    repo: str, name: str, reviewer: list[str], *, prevent_self_review: bool
) -> list[ApiChange]:
    changes: list[ApiChange] = []
    current, policies = environment(repo, name)
    reviewers = (
        [{'type': 'User', 'id': reviewer_id(login)} for login in reviewer] if name == 'pypi' else []
    )
    body: dict[str, Any] = {
        'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True},
    }
    if name == 'pypi':
        body.update(
            reviewers=reviewers, prevent_self_review=prevent_self_review, can_admins_bypass=False
        )
    path = f'repos/{repo}/environments/{name}'
    if environment_needs_update(current, body):
        changes.append(ApiChange(path, 'PUT', body))
    policy_path = f'{path}/deployment-branch-policies'
    kept_release_policy = False
    for policy in policies:
        if not kept_release_policy and policy.get('type') == 'tag' and policy.get('name') == 'v*':
            kept_release_policy = True
            continue

        detail = f'{policy.get("type")} {policy.get("name")}'
        changes.append(ApiChange(f'{policy_path}/{policy["id"]}', 'DELETE', description=detail))
    if not kept_release_policy:
        changes.append(ApiChange(policy_path, 'POST', {'name': 'v*', 'type': 'tag'}))
    return changes


def tag_ruleset_changes(repo: str) -> list[ApiChange]:
    changes: list[ApiChange] = []
    existing = [r for r in rulesets(repo, include_parents=False) if r.get('target') == 'tag']
    for name in RULE_NAMES:
        matches = [r for r in existing if r.get('name') == name]
        if len(matches) > 1:
            raise SetupError(f'more than one active ruleset named {name}')
        desired = desired_rule(name)
        current = matches[0] if matches else None
        if current is not None and name == CREATION_RULE:
            error = creation_bypass_error(current)
            if error:
                raise SetupError(f'{error}; review the existing ruleset in GitHub')
            desired['bypass_actors'] = current['bypass_actors']
        fields = desired.keys()
        if current is None or any(current.get(key) != desired[key] for key in fields):
            method = 'PUT' if current else 'POST'
            path = f'repos/{repo}/rulesets' + (f'/{current["id"]}' if current else '')
            changes.append(ApiChange(path, method, desired))
    return changes


def settings_report(
    repo: str, *, reviewer: list[str], prevent_self_review: bool
) -> list[ApiChange | SignerVariableChange]:
    """Build the plan using reads only. Preview and apply consume the same operations."""
    info = repo_info(repo)
    if not info.get('permissions', {}).get('admin'):
        raise SetupError('the gh account needs repository admin access')
    changes: list[ApiChange | SignerVariableChange] = []
    for name in ('testpypi', 'pypi'):
        changes.extend(
            environment_changes(repo, name, reviewer, prevent_self_review=prevent_self_review)
        )
    changes.extend(tag_ruleset_changes(repo))
    expected = remote_signers(repo, info['default_branch'])
    if variable(repo) != expected:
        changes.append(SignerVariableChange(repo, expected))
    return changes


def audit_environment(repo: str, name: str) -> list[str]:
    failures: list[str] = []
    current, policies = environment(repo, name)
    policy = current.get('deployment_branch_policy') if current else None
    if not policy or policy.get('custom_branch_policies') is not True:
        failures.append(f'{name}: custom deployment policy missing')
    if len(policies) != 1 or policies[0].get('type') != 'tag' or policies[0].get('name') != 'v*':
        failures.append(f'{name}: expected exactly one v* tag policy')
    if name == 'pypi' and current:
        required = [
            rule
            for rule in current.get('protection_rules', [])
            if rule.get('type') == 'required_reviewers' and rule.get('reviewers')
        ]
        if not required:
            failures.append('pypi: required reviewers missing')
        if current.get('can_admins_bypass') is not False:
            failures.append('pypi: administrator bypass must be disabled')
    return failures


def audit_release_tags(repo: str) -> list[str]:
    failures: list[str] = []
    found_creation = False
    found_immutability = False
    for rule in rulesets(repo):
        if rule.get('enforcement') != 'active' or rule.get('target') != 'tag':
            continue
        refs = rule.get('conditions', {}).get('ref_name', {})
        if 'refs/tags/v*' not in refs.get('include', []):
            continue
        if refs.get('exclude'):
            failures.append(f'{rule["name"]}: excluded release tags')
        if 'bypass_actors' not in rule:
            failures.append(f'{rule["name"]}: bypass list is unreadable with this token')
        controls = {control.get('type') for control in rule.get('rules', [])}
        if 'creation' in controls:
            found_creation = True
            error = creation_bypass_error(rule)
            if error:
                failures.append(error)
        if controls.issuperset(IMMUTABILITY_CONTROLS):
            found_immutability = True
            if rule.get('bypass_actors'):
                failures.append('release tag protection has bypass actors')
    if not found_creation:
        failures.append('release tag creation ruleset missing')
    if not found_immutability:
        failures.append('release tag immutability ruleset missing')
    return failures


def validate(repo: str) -> list[str]:
    failures: list[str] = []
    info = repo_info(repo)
    if not info.get('permissions', {}).get('admin'):
        raise SetupError('the gh account needs repository admin access to audit bypass lists')
    for name in ('testpypi', 'pypi'):
        failures.extend(audit_environment(repo, name))
    # GitHub resolves ref patterns, exclusions and inherited rules for this branch.
    branch = quote(info['default_branch'], safe='')
    pages = gh('api', f'repos/{repo}/rules/branches/{branch}', '--paginate', '--slurp')
    if not any(pages):
        failures.append(
            'default branch has no effective ruleset rules; inspect branch protection manually'
        )
    failures.extend(audit_release_tags(repo))
    try:
        expected = remote_signers(repo, info['default_branch'])
        if variable(repo) != expected:
            failures.append('RELEASE_SIGNERS_SHA256 differs from default-branch signer files')
    except MissingSignersError as exc:
        failures.append(str(exc))
    return failures


def configure_repository(
    repo: str, reviewers: list[str], *, prevent_self_review: bool, preview: bool
) -> int:
    if not reviewers:
        raise SetupError('preview/apply requires at least one --reviewer')
    changes = settings_report(repo, reviewer=reviewers, prevent_self_review=prevent_self_review)
    if not changes:
        print(f'{repo}: no settings changes needed')
    else:
        print('\n'.join(change.preview() for change in changes))
    if preview:
        print('PREVIEW ONLY: no settings changed')
        return 0
    for change in changes:
        change.apply()
    failures = validate(repo)
    if failures:
        raise SetupError('validation failed: ' + '; '.join(failures))
    print(f'PASS {repo}: applied and validated')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preview', 'apply'))
    parser.add_argument('--repo', required=True, help='GitHub OWNER/REPO; never inferred from git')
    parser.add_argument(
        '--reviewer',
        action='append',
        default=[],
        help='pypi reviewer login; repeat for additional users',
    )
    parser.add_argument(
        '--prevent-self-review', action='store_true', help='require another reviewer for a team'
    )
    args = parser.parse_args()
    try:
        return configure_repository(
            require_repo(args.repo),
            args.reviewer,
            prevent_self_review=args.prevent_self_review,
            preview=args.command == 'preview',
        )
    except SetupError as exc:
        print(f'ERROR {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

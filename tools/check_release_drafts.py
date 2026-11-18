# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Exercise the real release step with visible and hidden upload destinations.

Run: python3 tools/check_release_drafts.py [path/to/release.yml]
Uses runstep.py and the gh test double. No network or credentials required.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parent / 'template/_github/workflows/release.yml'
STEP = 'Create or complete the release (draft -> assets -> tag check -> publish)'


def write_assets(root: Path, sdist: str, wheel: str) -> list[dict[str, str]]:
    assets = root / 'assets'
    assets.mkdir()
    names = [
        'sbom.cdx.json',
        sdist,
        wheel,
        sdist + '.sigstore.json',
        wheel + '.sigstore.json',
        'sbom.cdx.json.sigstore.json',
        sdist + '.pypi-provenance.json',
        wheel + '.pypi-provenance.json',
    ]
    expected_assets: list[dict[str, str]] = []
    for name in names:
        content = (name + '\n').encode()
        (assets / name).write_bytes(content)
        expected_assets.append(
            {'name': name, 'digest': 'sha256:' + hashlib.sha256(content).hexdigest()}
        )

    return expected_assets


def write_release_fixtures(
    root: Path,
    expected_assets: list[dict[str, str]],
    *,
    published: bool,
    immutable: bool,
    corrupt: bool,
) -> Path:
    fixtures = root / 'fixtures'
    fixtures.mkdir()
    prefix = 'repos_fixture_dummy'
    draft: dict[str, Any] = {
        'id': 1,
        'tag_name': 'v1.0',
        'draft': not published,
        'immutable': immutable,
        'assets': expected_assets if published else [],
    }
    if corrupt:
        draft = {
            **draft,
            'assets': [{**asset, 'digest': 'sha256:wrong'} for asset in expected_assets],
        }
    for name, value in {
        f'GET_{prefix}_releases': [draft],  # The list hides draft 2.
        f'GET_{prefix}_releases_1': draft,
        f'GET_{prefix}_releases_2': {**draft, 'id': 2},
        f'GET_{prefix}_git_ref_tags_v1.0': {'object': {'type': 'tag', 'sha': 'annotated'}},
        f'GET_{prefix}_git_tags_annotated': {'object': {'sha': 'built'}},
        f'PATCH_{prefix}_releases_1': {**draft, 'draft': False, 'immutable': immutable},
    }.items():
        (fixtures / (name + '.json')).write_text(json.dumps(value))

    return fixtures


def require(condition: bool, detail: object) -> None:
    if not condition:
        raise AssertionError(detail)


def check(
    *,
    hidden_duplicate: bool = False,
    published: bool = False,
    immutable: bool = False,
    failures: int = 0,
    status: int = 0,
    delay: str = '',
    corrupt: bool = False,
    deadline_failure: bool = False,
    workflow: Path = WORKFLOW,
) -> None:
    with tempfile.TemporaryDirectory(prefix='release-drafts-') as directory:
        root = Path(directory)
        bin_dir = root / 'bin'
        bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_bytes((HERE.parent / 'tests/bin/gh').read_bytes())
        gh.chmod(0o755)
        sdist = 'dummy-1.0.tar.gz'
        wheel = 'dummy-1.0-py3-none-any.whl'
        expected_assets = write_assets(root, sdist, wheel)
        fixtures = write_release_fixtures(
            root, expected_assets, published=published, immutable=immutable, corrupt=corrupt
        )
        env = dict(
            os.environ,
            PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
            FIX=str(fixtures),
            GHLOG=str(root / 'gh.log'),
            WORKDIR=str(root),
            STATE=str(root / 'state'),
            GH_UPLOAD_RELEASE_ID='2' if hidden_duplicate else '1',
            GITHUB_REPOSITORY='fixture/dummy',
            GITHUB_SHA='built',
            GH_VERIFY_STATUS=str(status),
            GH_VERIFY_FAILURES=str(failures),
            GH_VERIFY_DELAY=delay,
        )
        # runstep requires every expression-valued job environment entry to be supplied.
        job_env = yaml.safe_load(workflow.read_text())['jobs']['github-release']['env']
        overrides = dict.fromkeys(job_env, 'unused')
        overrides.update(
            GH_TOKEN='test-double', TAG='v1.0', PRERELEASE='false', SDIST=sdist, WHEEL=wheel
        )
        result = subprocess.run(
            [
                sys.executable,
                str(HERE / 'runstep.py'),
                str(workflow),
                'github-release',
                STEP,
                *(key + '=' + value for key, value in overrides.items()),
            ],
            check=False,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        require((root / 'gh.log').exists(), result.stdout + result.stderr)
        calls = (root / 'gh.log').read_text()
        attempts = calls.count('gh release verify ')
        if published:
            require('-X PATCH' not in calls and 'gh release upload ' not in calls, calls)
        else:
            uploaded_id = 2 if hidden_duplicate else 1
            uploaded = json.loads(
                (fixtures / f'GET_repos_fixture_dummy_releases_{uploaded_id}.json').read_text()
            )
            require(uploaded['assets'] == expected_assets, uploaded)
            require('gh api repos/fixture/dummy/releases/1\n' in calls, calls)
        if hidden_duplicate or corrupt:
            require(result.returncode != 0, result.stdout + result.stderr)
            error = (
                'release 1: asset sbom.cdx.json differs or is missing'
                if hidden_duplicate
                else 'published release asset sbom.cdx.json differs'
            )
            require(error in result.stdout, result.stdout + result.stderr)
            require('-X PATCH' not in calls and attempts == 0, calls)
        elif deadline_failure:
            require(result.returncode != 0, 'verification failure was ignored')
            require(
                'immutable release verification did not succeed within' in result.stdout,
                result.stdout + result.stderr,
            )
            require(attempts >= 1, calls)
        else:
            require(result.returncode == 0, result.stdout + result.stderr)
            require(attempts == (failures + 1 if immutable else 0), calls)
            if not published:
                require('-X PATCH repos/fixture/dummy/releases/1' in calls, calls)
        print(
            f'PASS published={published} immutable={immutable} hidden={hidden_duplicate} '
            f'corrupt={corrupt} failures={failures} deadline_failure={deadline_failure}: '
            f'exit={result.returncode}, verification_attempts={attempts}'
        )


def main() -> None:
    workflow = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else WORKFLOW
    check(workflow=workflow)
    check(workflow=workflow, hidden_duplicate=True)
    check(workflow=workflow, published=True)
    check(workflow=workflow, published=True, immutable=True)
    check(workflow=workflow, published=True, immutable=True, corrupt=True)
    check(workflow=workflow, immutable=True)
    # Exercise the unchanged loop with shorter constants, so failure/deadline checks take seconds.
    with tempfile.TemporaryDirectory(prefix='release-verification-bounds-') as directory:
        shortened = Path(directory) / 'release.yml'
        source = (
            workflow.read_text()
            .replace('SECONDS + 300', 'SECONDS + 2')
            .replace('10 - SECONDS', '1 - SECONDS')
        )
        shortened.write_text(source)
        check(published=True, immutable=True, failures=1, workflow=shortened)
        check(published=True, immutable=True, status=1, deadline_failure=True, workflow=shortened)
        check(immutable=True, status=1, deadline_failure=True, workflow=shortened)
        check(published=True, immutable=True, delay='5', deadline_failure=True, workflow=shortened)


if __name__ == '__main__':
    main()

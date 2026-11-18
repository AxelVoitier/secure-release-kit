# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Run a single shell step from a workflow with local inputs."""

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


def step_environment(
    scopes: list[dict[str, Any]],
    state: Path,
    overrides: list[str],
) -> dict[str, str]:
    """Apply workflow, job, and step settings, then saved state and command-line inputs."""
    environment = dict(os.environ)
    for scope in scopes:
        settings: dict[str, Any] = scope.get('env') or {}
        for name, value in settings.items():
            # Callers can supply a resolved Actions expression in their process environment.
            if '${{' in str(value) and name in os.environ:
                continue
            environment[name] = str(value)

    saved = state / 'github_env'
    if saved.exists():
        for line in saved.read_text().splitlines():
            if '=' in line:
                name, value = line.split('=', 1)
                environment[name] = value
    for assignment in overrides:
        name, value = assignment.split('=', 1)
        environment[name] = value
    unresolved = [name for name, value in environment.items() if '${{' in value]
    if unresolved:
        raise SystemExit(f'unresolved expressions in env: {unresolved}')

    temporary = state / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    environment.update(
        GITHUB_ENV=str(saved), GITHUB_OUTPUT=str(state / 'outputs'), RUNNER_TEMP=str(temporary)
    )
    return environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workflow', type=Path)
    parser.add_argument('job')
    parser.add_argument('step', help='step name or id')
    parser.add_argument('overrides', nargs='*', metavar='KEY=VALUE')
    args = parser.parse_args()
    workflow = yaml.safe_load(args.workflow.read_text())
    job = workflow['jobs'][args.job]
    matches = [step for step in job['steps'] if args.step in (step.get('name'), step.get('id'))]
    if len(matches) != 1:
        available = [step.get('name') or step.get('id') for step in job['steps']]
        parser.exit(1, f'step {args.step!r} not found once in {args.job}: {available}\n')
    step = matches[0]
    state = Path(os.environ.get('STATE', '/tmp/state'))
    environment = step_environment([workflow, job, step], state, args.overrides)
    result = subprocess.run(
        ['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step['run']],
        env=environment,
        cwd=environment.get('WORKDIR', '.'),
        check=False,
    )
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())

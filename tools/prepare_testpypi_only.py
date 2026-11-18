# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Prepare an isolated TestPyPI-only workflow copy for an authorised hosted run.

usage: python3 tools/prepare_testpypi_only.py OUTPUT_DIR

OUTPUT_DIR must not exist. This command creates files locally; it does not deploy,
sign, push, dispatch a run, or configure trusted publishers.
"""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'template/_github/workflows'
PATCH = ROOT / 'tests/hosted/testpypi-only.patch'


def validate_hosted_workflow(path: Path) -> None:
    jobs = yaml.safe_load(path.read_text())['jobs']
    publisher = jobs['publish-pypi']
    verifier = jobs['verify-pypi']
    for name in ('publish-testpypi', 'verify-testpypi'):
        if jobs[name]['if'] is not False:
            raise ValueError(f'{name} must be disabled in the hosted copy')
    index = 'https://test.pypi.org'
    if publisher['env']['INDEX'] != index or verifier['env']['INDEX'] != index:
        raise ValueError('hosted publish and verify jobs must use the TestPyPI index')
    if publisher['env']['UPLOAD_URL'] != index + '/legacy/':
        raise ValueError('hosted upload must target TestPyPI')
    if publisher['needs'] != ['origin-check', 'build']:
        raise ValueError('hosted publisher must depend on origin-check and build')
    if not any(
        step.get('name') == 'Check CI tested these wheel bytes' for step in publisher['steps']
    ):
        raise ValueError('hosted publisher is missing the CI wheel check')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    output = args.output_dir.absolute()
    if output.exists() or output.is_symlink():
        parser.error(f'output already exists: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        candidate = Path(temp) / 'copy'
        workflows = candidate / '.github/workflows'
        workflows.mkdir(parents=True)
        for name in ('build.yml', 'ci.yml', 'release.yml'):
            shutil.copy2(SOURCE / name, workflows / name)
        subprocess.run(
            ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=candidate, check=True
        )
        validate_hosted_workflow(workflows / 'release.yml')
        # Reserve the name only after validation, without replacing a concurrent caller's directory.
        output.mkdir()
        try:
            (candidate / '.github').rename(output / '.github')
        except OSError:
            output.rmdir()
            raise
    print(f'Prepared TestPyPI-only workflow copy: {output / ".github/workflows"}')
    print('Review the diff against template/_github/workflows before use.')


if __name__ == '__main__':
    main()

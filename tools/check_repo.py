# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Read only GitHub settings audit for an explicit repository."""

import argparse
import sys

from repo_settings import SetupError, require_repo, validate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='GitHub OWNER/REPO')
    args = parser.parse_args()
    try:
        repo = require_repo(args.repo)
        failures = validate(repo)
    except SetupError as exc:
        print(f'ERROR {exc}', file=sys.stderr)
        return 2
    for failure in failures:
        print(f'FAIL {failure}')
    print('NOT RUN: trusted publishers, TestPyPI name claim, local workflow checks, or a release')
    if failures:
        return 1
    print(f'PASS {repo}: environment, branch, tag, bypass, and signer settings')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

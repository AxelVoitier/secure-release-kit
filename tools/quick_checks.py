# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Run portable checks on the maintained workflow template and local tools."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / "template/_github/workflows").glob("*.yml"))


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-linters", action="store_true", help="fail if actionlint or zizmor is unavailable")
    args = parser.parse_args()

    if len(WORKFLOWS) != 3:
        raise SystemExit("expected three workflow templates")
    for path in WORKFLOWS:
        workflow = yaml.safe_load(path.read_text())
        if not isinstance(workflow, dict) or not isinstance(workflow.get("jobs"), dict):
            raise SystemExit(f"invalid workflow structure: {path}")
    print("PASS: three workflow templates parse", flush=True)

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])

    actionlint = shutil.which("actionlint")
    zizmor = shutil.which("zizmor")
    missing = [name for name, path in (("actionlint", actionlint), ("zizmor", zizmor)) if path is None]
    if missing and args.require_linters:
        raise SystemExit("missing required linters: " + ", ".join(missing))
    if actionlint:
        run([actionlint, "-ignore", r'reusable workflow call "\$/', *map(str, WORKFLOWS)])
    else:
        print("SKIP: actionlint unavailable", flush=True)
    if zizmor:
        run([zizmor, "--offline", *map(str, WORKFLOWS)])
    else:
        print("SKIP: zizmor unavailable", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)

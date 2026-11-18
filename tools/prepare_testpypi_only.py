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
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "template/_github/workflows"
PATCH = ROOT / "tests/hosted/testpypi-only.patch"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        parser.error(f"output already exists: {output}")
    workflows = output / ".github/workflows"
    workflows.mkdir(parents=True)
    for name in ("build.yml", "ci.yml", "release.yml"):
        shutil.copy2(SOURCE / name, workflows / name)
    try:
        subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)],
                       cwd=output, check=True)
        release = yaml.safe_load((workflows / "release.yml").read_text())
        jobs = release["jobs"]
        valid = (
            jobs["publish-testpypi"]["if"] is False
            and jobs["verify-testpypi"]["if"] is False
            and jobs["publish-pypi"]["env"]["INDEX"] == "https://test.pypi.org"
            and jobs["publish-pypi"]["env"]["UPLOAD_URL"] == "https://test.pypi.org/legacy/"
            and jobs["verify-pypi"]["env"]["INDEX"] == "https://test.pypi.org"
            and jobs["publish-pypi"]["needs"] == ["origin-check", "build"]
            and any(step.get("name") == "Check CI tested these wheel bytes"
                    for step in jobs["publish-pypi"]["steps"])
        )
        if not valid:
            raise ValueError("hosted workflow has unexpected settings")
        print(f"Prepared TestPyPI-only workflow copy: {workflows}")
        print("Review the diff against template/_github/workflows before use.")
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError):
        shutil.rmtree(output)
        raise SystemExit("TestPyPI-only patch did not match the template; no output retained")


if __name__ == "__main__":
    main()

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
SOURCE = ROOT / "template/_github/workflows"
PATCH = ROOT / "tests/hosted/testpypi-only.patch"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir.absolute()
    if output.exists() or output.is_symlink():
        parser.error(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        candidate = Path(temp) / "copy"
        workflows = candidate / ".github/workflows"
        workflows.mkdir(parents=True)
        for name in ("build.yml", "ci.yml", "release.yml"):
            shutil.copy2(SOURCE / name, workflows / name)
        subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)],
                       cwd=candidate, check=True)
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
        # Reserve the name only after validation, without replacing a concurrent caller's directory.
        output.mkdir()
        try:
            (candidate / ".github").rename(output / ".github")
        except OSError:
            output.rmdir()
            raise
    print(f"Prepared TestPyPI-only workflow copy: {output / '.github/workflows'}")
    print("Review the diff against template/_github/workflows before use.")


if __name__ == "__main__":
    main()

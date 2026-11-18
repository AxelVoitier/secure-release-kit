# Rehearse a build locally

Turn the kit’s sample package into a source archive, then build an installable wheel from that archive in an empty directory. The archive carries the list of build tools and their hashes. You will check that list before you build the wheel.

Use Bash on Linux with Git, GNU tar and coreutils. You need a checkout of the kit, Python 3.11 or later with PyYAML, and uv on your path. Use the uv version in [Configuration and pins](../reference/configuration.md). Allow uv to download the workflow's Python version and build dependencies.

## Prepare the sample package

Start at the root of the kit checkout. Run the command blocks in order in the same shell.

```bash
kit=$PWD
lab=$(mktemp -d)
cp -R "$kit/tests/fixture" "$lab/package"
cd "$lab/package"
ls
```

Look for `pyproject.toml`, `src` and `tests`. The sample uses Hatchling to build its distributions. Without a Git checkout, its version falls back to `0.0.0`.

## Build and open the source archive

The kit's step runner executes one shell step from the workflow. Give the source build its own directory for step outputs. The lock step reads a Git commit timestamp to decide which dependency releases are old enough to use. Point that step at the kit’s Git history to use the checkout’s commit time.

```bash
workflow="$kit/template/_github/workflows/build.yml"
step() { python3 "$kit/tools/runstep.py" "$workflow" "$@"; }
export STATE="$lab/sdist-state"

GIT_DIR="$(git -C "$kit" rev-parse --absolute-git-dir)" step build-sdist lock
head -n 3 build-constraints.txt
```

Look for an exact package version followed by SHA-256 hashes. This build lock records which files uv can use to install Hatchling and its dependencies.

Build the source distribution (sdist). The next step checks the version inside the archive and compares the embedded lock with the file you just read.

```bash
step build-sdist 'Build the sdist with the hash-locked build environment'
step build-sdist check EXPECTED_VERSION=0.0.0
tar -tzf dist/*.tar.gz | grep '/build-constraints.txt$'
```

Look for `release_pipeline_dummy-0.0.0/build-constraints.txt` inside the archive.

## Build the wheel in an empty directory

Give the wheel job only the sdist and the values the source job recorded. In GitHub Actions these cross the job boundary as an artifact and job outputs.

```bash
output() { sed -n "s/^$1=//p" "$lab/sdist-state/outputs"; }
export SDIST="$(output sdist-name)"
export SDIST_SHA256="$(output sdist-sha256)"
export LOCK_SHA256="$(output lock-sha256)"
export SOURCE_DATE_EPOCH="$(output source-date-epoch)"

mkdir -p "$lab/wheel/dist"
cp "dist/$SDIST" "$lab/wheel/dist/"
cd "$lab/wheel"
export STATE="$lab/wheel-state"

step build-wheel 'Check the sdist digest'
step build-wheel 'Build the wheel from the sdist alone, with the lock it carries'
ls wheelhouse
```

The first step prints `OK` for the archive. The second checks the lock's hash, then builds with that lock. The result is `release_pipeline_dummy-0.0.0-py3-none-any.whl`. Its name carries the same version you checked inside the sdist.

You built the wheel without a source checkout in the wheel job. Hosted permissions, signatures, attestations, approval and publication need separate checks. To put this builder into your own CI, follow [Install the pipeline](../how-to/install.md). To see where the wheel goes after the build, read [How a release moves through the pipeline](../explanation/architecture.md).

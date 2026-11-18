# Make supported workflow adaptations

Keep the template checks enabled if your package passes them. If a check fails, identify the dependency, wheel or runner that caused it before choosing an edit below. Make the change in the deploying project's `.github/workflows/` and record it alongside the upstream kit revision. These edits change what a successful release tells its users.

## When CI and release builds produce different wheels

First check that CI tested the wheel from the shared `build.yml` at the tagged commit. Fix a reproducibility problem in the build if you can. If the project has to ship wheels whose bytes differ between builds, make these two edits in `release.yml`:

1. In `publish-testpypi.steps`, remove the whole step named `Check CI tested these wheel bytes`, including its `env` and `run` blocks. Stop before `Apply the hash rule against the index`.
2. In **that job's** `permissions` block, remove `actions: read`. Keep this permission in `origin-check` and `publish-pypi`.

Keep the CI workflow and its wheel tests. The origin check still requires successful CI on the tagged commit and a run that used the builder. Subsequent hash checks still bind the release files to the release build. Remove any claim that CI tested those exact bytes.

## When a runtime dependency ships only a source distribution

In `release.yml`, find `Install the hash-pinned wheel from the index under test, dependencies from PyPI only` under `verify-testpypi`. Change only the **second** install command:

```diff
-          "$PIP" --isolated install --index-url https://pypi.org/simple --only-binary :all: "$NAME==$VERSION"
+          "$PIP" --isolated install --index-url https://pypi.org/simple "$NAME==$VERSION"
```

The first install must still use `"$INDEX/simple"`, `--no-deps`, `--only-binary :all:` and `--require-hashes`. It selects the project's wheel by its release digest. Keep `pip check` after the second install.

The verifier steps are shared through the YAML anchor `&verify-steps`. This single edit permits dependency builds in **both** index verification jobs. A dependency's build backend can now execute there, after provenance capture. Name the dependency that needs the change in the deployment notes. The edit permits source builds for other runtime dependencies too.

## When a build dependency ships only a source distribution

Check whether a compatible wheel exists under the project's build cooldown. If the build must use the source distribution, edit both of these commands in `build.yml`:

1. In `build-sdist`, find `Check [build-system], generate the build lock`. Remove `--no-build` from the first line of the compile command. Preserve its continuation and the cooldown arguments on the following line.

    ```diff
    -          uv pip compile "$RUNNER_TEMP/build-requires.in" --generate-hashes --no-header --no-annotate --no-build \
    +          uv pip compile "$RUNNER_TEMP/build-requires.in" --generate-hashes --no-header --no-annotate \
    ```

2. In `sbom`, find `Generate the CycloneDX SBOM`. Remove the wheel-only restriction from the install of the build lock into the licence environment.

    ```diff
    -          uv pip install --python "$venv/bin/python" --no-deps --only-binary :all: --require-hashes \
    +          uv pip install --python "$venv/bin/python" --no-deps --require-hashes \
    ```

Resolution can now execute a dependency's build backend before the job records the lock digest. The digest still binds subsequent transfers to the recorded bytes. It cannot establish what the lock contained before that code ran. The SBOM job can also build dependencies while collecting licence metadata. Update the nearby workflow comments and wheel-only error message to describe the new behaviour. Keep the cooldown in the resolver. Later jobs still need the lock hashes and digest comparisons.

## When a GitHub Enterprise Server runner needs the relative call

If your server supports the relative reusable-workflow syntax, edit the `build` job's `uses` line in **both** `ci.yml` and `release.yml`:

```yaml
uses: ./.github/workflows/build.yml
```

This replaces `$/.github/workflows/build.yml` and still selects the builder from the caller's commit. Check the syntax against your server version. Before relying on the deployment, exercise the runner, attestations, trusted publishing and environment approvals on that installation. A syntax check establishes only that the call parses. [GitHub Enterprise Server workflow syntax](https://docs.github.com/en/enterprise-server@3.18/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_iduses)

## Check the deployed change

Review the exact diff from the deploying project root:

```bash
git diff HEAD -- .github/workflows/ci.yml .github/workflows/build.yml .github/workflows/release.yml
```

Check the changed path in a disposable copy with the same Python version and dependency constraints as the project. Run the affected commands against that copy. Use a fresh environment and lock output for each case. The kit's quick checks exercise the kit's template. They cannot exercise edits that exist only in a deployment.

| Change | What to exercise |
| --- | --- |
| Remove CI wheel comparison | On the unchanged template, run `python3 -m unittest tests/test_portable_steps.py -v` from the kit root. Matching bytes pass and differing bytes fail. In the deployed copy, confirm the step and its job-specific permission are absent. Exercise the origin check with failed CI and the staging digest check with a mismatched wheel. Both must still stop the release. |
| Allow source builds for runtime dependencies | Use a wheel with a dependency available as a wheel, then one whose dependency is available only as an sdist. With the default, the second install passes the first case and rejects the second. With the edit, both must install and pass `pip check`. A missing or wrong project wheel must still fail the first install. |
| Allow source builds for build dependencies | Try a wheel-backed build requirement, then an sdist-only one that needs its backend to obtain metadata. Default resolution must reject the latter. In the changed copy, resolve a fresh lock, build from it and generate the SBOM. Check that the licence environment accepts the locked sdist and rejects an incorrect hash. |
| Change the reusable-workflow call | Confirm both callers select the same builder at their commit. Check each caller on the target server before recording hosted support. |

In the deployment notes, record the affected job, the reason for the edit and the guarantee the project can still make. For the complete list of controls, see [Safeguards](../reference/safeguards.md).

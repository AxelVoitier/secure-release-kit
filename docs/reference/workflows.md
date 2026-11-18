# Workflow contracts

A push of a release tag starts two runs. Project CI tests the wheel from its own build. The release waits for CI, calls the same builder again and publishes the distributions from the release run. The default staging check uses the CI run IDs to download each tested wheel and compare it with the release wheel.

## Entry points

Paths below refer to the deployed repository. The kit ships these files under `template/_github/workflows/`.

| Workflow | Starts on | Contract |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Push to `main`, push of a `v*` tag, or pull request | Calls the builder with `attest: false` and tests the resulting wheel. |
| `.github/workflows/build.yml` | `workflow_call` | Both callers use `$/.github/workflows/build.yml` at the caller's commit. The builder has no deployment environment. |
| `.github/workflows/release.yml` | Push of a `v*` tag | One concurrency group per full ref, `release-${{ github.ref }}`, with `cancel-in-progress: false`. A later run for the same tag cannot interrupt an active publication. |

All three workflows declare `permissions: {}` at the top level. The tables below list each job's declared token scopes. An empty map grants no repository token scopes. Actions has a separate runtime token for artifacts and caches. All jobs that execute steps use `ubuntu-latest`.

### Tag and version

The release accepts an annotated tag signed by a pinned SSH or GPG signer. Its internal tag name must match the ref name. Its commit must equal `GITHUB_SHA` and belong to the history of the default branch. The version is the part after the initial lowercase `v`.

| Version part | Accepted spelling |
| --- | --- |
| Epoch | Optional positive integer followed by `!`, as in `v1!2.0`. |
| Release | One or more dot-separated non-negative integers. Zero is valid. Leading zeroes are rejected in every numeric part. |
| Suffixes, in order | Optional `aN`, `bN` or `rcN`, then optional `.postN`, then optional `.devN`. Each `N` is required when the suffix is present. |

The spelling must already be canonical. For example, `v1.4rc1` passes, while `v1.4-rc1` and `v1.4+local` fail. The builder compares the version string directly with the `Version` field in the source distribution's `PKG-INFO`.

## Reusable builder

| Input | Type | Default | Effect |
| --- | --- | --- | --- |
| `attest` | Boolean | `false` | With `true`, sign the source distribution (sdist), wheel and software bill of materials (SBOM). Verify the sdist attestation before building the wheel. |
| `expected-version` | String | `""` | A non-empty string requires an exact version match. CI omits this input. The release passes `origin-check.outputs.version` through `needs`. |

Both caller jobs grant `contents: read`, `id-token: write` and `attestations: write`. GitHub checks this ceiling even when a called job will be skipped. Each executed job receives its own narrower scopes. CI skips the three signing jobs because its caller sets `attest: false`.

| Job | Direct dependencies (`needs`) | Token scopes | Condition and result |
| --- | --- | --- | --- |
| `build-sdist` | None | `contents: read` | Builds one `.tar.gz` containing the generated `build-constraints.txt` at its root. |
| `attest-sdist` | `build-sdist` | `id-token: write`, `attestations: write` | Runs when `attest` is true. Checks the sdist digest and signs those bytes. |
| `build-wheel` | `build-sdist`, `attest-sdist` | `contents: read`, `attestations: read` | Requires a successful sdist build and attestation, or a skipped attestation with `attest: false`. Skips on cancellation. Checks the embedded lock digest and builds one `.whl` from the sdist alone. |
| `attest-wheel` | `build-wheel` | `id-token: write`, `attestations: write` | Runs when `attest` is true. Checks and signs the wheel. |
| `sbom` | `build-sdist`, `build-wheel` | `{}` | Runs after a successful wheel build unless cancelled. Checks both distribution digests and writes `sbom.cdx.json`. |
| `attest-sbom` | `sbom` | `id-token: write`, `attestations: write` | Runs when `attest` is true. Checks and signs the SBOM. |

All three signing jobs use the same steps. Each downloads its named artifact, checks its file against the producer's SHA-256 output, then runs `actions/attest` with `create-storage-record: false`. The job hashes the resulting bundle and uploads it separately.

The SBOM uses CycloneDX 1.6 JSON. Its root component identifies the package and records the hashes of both distributions. Build-lock components carry hashes and build scope. The job adds declared licences to the package and build components where metadata supplies them. Runtime components carry the wheel's declared requirements, without resolving installed versions or licences.

### Outputs to callers

Callers read these values as `needs.build.outputs.<name>`. A file travels in an Actions artifact. Its expected SHA-256 travels separately in a job output.

| Output | Producer and value |
| --- | --- |
| `sdist-name`, `sdist-sha256` | `build-sdist` reports the sdist filename and file digest. |
| `wheel-name`, `wheel-sha256` | `build-wheel` reports the wheel filename and file digest. |
| `source-date-epoch` | `build-sdist` reports the commit timestamp in Unix seconds. Both builds use it. The job rejects a timestamp more than 300 seconds ahead of the runner clock. |
| `sbom-sha256` | `sbom` reports the SBOM file digest. |
| `bundle-sdist-sha256`, `bundle-wheel-sha256`, `bundle-sbom-sha256` | Each signing job exposes its own `bundle-sha256` under the corresponding workflow output. These digests are available only on attested builds. |

Inside the builder, `build-sdist` also supplies `lock-sha256` to `build-wheel`. Under the default wheel-only resolution rule, the lock step records this digest before running the build backend. Distribution digests describe the files after the backend produces them.

## Project CI

The `build` job has no dependencies and calls the builder with the ceiling above. The `test` job needs `build`, declares `permissions: {}` and uses no deployment environment. The template runs the test on Python 3.10 and 3.14. Each matrix job downloads the `wheel` artifact, checks the named file against `wheel-sha256`, installs it with pytest, removes the checkout's `src` directory and runs the project's tests.

The release selects CI runs by commit SHA, push event and `head_branch` equal to the tag name. It excludes its own run. A branch push with the same name at the same commit can also match. Every matching run must finish successfully, and at least one must reference this repository's `.github/workflows/build.yml`. No CI workflow name is configured.

## Release jobs

A release job requires successful direct dependencies. Only the two publisher jobs enter deployment environments.

| Job | Direct dependencies (`needs`) | Token scopes | Environment and result |
| --- | --- | --- | --- |
| `origin-check` | None | `contents: read`, `actions: read` | Checks the signed tag, signer files, environment protections, tag rulesets and CI. Exports `version`, `prerelease` and `ci-runs` (space-separated IDs of matching runs that used the builder). |
| `build` | `origin-check` | `contents: read`, `id-token: write`, `attestations: write` | Calls the builder with `attest: true` and the tag version. |
| `publish-testpypi` | `origin-check`, `build` | `contents: read`, `id-token: write`, `actions: read` | Enters `testpypi`. Checks the tag and build digests. By default it downloads the wheel from every run in `ci-runs` and hashes the file itself. A missing or different wheel stops staging. This optional comparison alone uses `actions: read` here. |
| `verify-testpypi` | `origin-check`, `build`, `publish-testpypi` | `contents: read`, `attestations: read` | Reads TestPyPI and expects publisher environment `testpypi`. |
| `publish-pypi` | `origin-check`, `build`, `verify-testpypi` | `contents: read`, `actions: read`, `id-token: write` | Enters `pypi` through the configured approval gate. Rechecks protections on both environments, then checks the tag and distribution digests before upload. |
| `verify-pypi` | `origin-check`, `build`, `publish-pypi` | `contents: read`, `attestations: read` | Reads PyPI and expects publisher environment `pypi`. Exports `sdist-provenance-sha256` and `wheel-provenance-sha256` and uploads both provenance files. |
| `github-release` | `origin-check`, `build`, `verify-pypi` | `contents: write` | Checks the eight named assets against producer digests and completes or verifies the release for the tag. |

### Index publication and verification

The publishers use the same per-file rule against their own index. An absent filename goes into the upload directory. An identical SHA-256 skips that file. A different digest fails the job. HTTP 404 on the version lookup means neither file exists. Any response other than 200 or 404 fails the lookup. Only a non-empty upload directory starts trusted publishing, with PEP 740 attestations enabled.

Both verifiers use the same checks. For each expected filename, the digest in the index listing and the digest of the downloaded file must equal the build output.

| Identity check | Required values |
| --- | --- |
| GitHub build attestation for each distribution | Current repository, signer workflow `<owner>/<repo>/.github/workflows/build.yml`, current tag ref and source commit SHA. Self-hosted runners are rejected. |
| Index provenance for each distribution | The response must contain at least one attestation bundle. Every publisher must have `kind: GitHub`, the current `repository`, `workflow: release.yml` and the publisher job's `environment`. |
| PEP 740 signatures | `pypi-attestations` verifies the downloaded distribution against its provenance file and expected repository. The verifier records the provenance digest before invoking the tool. |

The install check takes the hash-pinned wheel from the index under test, with dependencies disabled. A second pip invocation resolves dependencies from PyPI alone, using wheels only by default. The check finishes with `pip check`. Only the production verifier passes provenance files to the GitHub release.

### Polling and retry limits

| Waiting for | Loop in the template |
| --- | --- |
| Tag CI to finish | `origin-check` checks every 30 seconds against a 60-minute deadline. A completed run with a conclusion other than `success` fails immediately. |
| The index to list both filenames | Each verifier sets a 600-second deadline. Its actual sleep intervals are 5, 10, 20, 40 and 80 seconds, then 60 seconds thereafter. The loop checks the deadline after an unsuccessful lookup, before sleeping. |
| GitHub to verify an immutable release | `github-release` attempts verification immediately with its job token. It schedules attempt starts 10 seconds apart when calls finish within that interval. A longer call can consume the remaining time. Each invocation is limited to the time left in the 300-second deadline. Exhaustion fails the job. |

## GitHub release assets

Here, `<sdist>` and `<wheel>` stand for the complete filenames from the builder, including their extensions. The release job reads eight files from seven named Actions artifacts.

| Actions artifact | File attached to the release | Expected digest output |
| --- | --- | --- |
| `sdist` | `<sdist>` | `sdist-sha256` |
| `wheel` | `<wheel>` | `wheel-sha256` |
| `sbom` | `sbom.cdx.json` | `sbom-sha256` |
| `bundle-sdist` | `<sdist>.sigstore.json` | `bundle-sdist-sha256` |
| `bundle-wheel` | `<wheel>.sigstore.json` | `bundle-wheel-sha256` |
| `bundle-sbom` | `sbom.cdx.json.sigstore.json` | `bundle-sbom-sha256` |
| `pypi-provenance` | `<sdist>.pypi-provenance.json` | `sdist-provenance-sha256` |
| `pypi-provenance` | `<wheel>.pypi-provenance.json` | `wheel-provenance-sha256` |

The job rejects multiple visible releases for one tag and unexpected assets on an existing release. A prepared draft keeps its notes. A new draft starts with an empty body. After uploading the assets, the job rechecks the tag's target and reads back the draft by release ID. It publishes only when that draft lists exactly the expected names and digests.

Tags with `aN`, `bN`, `rcN` or `.devN` produce a GitHub prerelease with `make_latest=false`. Other accepted tags, including a plain post-release such as `v1.2.post1`, use `make_latest=legacy`. On a rerun against an already published release, the job compares every asset digest. Both paths require `gh release verify` to succeed if GitHub marks the release immutable.

For the sequence across jobs, see [How a release moves through the pipeline](../explanation/architecture.md). For the values a project supplies and the checks that enforce them, see [Configuration and pins](configuration.md) and [Safeguards](safeguards.md).

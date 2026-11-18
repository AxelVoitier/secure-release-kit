# Configuration and pins

The pipeline reads one project-specific release setting from `pyproject.toml`, the minimum age of a build dependency. The build backend controls what goes into the source distribution (sdist). The workflow files fix the tool versions. GitHub and the two package indexes control who can release.

## Build cooldown

```toml title="pyproject.toml"
[tool.release-pipeline]
build-cooldown-days = 7
```

| Field | Accepted value | Default |
| --- | --- | --- |
| `build-cooldown-days` | TOML integer greater than or equal to zero. Strings, booleans and negative values fail the build. | `7`, from `DEFAULT_BUILD_COOLDOWN_DAYS` in `build.yml` |

The builder subtracts this many days from the Git committer timestamp of the commit being built. It resolves build requirements from files uploaded by that cutoff, including transitive requirements. Setting the value to `0` emits a warning and sets the cutoff to the commit time. A commit more than five minutes ahead of the runner clock fails.

An exact `==` or `===` requirement in `build-system.requires` can exempt its named package. If the latest file upload for that version falls after the cutoff, the builder names the package in a warning and extends only its cutoff. The exemption does not extend to dependencies of the pinned package. A lower bound such as `>=` and a wildcard such as `==1.*` receive no exemption.

## Build backend and package metadata

`[build-system]` must supply both `requires` and `build-backend`. The builder rejects `backend-path`. By default every build requirement must resolve to a compatible wheel, including requirements pulled in by the backend.

The pipeline generates `build-constraints.txt` in the project root. The file must be untracked and included at the root of the sdist, directly beside `PKG-INFO`. Keep it out of ignore rules that your backend honours. The builder compares the embedded copy with the generated file.

| Backend | Inclusion rule for the generated lock |
| --- | --- |
| Hatchling | The default sdist selection includes the file. A custom selection must also include it. |
| setuptools | In `MANIFEST.in`, add `include build-constraints.txt`. |
| flit | In `[tool.flit.sdist]`, include the filename in `include = ["build-constraints.txt"]`. |
| pdm-backend | In `[tool.pdm.build]`, include it in `source-includes = ["build-constraints.txt"]`. |
| poetry-core | In `[tool.poetry]`, include it in `include = [{ path = "build-constraints.txt", format = "sdist" }]`. |

For versions derived from Git, the sdist build needs tags and history. Before the first tag, the backend needs a fallback for CI, such as `fallback-version = "0.0.0"` under `[tool.hatch.version]` with hatch-vcs. The wheel must build from the sdist alone. On a release, the `Version` field in `PKG-INFO` must equal the tag with its leading `v` removed.

Declare the project's own SPDX licence expression in `[project].license`. A backend that supports PEP 639 writes it to the distribution's `License-Expression` field. The SBOM (software bill of materials) takes the project name, version and runtime requirements from wheel metadata. It associates licence data from the installed wheels by normalised package name. It lowercases the name and replaces each run of `-`, `_` or `.` with one hyphen. Declared runtime requirements carry no licence in the SBOM.

## Release signers

The release reads the public signer files from the current default branch. At least one of the following must exist. Other filenames beginning with `.github/release-signers` fail the origin check.

| File | Contents |
| --- | --- |
| `.github/release-signers` | SSH allowed-signers file with authorised principals and public keys. |
| `.github/release-signers.asc` | Armoured OpenPGP public keys for authorised release signers. |

`RELEASE_SIGNERS_SHA256` is a repository Actions variable. It contains one `sha256sum` line per file, in filename order. Each line contains the 64-character hex digest followed by two spaces and the repository-relative path. The origin check compares the set of filenames and checks each digest.

!!! warning "Who can change the signer digest"

    A matching checksum establishes agreement between the variable and the default branch. Independent approval of a key change depends on who can change each. GitHub grants access to repository variables to collaborators on personal repositories and to users with write access on organisation repositories. The setup tool's admin check does not restrict those GitHub permissions. [GitHub variable permissions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables#creating-configuration-variables-for-a-repository)

## GitHub protections

| Object | Required configuration |
| --- | --- |
| Default branch | Active ruleset covering the default branch. Protect changes to the release workflows and signer files. For a team, require code-owner review for `.github/` changes. The admin audit asks GitHub for the effective ruleset rules on the default branch, including inherited rules. It checks whether any rules apply. The audit leaves review policy strength to the administrator. |
| Release tag creation | Active tag ruleset including `refs/tags/v*`, with no excluded refs. Restrict creation. Limit bypass to the release-manager team or, for a solo repository, the repository admin role. The setup tool defaults to the admin role. |
| Existing release tags | Separate active tag ruleset with the same include and no exclusions. Enable `update`, `deletion` and `non_fast_forward` restrictions together. Leave the bypass list empty. |
| `testpypi` environment | Selected branches and tags, with exactly one tag policy, `v*`, and no branch policy. Staging needs no reviewer. |
| `pypi` environment | Same tag policy. At least one required reviewer. Disable administrator bypass. For a team, prevent self-review. For a solo maintainer, allow self-review so the maintainer can approve the waiting job. |

The workflow can see tag rules and exclusions. The admin audit also checks bypass lists, which the workflow token cannot read. A human must confirm that the named release managers are the intended people. Release immutability is a separate, optional repository setting. The final release job detects it automatically.

### Repository visibility

Public repositories on current GitHub.com plans can use tag rulesets, required reviewers and artifact attestations. Private repositories on Free lack the required rulesets. Private repositories on Pro or Team can use rulesets and environments, but required reviewers and artifact attestations on those plans are public-only. Private or internal repositories need GitHub Enterprise Cloud for the full set of controls. The kit's hosted testing covers public repositories. [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets) · [Deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) · [Artifact attestation availability](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)

## Trusted publishers

Each index needs its own GitHub Actions trusted publisher for the package. Enter the GitHub repository owner and repository name in their separate fields. Use the workflow filename without its directory. The kit requires an environment on both records.

| Index | Project | Workflow filename | GitHub environment |
| --- | --- | --- | --- |
| TestPyPI | Staging distribution name | `release.yml` | `testpypi` |
| PyPI | Production distribution name | `release.yml` | `pypi` |

Both uploads use the same built files and therefore the same distribution name. For an existing project, the publisher belongs to that project's publishing settings. For a new project, a pending publisher specifies the intended project name. The index creates the project on the first successful upload. A pending record alone does not reserve the name. [Existing projects](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) · [Pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)

## Workflow pins

The following values belong to the deployed files under `.github/workflows/`. In the kit, those files live under `template/_github/workflows/`.

| Identifier | Shipped value | Locations |
| --- | --- | --- |
| `PYTHON_VERSION` | `3.14.6` | `build.yml` and `release.yml` |
| `UV_VERSION` | `0.11.32` | `build.yml` and `release.yml`. The `setup-uv` step in `ci.yml` repeats the literal version. |
| `DEFAULT_BUILD_COOLDOWN_DAYS` | `7` | `build.yml` |
| `TOOLS_EXCLUDE_NEWER` | `2026-11-01T00:00:00Z` | `build.yml` and `release.yml` |
| `CYCLONEDX_BOM` | `cyclonedx-bom==7.6.0` | `build.yml` |
| `PYPI_ATTESTATIONS` | `pypi-attestations==0.0.30` | `release.yml` |

`TOOLS_EXCLUDE_NEWER` is a fixed UTC cutoff for `uvx` when it resolves the SBOM and verification tools. Moving the date can change their transitive dependencies even if both direct versions stay the same. The kit selects tool releases at least seven days old. These tool installations use version and upload-date constraints. The package build uses a separate generated hash lock. Both workflows also set `UV_NO_CONFIG` to `1` so uv ignores project configuration in `uv.toml` or `[tool.uv]`.

The workflow runs each external action at the commit in its `uses:` line. The release tag in the YAML comment identifies that commit for review. Repeated uses of the same action share a pin.

| Action | Release in template | Commit | Workflows |
| --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | Build, CI, release |
| `actions/download-artifact` | `v8.0.2` | `9000827ccba6bdab643e8b6fd33ac0654aef8333` | Build, CI, release |
| `actions/upload-artifact` | `v7.0.2` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | Build, release |
| `actions/attest` | `v4.2.2` | `1e69f48acb82d1966a394da916b4c1698aa569d6` | Build |
| `astral-sh/setup-uv` | `v10.3.3` | `68559e99cc807c1eb7e9238fd43a15bba460eec2` | Build, CI, release |
| `pypa/gh-action-pypi-publish` | `v1.14.3` | `7245906fb61fa33a13554f9d5fb856fe61758086` | Release |

## Project CI and supported workflow edits

Project CI calls `build.yml` with `attest: false`, tests its installed wheel, and runs on pushes of `v*` tags. The calling job grants `contents: read`, `id-token: write` and `attestations: write`. GitHub checks this permission ceiling even when the called signing jobs are skipped. The example CI file uses `main` for branch pushes and tests Python `3.10` and `3.14`. The branch, supported test versions and test command belong to the adopting project. [Workflow contracts](workflows.md)

| Workflow choice | Shipped behaviour | Effect of a reviewed edit |
| --- | --- | --- |
| CI wheel comparison (optional step) | Staging compares the wheel from CI with the release wheel. | Omitting the comparison accommodates differing builds. CI then establishes that tests passed on the commit, without establishing that CI tested the released bytes. |
| Build dependencies available only as sdists (documented reversal) | Lock resolution and the SBOM licence environment require wheels. | Allowing a source build during resolution moves that dependency's build before the lock digest. Both resolution and the SBOM environment need the corresponding adaptation. |
| Runtime dependencies available only as sdists (documented reversal) | Verification installs runtime dependencies as wheels only. | Allowing source distributions here executes dependency build code during verification. |

For the exact edits and their effects on both index jobs, see [Make supported workflow adaptations](../how-to/adapt.md). [Safeguards](safeguards.md)

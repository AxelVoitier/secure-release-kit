# Install the pipeline

Prepare a GitHub repository to release its pure-Python package. Finish the installation before anyone pushes a release tag. The first tag starts staging, so use ordinary branch CI for the initial build checks.

You need a project maintainer to adapt CI, a repository administrator to set protections, an authorised release signer and a person who can configure publishing on each package index. For a new project that person needs an account on the index. For an existing project they need owner access. One person can hold all four roles. For the scripted settings checks, use Python 3.11 or later and GitHub CLI signed in as an administrator of the target repository.

## Check which controls the repository can enforce

Use the repository's intended visibility and GitHub plan. Public repositories on current GitHub.com plans support the required controls. A private or internal repository needs Enterprise Cloud for the full combination of rulesets, environment reviewers and attestations. The hosted validation for this kit used public repositories. [Deployment environment availability](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments) · [Artifact attestation availability](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)

If the project is private now and will go public before release, prepare the files and run the available CI checks. Mark unavailable controls as pending. After the owner changes visibility, create or reopen the rulesets and environments, inspect their saved policies, and repeat the admin audit below before authorising a tag.

## Bring the template into the project

In a separate kit checkout, select the full commit ID approved for adoption. Use a clean worktree. Review the files at that revision before copying them.

```bash
git -C "$kit" status --short
git -C "$kit" rev-parse HEAD
git -C "$kit" ls-tree -r --name-only HEAD template/_github
```

Here `kit` is the absolute path to that checkout. In the adopting repository, create a working branch. Map each file under `template/_github/` to the same relative name under the project's `.github/`. Copy new files individually. Where a file already exists, compare it first and merge the required entries. Keep existing project CI tests, triggers, dependency update rules and unrelated workflows. The kit's top-level `.github/` serves the kit itself. The hosted test patch belongs only in a test deployment.

Record the upstream repository, full commit ID and local file mapping in the project's [deployment notes](../reference/deployment-notes.md). This is the baseline for its next upstream update.

## Build and test the project's wheel

1. Inspect `[build-system]` in `pyproject.toml`. Supply an explicit backend and its requirements. An in-tree `backend-path` is unsupported. Check that compatible wheels exist for build and runtime dependencies. If a dependency is source-only, review the corresponding [workflow adaptation](adapt.md) before proceeding.
2. Configure the backend to put the generated, untracked `build-constraints.txt` at the root of the sdist. Check custom inclusion and ignore rules. Declare the project's own SPDX licence expression and choose its build cooldown (seven days by default). If the version comes from Git, supply the backend's pre-tag fallback and check that it can build the wheel from the sdist alone. [Backend-specific settings](../reference/configuration.md#build-backend-and-package-metadata)
3. Use the template's `ci.yml` as the integration example. Include pushes of `v*` tags alongside the project's usual triggers. Call the local `build.yml` with `attest: false` and the caller permissions `contents: read`, `id-token: write` and `attestations: write`. Download its `wheel` artifact, verify its digest, install it and run the project's actual test suite against the installation. Adjust the matrix, test dependencies and handling of the source tree to the project.
4. Run CI twice at the same commit with the same tag history. For example, use a successful pull request run, download its `wheel` artifact, then use **Re-run all jobs** to rebuild. Download the new attempt's wheel separately. Take the wheels from separate, successful build attempts. Extract one into `first/` and the other into `second/`.

From their parent directory, compare the wheel names and bytes in Bash. A successful comparison prints the shared SHA-256 digest beside both paths.

```bash
(
  set -e
  shopt -s nullglob
  first=(first/*.whl)
  second=(second/*.whl)
  [[ ${#first[@]} == 1 && ${#second[@]} == 1 ]]
  [[ ${first[0]##*/} == "${second[0]##*/}" ]]
  cmp "${first[0]}" "${second[0]}"
  sha256sum "${first[0]}" "${second[0]}"
)
```

Inspect one build's extracted sdist with `tar -tzf path/to/package.tar.gz`. Confirm that the generated lock sits beside the root `PKG-INFO`. Two CI builds test reproducibility at installation. With the default staging check, the first release will also compare its own wheel with the one CI tested on that tag.

Investigate any mismatch. If reproducibility is unattainable, review the [optional comparison and its cost](adapt.md#when-ci-and-release-builds-produce-different-wheels) and record the decision before enabling publication. Have the project maintainer review and merge the deployment changes.

## Establish release authority on GitHub

Have the signer supply their **public** key. Follow [Configure and rotate release signers](signers.md) to verify its identity, merge the signer file on the default branch and calculate its checksum. The signer handles their private key and passphrase. Agree who can approve changes to that branch and who can update repository Actions variables.

The administrator creates an active ruleset for the default branch that blocks force pushes and deletion. In a team, require code-owner review of `.github/`, including the ownership file itself. Reopen the ruleset and inspect its target, exclusions, review requirements and bypass actors. Agree who may create tags outside the release namespace too. A `v*` rule alone leaves other names to the repository's wider tag policy.

Choose one route for the tag, environment and checksum settings.

Set `repo` to the adopting repository's `OWNER/REPO` before choosing either route.

=== "Preview and apply"

    From the kit checkout, set `reviewer` to the GitHub login responsible for the production gate. For a team, add `--prevent-self-review` to both commands and repeat `--reviewer LOGIN` for additional reviewers.

    ```bash
    python3 tools/repo_settings.py preview --repo "$repo" --reviewer "$reviewer"
    ```

    Review every operation, especially policy deletions and replacement bypass lists. If an existing environment serves another deployment, resolve the conflict first. After approving the displayed changes, copy the printed plan ID into `plan_id`. The administrator runs the matching apply command. If apply reports a different plan, preview and review the current changes before trying again.

    ```bash
    python3 tools/repo_settings.py apply --repo "$repo" --reviewer "$reviewer" --approved-plan "$plan_id"
    ```

    The tool grants the repository admin role bypass when it creates the tag creation ruleset. For a team, use the manual route for a named team policy or replace the role with the intended release managers and inspect the result. Later runs preserve the selected teams or admin role, including when they repair other ruleset settings. An empty, unreadable or unsupported creation bypass list requires manual review. A partial API failure requires a fresh audit and preview before retrying.

=== "Set them in GitHub"

    In **Settings → Rules → Rulesets**, create two active tag rulesets. Both must include `refs/tags/v*` and have no excluded refs. In one, restrict creation and allow only the named release-manager team (admin role for a solo repository) to bypass. In the other, restrict updates and deletions and block force pushes. Leave its bypass list empty.

    In **Settings → Environments**, configure both `testpypi` and `pypi` for selected branches and tags. Each needs exactly one tag policy, `v*`, and no branch policy. Staging requires no reviewer. Production requires at least one reviewer and disabled administrator bypass. For a team, prevent self-review. For a solo maintainer, allow self-review so the release can pass the gate.

    Under **Settings → Secrets and variables → Actions → Variables**, set `RELEASE_SIGNERS_SHA256` to the checksum lines for the public files on the remote default branch. The [signer guide](signers.md) gives the exact format.

After either route, the administrator runs the read-only audit from the kit checkout.

```bash
python3 tools/check_repo.py --repo "$repo"
```

Read each failure and the final list of checks it skipped. Inspect both bypass lists with admin access. Confirm the identities of the release managers and reviewers and the saved self-review policy. Inspect both environments for wait timers or other deployment rules, and confirm that staging has no reviewer. The audit does not check those conditions. The checker recognises an active default-branch rule but cannot decide whether its review policy protects this project. Enable immutable releases in repository settings unless the project needs to keep its published tags or assets editable. The workflow detects that setting.

## Connect both package indexes

The index owner signs in to TestPyPI and PyPI separately. On each site use the distribution name from the project's metadata. For an existing project, add the GitHub trusted publisher in the project's publishing settings. For first publication, configure a pending publisher in the account's publishing settings. Set the GitHub owner and repository to the adopting project. Use workflow filename `release.yml` and environment `testpypi` on TestPyPI and `pypi` on PyPI. Read back all four fields on both sites. [Existing projects](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) · [First publication](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)

On TestPyPI, check the project's owner list. If the project does not exist, the intended owner must arrange a separately authorised TestPyPI upload to claim it. Use a genuine test version distinct from the first planned release. After that upload, confirm owner access and the release workflow's publisher under the project's settings. If another party owns the name, resolve that before tagging. Until ownership is confirmed, record the TestPyPI name claim as pending.

For a new PyPI project, leave its publisher pending until the first authorised production release. A pending publisher on either index leaves the name available to others. Check the name and the publisher again before that first release. [How pending publishers work](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)

## Hand the deployment to its operators

Set up the project's [update and security notifications](notifications.md) and name the person who reviews them. In the project's `SECURITY.md`, tell users which versions receive fixes, for how long and how to report a vulnerability privately. Verify the reporting route. Have the project owner record their assessment of how the EU Cyber Resilience Act applies to this project. Installing these workflows cannot determine that classification.

Call the deployment **prepared** when its files, signer, repository protections, publisher settings and TestPyPI ownership checks are complete. Include the result of the wheel comparison and any approved adaptation in the handoff. Report outstanding controls individually. A successful admin audit covers only the settings it inspected.

Use **TestPyPI validated** when this deployment has published to TestPyPI and verified what the index serves. Name the jobs exercised if a test copy redirected the gated leg. Use **production validated** only after a separately authorised release has passed PyPI publication, verification and the final GitHub release checks. For the next action, choose [Run the full TestPyPI campaign](full-campaign.md) for an isolated test deployment or [Publish a release](release.md) for a real project version.

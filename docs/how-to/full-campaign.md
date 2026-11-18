# Run the full TestPyPI campaign

Use this campaign to test a release workflow on GitHub when local checks cannot exercise its permissions, approval gate or trusted publisher. It produces real packages on TestPyPI and real releases in the chosen test repository. Obtain the owner's authorisation for those changes. The release signer creates the tags, the reviewer decides each deployment and the administrator controls repository and index settings.

## Prepare the isolated deployment

Use a dedicated test repository and a TestPyPI project under your control. For maintenance of the original kit, reuse its existing test repository with the owner's permission. Preserve its tags, releases and history. For an independent deployment, choose your own repository and package name. Set `REPO` to its `OWNER/REPO` and `PROJECT` to its distribution name.

1. Run the [local checks](test.md) against the proposed revision. From the kit root, prepare a disposable copy:

    ```bash
    scratch=$(mktemp -d)
    python3 tools/prepare_testpypi_only.py "$scratch/hosted"
    diff -ru template/_github/workflows "$scratch/hosted/.github/workflows"
    ```

    Expect a diff in `release.yml` only. Both staging jobs have `if: false`. The gated `publish-pypi` job depends on origin and build, checks the CI wheel and uploads to `https://test.pypi.org/legacy/`. Its verifier reads `https://test.pypi.org`. A nonzero exit from `diff` is normal when it shows these changes.

2. In a review branch of the test repository, install **the generated workflows** under `.github/workflows/`. Preserve existing signers and project settings. For a new test package, start with `tests/fixture/`, keeping its licence. Change `project.name` and the distribution lookup in `src/release_pipeline_dummy/__init__.py` to your TestPyPI name. In `pyproject.toml`, set `packages = ["src/release_pipeline_dummy"]` under `[tool.hatch.build.targets.wheel]` so Hatchling still includes that module. Keep the installed-wheel test. Adjust CI's branch trigger if the default branch differs from `main`.
3. Configure the [signers](signers.md) and both protected environments. Restrict each to `v*` tags. The environment **named `pypi` in GitHub** needs a reviewer and administrator bypass disabled. On **TestPyPI**, register the GitHub owner, repository, `release.yml` and that `pypi` environment as the trusted publisher. An existing project owner can add the publisher. For a new name, use a pending publisher and verify ownership after the first successful publish. Keep production PyPI out of this fixture. [Pending trusted publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
4. Have the administrator review the changes, merge them through the test repository's normal process and run `python3 tools/check_repo.py --repo "$REPO"` from the kit checkout. Inspect default-branch protections and both tag rulesets, including their bypass lists. Confirm that default-branch CI builds the sdist, wheel and SBOM and passes its wheel tests. CI skips the three attestation jobs.

!!! note "What passes through the gate"
    CI and release each call the reusable builder. In release, all six builder jobs run, including attestations for the sdist, wheel and SBOM. After approval, `publish-pypi`, `verify-pypi` and `github-release` run. This topology tests the gated jobs against TestPyPI. It skips `publish-testpypi` and `verify-testpypi`, so the ordinary staging-to-gate dependency and the production PyPI service remain untested.

## Probe the installation and make the first release

Before issuing any release tag, inspect the administrator audit and CI job logs. Confirm that CI calls the builder in this repository. Run the [portable step cases](test.md) with valid and invalid inputs.

### Check which refs the environments reject

Copy `tests/hosted/environment-probe.yml` to `.github/workflows/environment-probe.yml` in the dedicated test repository. Have its owner review and merge it. The probe has no publishing permissions. If either environment admits the ref, the job's first step emits an error and fails.

Set `branch` to the test repository's default branch. Create a lightweight tag such as `environment-probe-1` at a commit containing the probe. Use an unused name outside `v*` and have the authorised maintainer push it. Set `probe_tag` to that name. Dispatch the probe for both refs.

```bash
gh workflow run environment-probe.yml --repo "$REPO" --ref "$branch"
gh workflow run environment-probe.yml --repo "$REPO" --ref "$probe_tag"
```

Open both runs. Each job must fail before any step runs, with a message that its environment does not allow the ref. If a job asks for approval, leave it unapproved and stop. If a job reaches its error step, correct the environment policy and rerun the probe before testing releases.

### Publish the first test release

For each release case use a fresh canonical version. Set `TAG` to `v` followed by the version. Check both destinations before signing:

```bash
git ls-remote --tags origin "refs/tags/$TAG"
curl -sS -o /dev/null -w '%{http_code}\n' \
  "https://test.pypi.org/pypi/$PROJECT/${TAG#v}/json"
```

On a successful remote query, expect no matching ref and HTTP 404. An API or network error leaves availability unknown. In the test checkout, confirm that `origin` points to `$REPO` and that the selected commit is on the protected default branch. Start with a prerelease and mutable GitHub releases if the owner authorises the mutable cases. The signer runs:

```bash
git tag -s "$TAG" -m "$TAG"
git -c gpg.ssh.allowedSignersFile="$PWD/.github/release-signers" verify-tag "$TAG"
git push origin "refs/tags/$TAG"
```

Open the release run for that tag. Confirm that origin checked the signature, protections and successful **tag-push CI** at its SHA. The release builder must verify the attested sdist before building the wheel. While `publish-pypi` waits, inspect the pending deployment and its target. Only the designated reviewer approves it.

After approval, check the publisher's environment recheck, CI wheel comparison and per-file selection. The verifier must match the downloaded digests, verify both kinds of attestation for each distribution, install the project wheel and finish `pip check`. Inspect the release:

```bash
gh api "repos/$REPO/releases/tags/$TAG" \
  --jq '{draft,prerelease,immutable,body,assets:[.assets[]|{name,digest}]}'
```

Expect a published prerelease, excluded from latest, with the [eight expected assets](../reference/workflows.md#github-release-assets). Inspect the SBOM's root package and build components against the **current fixture's** declared licences. Runtime requirements carry version constraints and can lack a licence.

## Exercise refusals and reruns

Use a separate tag for each case that changes inputs. Wait for each refusal and inspect the **specific failed step**. If an earlier check fails, that attempt has not tested the intended control. The operator can rerun a reviewed job from the run page or select its numeric database ID:

```bash
gh run view "$RUN_ID" --repo "$REPO" --json jobs \
  --jq '.jobs[] | [.databaseId,.name,.conclusion] | @tsv'
gh run rerun "$RUN_ID" --repo "$REPO" --job "$JOB_ID"
```

Use the run ID and job ID from this attempt in the test repository. Each rerun uses the same tagged workflow revision. [GitHub CLI job reruns](https://cli.github.com/manual/gh_run_rerun)

| Case | Action in the test repository | Pass condition |
| --- | --- | --- |
| Mutable release rerun | Rerun `github-release` on the successful mutable prerelease. Exercise a changed asset digest in the local release-step test. | The hosted rerun leaves assets and notes alone. The local mismatch fails. |
| Immutable final with notes | Have the owner enable immutable releases. Prepare one draft with notes for an unused final tag, then sign and approve the release. | Notes survive. The final uses GitHub's legacy latest-selection rule. Fresh immutable verification succeeds inside the publishing job. |
| Tag form and trust | With distinct unused test versions, have the signer supply an unsigned annotated tag, a lightweight tag and a tag signed by a disposable key outside the signer list. | Origin refuses each at its respective annotation or signature check. No release build or upload follows. |
| Name mismatch | Check the origin step with a local tag-object fixture whose embedded name differs from the event ref. | Origin rejects the object-name mismatch before trusting its signature. |
| Failed CI | Use a fixture commit with a deliberately failing installed-wheel assertion and sign a new tag on that commit. Restore the test in a new reviewed commit afterwards. | Origin refuses the failed tag-push CI. |
| Rejected approval | Reject a pending `pypi` deployment for a fresh tag. | No fixture package or release appears. Use a new tag for another attempt. |
| Protection drift | From the kit root run `python3 -m unittest discover -s tests -p test_portable_steps.py -v`. The fixtures run the actual origin checks with valid rules, a missing reviewer and a tag exclusion. | The valid inputs pass. The invalid inputs fail with the expected reviewer or exclusion message. These checks run locally. |
| Repeat upload | On an ordinary completed release, rerun `publish-pypi`. | A fresh approval is required. Each existing file matches, the upload action is skipped and verification passes. |
| Conflicting drafts | From the kit root run `python3 tools/check_release_drafts.py`. It supplies two drafts for the same tag through the local GitHub CLI double. | Expect `PASS visible duplicates`. The real release step refuses the list before upload or publication. |
| Second signature format | If both formats are available, authorise a test signer in the other format, refresh the checksum and sign a fresh tag. | Origin accepts the configured format. Remove temporary trust through the [signer rotation procedure](signers.md). |

For the hidden-duplicate case run `python3 tools/check_release_drafts.py` locally. In the hidden case the fixture expects the by-ID asset check to stop the release before publication. The printed `PASS` means it observed the refusal. Report this separately from the visible-draft case.

## Recover a partially published version with trusted provenance

Use an unused version, immutable releases enabled and a dedicated **test-only** revision of the generated workflow. A matching hash establishes file identity, but verification also requires the expected publisher's PEP 740 attestation. An sdist uploaded manually cannot establish this result.

1. In the generated `publish-pypi` job, insert the following shell step after `*check-ci-wheel` and before `*hash-rule`. Set `FIXTURE_VERSION` in this step's YAML `env:` to the **literal unused version** chosen for this test. The step must refuse all other versions.

    ```bash
    set -eu
    test "$INDEX" = https://test.pypi.org
    test "$UPLOAD_URL" = https://test.pypi.org/legacy/
    test "$VERSION" = "$FIXTURE_VERSION"
    name=${SDIST%-"$VERSION".tar.gz}
    status=$(curl -sSL --max-time 15 -o /dev/null -w '%{http_code}' \
      "$INDEX/pypi/$name/$VERSION/json")
    test "$status" = 404
    mkdir partial-upload
    cp "dist/$SDIST" partial-upload/
    ```

2. Immediately after this step, copy the normal publisher's exact pinned `uses:` line into a new step. Give it `repository-url: https://test.pypi.org/legacy/`, `packages-dir: partial-upload/` and `attestations: true` under `with:`. Omit the normal publisher's condition on the hash-rule output, since that step runs later. This upload of the sdist uses the same workflow identity and protected environment as the eventual wheel upload.
3. Add one shell step to wait for that specific file. It must see exactly the sdist and its expected SHA-256 before the ordinary hash rule runs.

    ```bash
    set -eu
    name=${SDIST%-"$VERSION".tar.gz}
    url="$INDEX/pypi/$name/$VERSION/json"
    json="$RUNNER_TEMP/partial-index.json"
    deadline=$((SECONDS + 300))
    while (( SECONDS < deadline )); do
      remaining=$((deadline - SECONDS))
      (( remaining > 0 )) || break
      limit=$((remaining < 10 ? remaining : 10))
      status=$(curl -sSL --max-time "$limit" -o "$json" -w '%{http_code}' "$url")
      case "$status" in
        200)
          if jq -e --arg name "$SDIST" --arg sha "$SDIST_SHA256" \
            '(.urls | length) == 1 and .urls[0].filename == $name
             and .urls[0].digests.sha256 == $sha' "$json"; then
            exit 0
          fi
          ;;
        404) ;;
        *) echo "TestPyPI returned HTTP $status"; exit 1 ;;
      esac
      remaining=$((deadline - SECONDS))
      (( remaining > 0 )) || break
      sleep "$((remaining < 5 ? remaining : 5))"
    done
    echo "The expected sdist did not become visible within five minutes"
    exit 1
    ```

4. Leave the existing `*hash-rule` and `*publish` steps in place. Review the whole fixture diff against the generated workflow before the owner deploys it. The signer tags this revision. At the gate the reviewer authorises both TestPyPI uploads. Expect the normal hash rule to skip the identical sdist and select only the missing wheel. Require successful file and publisher verification for **both** distributions.
5. Check that `github-release` publishes and verifies the immutable release inside its 300-second deadline. Read the release metadata and asset digests, then rerun only `github-release`. Expect the rerun to compare the eight digests and verify the immutable release with its own workflow token. Compare the metadata and digests afterwards. Notes and assets must still match.

If the fixture stops after its first upload, inspect the existing TestPyPI file before doing anything else. A publisher rerun would encounter that file at the fixture's initial absence check. If immutable verification expires, the release may already be public. Follow [Recover a failed release](recover.md). A later verification on a workstation cannot establish that the hosted attempt passed.

## Return the test repository to its baseline

Remove the partial-upload fixture in a reviewed change to the test repository. Compare its three workflows with a newly generated TestPyPI-only copy, accounting for intentional local adaptations. Read back the protected environments, signer checksum and tag rulesets. Keep test-only workflows confined to the test repository and temporary copy. Preserve published versions and tags.

Report the revision, jobs exercised, expected refusals and any unchecked paths. For example, a passing gated TestPyPI upload establishes that publisher identity for this repository and environment. Production publication, the skipped staging sequence and private or cross-repository deployments need their own checks.

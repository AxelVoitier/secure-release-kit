# Update tool pins

Prepare a pin change when the maintainer requests it. If installation merely reveals a newer version, report the candidate and keep the current combination. If an advisory applies to the installed version, pause deployment for the maintainer's decision.

## Identify the combination under review

Start on a review branch. In Bash, set `wf=template/_github/workflows` in the original kit, or `wf=.github/workflows` in an adopting project. Adjust the CI path if the deployment uses its own workflow. List every occurrence before editing.

```bash
rg -n 'uses:|PYTHON_VERSION:|UV_VERSION:|keep in sync with UV_VERSION|PYPI_ATTESTATIONS:|CYCLONEDX_BOM:|TOOLS_EXCLUDE_NEWER:|DEFAULT_BUILD_COOLDOWN_DAYS:' \
  "$wf"/{build,ci,release}.yml
```

Use update proposals as leads. Read the publisher's release notes and advisories, check the release date and choose a stable version at least seven days old. Check the action publisher's repository, Python release pages, uv's GitHub releases and both projects on PyPI as applicable. Review breaking changes against the actual runner, Python version and options used in the workflow. [Configure notifications and scans](notifications.md) · [Workflow pins](../reference/configuration.md#workflow-pins)

## Verify each action commit

For each proposed action SHA, look up the exact release tag in the publisher's repository. For example, these commands show how to review the kit's checkout pin. Substitute the action repository and the exact candidate release tag for an update.

```bash
action_repo=actions/checkout
tag=v7.0.1
git ls-remote --exit-code "https://github.com/$action_repo.git" \
  "refs/tags/$tag" "refs/tags/$tag^{}"
```

An annotated tag produces two lines. Use the commit on the line ending in `^{}`. A lightweight release tag pointing directly to a commit produces one line. Require a match with the full commit ID in the proposed `uses:` edit. Stop if the tag is missing or the IDs disagree. Review the changes between the old and new commits, particularly changes to inputs, outputs and permissions. Update every use of that action and the release tag in its adjacent comment.

## Change all copies of a pin

| When changing | Files to edit together |
| --- | --- |
| Python for the release pipeline | Set the same `PYTHON_VERSION` in `build.yml` and `release.yml`. The project's supported CI test matrix is a separate choice. |
| uv | Set `UV_VERSION` in both workflows and the literal `version:` input to `setup-uv` in `ci.yml`. The commit for the `setup-uv` action is a separate pin. |
| SBOM tool | Set `CYCLONEDX_BOM` to the exact `cyclonedx-bom==VERSION` in `build.yml`. |
| Package attestation verifier | Set `PYPI_ATTESTATIONS` to the exact `pypi-attestations==VERSION` in `release.yml`. |
| Resolution date for both tools | Set the same UTC `TOOLS_EXCLUDE_NEWER` timestamp in both workflows. Check that required release files were available by that date and satisfy the tool-age policy. |

A later cutoff admits newer transitive dependencies even if both named tools stay pinned. Treat a date-only change as an update to **both** tools. Exercise SBOM generation and attestation verification with the resulting environment. Keep the package's build cooldown and the builder's fallback cooldown unchanged during routine pin updates. Those settings govern the project's build dependencies, measured against the commit time.

## Check the candidate and hand it over

Repeat the inventory command and compare the duplicate values. In the original kit, update the pin table in the configuration reference alongside the workflow edits. In an adopting project, record the pin differences against the upstream kit revision in the [deployment notes](../reference/deployment-notes.md).

Run the quick checks on the changed workflows, including lint and security settings. Exercise the changed steps on a valid input and a rejected input. For example, a verifier update needs an accepted file and a file with the wrong digest or identity. A local rejection exercises the corresponding check. A claim about the index serving a valid attestation for a hosted release needs an authorised TestPyPI run. [Test a pipeline change](test.md)

For an independent deployment, describe any matching upstream checks and identify hosted behaviour you left untested. For the original kit, run the affected hosted path and relevant failure cases before distributing a newly validated combination. Use the full campaign when the change spans the release path. [Run the full TestPyPI campaign](full-campaign.md)

Stage only the reviewed workflow edits and their corresponding documentation. Read `git diff --cached` and tell the maintainer which pins changed, which checks ran, what failed and which hosted paths remain untested.

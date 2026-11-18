# Test a pipeline change

Start with the claim your change affects. A new action pin needs a syntax check. If that action publishes an attestation, you also need a hosted run to say that the new pin can publish one.

| Change or claim | What to run |
| --- | --- |
| Every update | Parse all three workflows, run the portable tests and lint the changed YAML. Check duplicated pin values against the [configuration reference](../reference/configuration.md). |
| A shell step, API response check or recovery rule | Run the affected step with an input it must accept and one it must reject. Check the failed step and the resulting side effects. |
| Repository protection or signers | Run the settings tests, then the read-only audit against the named deployment with an authorised administrator account. |
| OIDC, attestation identity, index publication, approval, hosted permissions or service discovery | Test the affected behaviour on the actual service. Use the [TestPyPI campaign](full-campaign.md) for release paths. |

## Run the quick checks

From the kit checkout on Linux, use Python 3.11 or later, Bash, Git, GNU coreutils and `patch`. The kit's locked documentation environment includes PyYAML. Use it for the local tests.

```bash
uv sync --locked --group docs
source .venv/bin/activate
python3 tools/quick_checks.py
```

Expect three workflows to parse, followed by passing unit and workflow-step tests. The last lines tell you which linters ran. With `actionlint` and `zizmor` on `PATH`, require both with `python3 tools/quick_checks.py --require-linters`. The command runs zizmor offline. It filters actionlint's diagnostic for the `$/` reusable-workflow form. If your installed actionlint accepts that form, run it on the template without the filter:

```bash
actionlint template/_github/workflows/*.yml
```

Tests for maintenance configuration count the occurrences that Renovate can match. Compare the actual pin values and action SHAs across all three workflows yourself. For a change to deployed protections, run `python3 tools/check_repo.py --repo OWNER/REPO`. Read each finding and the unchecked items. This command reads the chosen repository's live configuration.

### Check an adopting project's files

When the update is in an adopting repository, start with the kit checkout at the recorded baseline or proposed upstream revision. Run its quick suite there. Then lint the **installed** workflow paths in the project checkout, using the same actionlint exception if your version needs it. Point the targeted step tests at those installed files as shown below. If a project split its CI across files, include each affected workflow. A passing test against an unchanged kit checkout says nothing about a local merge error.

## Run one step with two inputs

This example runs the release workflow's actual tag parser. Use Bash in the kit root. The parser needs no network access or GitHub credentials.

```bash
state=$(mktemp -d)
workflow=template/_github/workflows/release.yml
STATE="$state" python3 tools/runstep.py "$workflow" origin-check tag \
  TAG=v1.2rc3 GITHUB_REF=refs/tags/v1.2rc3 GH_TOKEN=fixture DEFAULT_BRANCH=main
cat "$state/outputs"
```

Expect `version=1.2rc3` and `prerelease=true`. Run the same step with a leading zero in the version:

```bash
STATE="$(mktemp -d)" python3 tools/runstep.py "$workflow" origin-check tag \
  TAG=v01.2 GITHUB_REF=refs/tags/v01.2 GH_TOKEN=fixture DEFAULT_BRANCH=main
```

Expect a nonzero exit and a message containing `not v + a canonical PEP 440 version`. If the failure occurs before that message, fix the test inputs before drawing a conclusion about the parser.

## Exercise the control you changed

| Control | Passing case | Rejected case and how to run it |
| --- | --- | --- |
| CI wheel comparison | CI's downloaded wheel matches the build digest. | A different wheel or no CI run fails. Run `python3 -m unittest discover -s tests -p test_portable_steps.py -v`. |
| Repository settings | All required controls and expected signer checksum are present. | Missing controls produce findings. An invalid target is rejected before the API call. Run `python3 -m unittest discover -s tests -p test_repo_settings.py -v`. |
| Draft selection and immutable verification | Matching assets on the selected release pass. A transient verification failure can recover before the deadline. | A wrong asset digest, an unexpected upload destination or verification past the deadline must fail. Run `python3 tools/check_release_drafts.py` with `jq` and GNU `timeout` installed. This is separate from the quick suite. |
| Index hash rule | In a directory containing test distributions, serve matching bytes with `python3 tools/miniindex.py DIR 8080`. Use `http://127.0.0.1:8080` as the step's `INDEX`. A matching file is skipped and an absent file is selected. | Change one local file without changing its expected digest. The same filename with different bytes must stop publication. Use a fresh work directory and the values required by the chosen step. |

For a new case, copy the setup in `tests/test_portable_steps.py`. Supply the workflow's expression values, use a fresh state directory and assert the output or error that identifies the control. To check a deployed workflow, pass its path to `runstep.py`. Running the kit's quick suite alone always tests the kit template.

## Inspect the job graph with act

If your version of act rejects the template's anchors or `$/` form, expand a temporary copy before listing its CI jobs. The expander edits its argument in place.

```bash
copy=$(mktemp -d)
mkdir -p "$copy/.github/workflows"
cp template/_github/workflows/*.yml "$copy/.github/workflows/"
for workflow in "$copy"/.github/workflows/*.yml; do
  python3 tools/expand_anchors.py "$workflow"
done
(cd "$copy" && act push --list -W .github/workflows/ci.yml)
```

The listing checks what act can parse. For host-mode experiments the kit supplies checkout, setup-uv and artifact stubs in `tests/stubs/`. The checkout stub resets and cleans its work directory. Use disposable directories and a fixture checkout. The stubs use local files in place of Actions services. Use GitHub to check job permissions and approvals. Attestation verification also needs the real service. [act usage guide](https://nektosact.com/usage/index.html)

State which controls passed, failed or were skipped. When using checks from an upstream kit revision, identify the workflow and pins they exercised and compare them to the deployed copy. Run any case that a local adaptation changes. A single failed step usually needs a targeted rerun before another hosted campaign.

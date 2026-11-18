# Setup and validation tools

Run the commands from the kit checkout. The repository tools take an explicit GitHub target, even when the current directory belongs to another repository. The workflow tests read the templates inside the kit. Point a test at a deployment copy explicitly when checking an adaptation.

## Repository settings

Both commands use Python 3.11 or later and the GitHub CLI (`gh`) on the invoking machine. They need network access and an authenticated account with administrator access to the target. The audit needs this access to read the ruleset bypass lists. These scripts use the Python standard library.

| Command | Reads or changes |
| --- | --- |
| `python3 tools/repo_settings.py preview --repo OWNER/REPO --reviewer LOGIN` | Reads settings and prints the proposed operations, any signer checksum change and the plan ID. Sends no changes. |
| `python3 tools/repo_settings.py apply --repo OWNER/REPO --reviewer LOGIN --approved-plan ID` | Recomputes the plan. If its ID matches the reviewed preview, applies those operations in order and audits the repository. A mismatch stops before any write. The audit also runs when no changes are needed. |
| `python3 tools/check_repo.py --repo OWNER/REPO` | Reads environment policies, active rulesets (including inherited rules), bypass lists, and signer files and checksum. Prints each failed control. |

For preview and apply, repeat `--reviewer LOGIN` for each individual GitHub user who can approve the `pypi` environment. The list replaces the configured production reviewers. Use `--prevent-self-review` when another reviewer can approve. The tool reads the default branch and hashes its committed public signer files. A local edit cannot supply this checksum.

The preview shows what would change in these GitHub settings:

* **Settings → Environments.** Each of `testpypi` and `pypi` gets a single deployment policy allowing tags matching `v*`. Apply deletes conflicting policies. The `pypi` environment also gets required reviewers and disables administrator bypass.
* **Settings → Rules → Rulesets.** The tool manages two tag rulesets by name. A new creation ruleset allows the repository admin role to create `v*` tags. When updating that ruleset, the tool preserves supported team or admin bypass entries. An empty, unreadable or unsupported creation bypass list needs manual review. The second ruleset blocks updates, deletions and force pushes without a bypass.
* **Settings → Secrets and variables → Actions → Variables.** The tool sets `RELEASE_SIGNERS_SHA256` to one checksum line per public signer file on the default branch. The line includes the path.

The administrator sets default-branch protection separately. The audit checks whether GitHub reports any effective ruleset rules for the default branch. Inspect the rules yourself to make sure that they enforce your review policy. An audit also leaves trusted publishers, TestPyPI project ownership, local workflows and release execution unchecked. The final `NOT RUN` line lists these limits.

| Exit | Meaning |
| --- | --- |
| 0 | The requested preview, apply or audit completed. A preview can show outstanding changes and still succeed. |
| 1 | The audit completed and printed one or more `FAIL` findings. |
| 2 | Invalid input, missing access, a failed prerequisite or command error. Apply also returns 2 if its final audit reports a failed control. |

Apply can stop after some writes have succeeded. Read the current state with `check_repo.py`, then preview the outstanding changes before deciding whether to retry. For settings that need a browser or a separate service, see [Install the pipeline](../how-to/install.md).

## Workflow checks

Use a Linux shell with Python 3.11+, PyYAML, Bash, Git, GNU coreutils and `patch`. Some workflow steps also call `jq`, `curl` or other commands named in their `run:` block. The quick check uses each linter it finds on `PATH`.

| Invocation | Inputs, outputs and limits |
| --- | --- |
| `python3 tools/quick_checks.py [--require-linters]` | Parses the three template workflows, runs tests discovered under `tests/`, then runs available copies of actionlint and offline zizmor. Missing linters print `SKIP` by default. The option makes a missing linter an error. A failed subprocess gives a nonzero exit. |
| `python3 tools/runstep.py WORKFLOW JOB STEP [KEY=VALUE ...]` | Runs one shell step matched uniquely by name or ID. Inherited environment, workflow/job/step environment, prior `GITHUB_ENV` entries, then command-line overrides supply its values. Supply literal values for unresolved expressions. Runs Bash in `WORKDIR` (default current directory) and returns its exit status. |
| `python3 tools/check_release_drafts.py [WORKFLOW]` | Uses the release step, temporary files, `jq` and the fixture `gh` to check draft selection, asset hashes and immutable-release retries. Defaults to the release template. Prints `PASS` for matching expectations, including expected step failures. |
| `python3 tools/miniindex.py DIR PORT` | Serves files directly from `DIR` on loopback until interrupted. Supports version JSON, simple-index pages and distribution downloads. Missing files return HTTP 404. No upload endpoint or Integrity API. |
| `python3 tools/expand_anchors.py WORKFLOW` | **Rewrites the named file in place.** Expands template step anchors and rewrites self-repository workflow calls for act. Run only on a disposable copy. |
| `python3 tools/prepare_testpypi_only.py OUTPUT_DIR` | Creates a new directory with the three deployed workflow paths. Checks that the patched jobs publish and verify on TestPyPI. It also checks the staging skips, job dependencies and presence of the CI wheel comparison. An existing output directory is rejected. A patch or validation failure removes the attempted copy. |

Give each runstep case a fresh `STATE` directory. Steps in the same simulated job can share it. The runner writes outputs to `STATE/outputs`, environment updates to `STATE/github_env` and temporary files under `STATE/tmp`. It executes the step's shell code on your machine. It does not evaluate job conditions, dispatch actions or provide a workflow token.

For tests that call GitHub, the suite prepends `tests/bin` to the test process's `PATH`. Its `gh` reads API responses from JSON files in `FIX`, serves downloaded artifacts from `FIX/run-ID-NAME/` and logs calls to `GHLOG`. Give it temporary paths and fixture values only. The test double implements the calls that its fixtures need. Use the real CLI for the live repository audit.

The [pipeline testing guide](../how-to/test.md) includes working step inputs, an act workflow listing and the expected failures. [Run the full TestPyPI campaign](../how-to/full-campaign.md) describes what the hosted copy exercises.

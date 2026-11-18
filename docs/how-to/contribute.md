# Contribute to the kit

Start in a checkout of the kit. Edit the workflow that adopters will copy under `template/_github/workflows/`. The reusable builder lives in `build.yml` and the tag-triggered release in `release.yml`. The example `ci.yml` shows how project CI calls the same builder and tests its wheel. Keep test packages, service doubles and TestPyPI-only patches under `tests/`. The local commands that exercise the workflows live under `tools/`.

## Make the change reviewable

For a workflow change, identify the job and the claim its step makes. Each job header explains what the job proves and whether it runs third-party code or holds a credential. Keep the commands inline so someone reviewing the workflow can see what runs with those permissions. Consult [Why each step exists](../explanation/step-rationale.md) before moving a check across job or step boundaries.

Keep the imperative step names and their order when changing readability. Write a short `# Proves:` comment above a check step. In a long step, use a `# ---- <claim> ----` comment to separate checks. Give intermediate values names. Put each shell check on its own line or in its own block and use the surrounding step's `fail` helper to explain a rejection. Write the reason in words a maintainer of a copied workflow can understand.

From the repository root on Linux, install the locked documentation environment with uv and run the local suite. You need Python 3.11 or later, Bash, Git, GNU coreutils and `patch`.

```bash
uv sync --locked --group docs
.venv/bin/python tools/quick_checks.py
```

Check which linters ran. For a changed workflow, install actionlint and zizmor and repeat the command with `--require-linters`. Exercise the affected step with an input it must accept and one it must reject. For a pin change, compare every occurrence in [Configuration and pins](../reference/configuration.md). [Test a pipeline change](test.md) gives commands for each kind of check.

## Preview the documentation

Write in British English under `docs/`. Choose the folder by what the reader came to do. A tutorial guides one rehearsal, a how-to helps with a real task, reference gives exact values and explanation gives the reasons. Use a visible admonition for a decision the reader must see before running a command. Use labelled tabs for alternatives and give each Mermaid diagram a caption that explains how to read it.

```bash
.venv/bin/zensical build --strict --clean
.venv/bin/zensical serve
```

Open the local address printed by the server. Follow the links from your page and check that code, diagrams and instructions remain legible on a narrow screen. Press Ctrl+C to stop the preview. Review the diff for private paths, test identities and links a public reader cannot open. Preserve existing licence notices when moving or adapting files.

## Hand the change to the maintainer

State which checks passed, which were skipped and what still needs a hosted run. Before distributing a newly validated combination of pins, the original kit maintainer runs the authorised TestPyPI checks and relevant failure cases. [Run the full TestPyPI campaign](full-campaign.md) describes that work.

Leave commits and pushes to the human maintainer. Use the local preview for review. Every push to `main` starts the **Documentation** workflow, including a pull request merge. The workflow deploys the site after a successful build. To deploy the current `main` revision again, run the workflow manually with the maintainer’s authorisation.

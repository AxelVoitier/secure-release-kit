# Run the portable checks

Run these commands from the kit repository root. Use Python 3.11 or later with
PyYAML installed. Put `bash`, `patch`, and `sha256sum` on `PATH`. The test suite
uses its own `gh` double for workflow step tests. It does not contact GitHub
or a package index.

## Check each update

```bash
python3 tools/quick_checks.py
```

Exit status 0 means that the workflow YAML parses and all local unit and step
tests pass. The command prints `SKIP` for each missing linter. To require both
linters, install `actionlint` and `zizmor`, then run:

```bash
python3 tools/quick_checks.py --require-linters
```

The linter mode requires Git. It runs `actionlint` on the templates with the current `$/` syntax exception, checks an expanded deployment copy without the exception, and runs
`zizmor --offline`. Review the exception when either tool gains support for
the self-repository workflow form. A skipped linter does not count as a passed
lint check.

## Test a changed step

Run the local step cases with:

```bash
python3 -m unittest tests/test_portable_steps.py -v
```

The cases run the template's tag validation and CI wheel comparison through
`tools/runstep.py`. A canonical pre-release tag and matching CI wheel pass.
A noncanonical tag and a different CI wheel fail with the workflow's error.
The test also checks that the hosted TestPyPI copy leaves the template intact.
Add a positive and a negative `runstep.py` case for each control you change.
For index behaviour, start `python3 tools/miniindex.py DIR PORT` with test
distributions in `DIR`. The stand-in has no Integrity API, so it cannot test
PEP 740 verification.

## Prepare a TestPyPI-only hosted copy

Use a new output directory. The command refuses to overwrite one:

```bash
python3 tools/prepare_testpypi_only.py /tmp/kit-testpypi-only
diff -u template/_github/workflows/release.yml /tmp/kit-testpypi-only/.github/workflows/release.yml
```

The command copies the three workflows and applies
`tests/hosted/testpypi-only.patch`. In the copy, the gated `pypi` job uploads
to TestPyPI and the staging jobs are skipped. The command checks the upload
URL, index URLs, job dependencies, and CI wheel step. A patch mismatch exits
nonzero and removes the output directory. Review the diff before using the
copy in an authorised test repository. Configure its `pypi` environment as
a TestPyPI trusted publisher. Keep both protected environments, because the
workflow checks both. The kit does not choose a test repository or TestPyPI
project.

Local success does not establish OIDC, environment approval, hosted runner
permissions, attestations, or package publication. Run an authorised hosted
test when a change affects those behaviours. Keep the test-only patch and
signer files out of `template/_github/`.

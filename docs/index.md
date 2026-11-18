# Secure Release Kit

The kit gives maintainers of pure-Python packages a set of GitHub Actions workflows to copy into their own repository. Your CI tests a wheel. When an authorised signer pushes a release tag, the release workflow checks the tag and the CI result. It builds the source distribution and wheel, stages them on TestPyPI and verifies the files that TestPyPI serves. A reviewer then decides whether those files can go to PyPI.

Your project owns its copy. You choose who can sign a tag and who can approve publication. You also decide when to bring an upstream change into your workflows.

## Where to start

| If you want to… | Start here |
| --- | --- |
| Try the build on your machine | [Rehearse a build locally](tutorials/local-build.md) takes you from a sample package to a wheel without a publishing account. |
| Set up your own package | [Install the pipeline](how-to/install.md) covers your build backend, CI, signers, repository settings and package indexes. |
| Audit the pipeline | Follow a file through the [release architecture](explanation/architecture.md), then find the checks behind each claim in [Safeguards](reference/safeguards.md). |
| Operate an installed pipeline | [Publish a release](how-to/release.md) walks through tagging and approval. If a job stops, use [Recover a failed release](how-to/recover.md). |
| Change the kit itself | [Contribute to the kit](how-to/contribute.md) explains how to prepare a change for review. |

## What has your deployment demonstrated?

A **prepared** deployment has passed its installation checks. **TestPyPI validated** means that deployment published to the staging index and verified the files it served. **Production validated** requires a separately authorised PyPI release, successful verification and the final GitHub release checks.

The template builds one pure-Python wheel. The kit’s hosted tests used a public repository and TestPyPI. Read [Trust and limits](explanation/trust.md) for what those runs exercised and what remains untested.

The kit uses the [Mozilla Public License 2.0](https://www.mozilla.org/MPL/2.0/). The maintainers support the `main` branch until the first kit release, then the latest kit release only. Each adopting project sets its own support policy.

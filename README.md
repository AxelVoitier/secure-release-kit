# Secure Release Kit

This kit gives pure-Python projects a set of GitHub Actions workflows to copy into their own repositories. A signed release tag starts the build. The pipeline uploads the source distribution and wheel to TestPyPI and checks the files it gets back. A reviewer then decides whether to publish those same files to PyPI. The GitHub release carries the distributions, their attestations and a software bill of materials.

Start with [Install the pipeline](docs/how-to/install.md). If an agent is helping you install it, give it the [agent installation guide](INSTALL-AGENT.md). To see what the checks establish, read [Trust and limits](docs/explanation/trust.md).

Read the [documentation in this checkout](docs/index.md) for the revision you are using. After publication, the [documentation site](https://axelvoitier.github.io/secure-release-kit/) will also host the [installation guide](https://axelvoitier.github.io/secure-release-kit/how-to/install/).

## Repository layout

- [template/_github/](template/_github/) contains the files to merge into your project’s `.github/` directory.
- [docs/](docs/) contains the guides and workflow reference.
- [tools/](tools/) contains scripts for repository setup, validation and testing.
- [tests/](tests/) contains the example package, local test fixtures and TestPyPI-only test configuration.

For changes to the kit, see [Contribute to the kit](docs/how-to/contribute.md). To report a vulnerability, see the [security policy](SECURITY.md).

The kit is licensed under the [Mozilla Public License 2.0](LICENSE).

# Obtain runtime dependency licences

To find the licences declared by the packages in your deployment, start with the Python environment you ship. The release SBOM (software bill of materials) lists the library’s declared runtime requirements. Two consumers can satisfy the same requirement with different versions. [What the SBOM describes](../explanation/sbom.md)

## Select the environment to inspect

If you have an isolated deployment environment, use its Python interpreter in the next step. Otherwise, recreate it on the same platform with the same Python version, locked dependencies and optional extras. A fresh install from a version range tells you what resolves today. To inspect an existing deployment, compare the installed names and versions with that deployment before relying on the result.

For a small example, start in an empty directory on Linux or macOS with Python 3, uv and jq installed. These commands create an environment containing one distribution, `packaging` version `25.0`.

```bash
uv venv --python python3 runtime
uv pip install --python runtime/bin/python 'packaging==25.0'
```

## Read the licences from installed distributions

Run CycloneDX against the environment’s interpreter. Replace `runtime/bin/python` with your deployment interpreter when checking your own project. The `uvx` command runs the scanner in a separate environment so its dependencies stay out of the inventory. [CycloneDX environment command](https://cyclonedx-bom-tool.readthedocs.io/en/latest/usage.html#for-python-virtual-environment) · [Kit tool pins](../reference/configuration.md)

```bash
uvx --from 'cyclonedx-bom==7.6.0' cyclonedx-py environment runtime/bin/python \
  --of JSON -o runtime.cdx.json
jq '.components[] | {name, version, licenses}' runtime.cdx.json
```

For the example, look for a single component named `packaging` with version `25.0`. Its two licence entries contain the classifier names “Apache Software License” and “BSD License”. Keep those labels as reported. Two classifiers alone do not tell you whether the terms apply together or offer a choice.

## Follow up on missing or unclear declarations

For a package from PyPI, look up `https://pypi.org/pypi/<name>/<version>/json` using the installed distribution name and exact version. Read `info.license_expression` first. Older releases can carry free text in `info.license` or licence labels under `info.classifiers`. PyPI records metadata from the first upload for a release, so check the installed wheel when the values differ. [PyPI release endpoint](https://docs.pypi.org/api/json/#get-a-release) · [Example for packaging 25.0](https://pypi.org/pypi/packaging/25.0/json)

If a licence is missing or only classifiers appear, inspect the licence files shipped in the installed distribution. For a private or locally modified wheel, go directly to that wheel. For example, list the files installed with `packaging` and open `packaging-25.0.dist-info/licenses/LICENSE` under the reported `Location`.

```bash
uv pip show --python runtime/bin/python --files packaging
```

If the terms remain unclear, record the licence as unknown and ask the publisher. [Python package licence metadata](https://packaging.python.org/en/latest/specifications/core-metadata/#license-expression)

Keep `runtime.cdx.json` separate from the attested release SBOM. It describes the installed versions you inspected. Use the declarations and licence texts to review your intended use. The inventory alone cannot establish whether that use complies with the terms.

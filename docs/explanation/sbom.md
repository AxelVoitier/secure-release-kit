# What the SBOM describes

Suppose an advisory names a Python package that appears in your release. Did the builder use the affected version? Will someone who installs your wheel use it too? The software bill of materials (SBOM) gives different answers to those questions. Build dependencies have exact versions in the build lock. Runtime dependencies come from the requirements in the wheel. The same package can appear in both roles.

## Which release does it describe?

The GitHub release includes `sbom.cdx.json`, a CycloneDX 1.6 document, alongside the wheel and the source distribution (sdist). Its root component, `metadata.component`, takes the project name and version from the wheel. Under `externalReferences`, each distribution has its own filename and SHA-256 hash. A consumer can compare a downloaded file with that hash. Both entries link to the same PyPI release page, even in a TestPyPI rehearsal. The URL alone tells you nothing about whether the files reached PyPI.

The builder generates the inventory after it checks the hashes of both finished distributions. Keeping the inventory outside the wheel lets it identify the exact wheel bytes, including their hash. A separate job attests the inventory itself. Its signed bundle, `sbom.cdx.json.sigstore.json`, ties those inventory bytes to the workflow that produced them. See [how files cross job boundaries](architecture.md#how-a-file-crosses-a-job-boundary) and the [workflow contracts](../reference/workflows.md).

## Why a package can appear twice

For example, suppose the build lock pins `packaging==25.0` and the wheel declares `packaging>=24`. These selected fields from two component entries show how the SBOM preserves both facts.

```json
[
  {
    "name": "packaging",
    "version": "25.0",
    "scope": "excluded",
    "properties": [{"name": "release-pipeline:scope", "value": "build"}]
  },
  {
    "name": "packaging",
    "scope": "required",
    "properties": [{"name": "release-pipeline:requirement", "value": "packaging>=24"}]
  }
]
```

Here `excluded` places the locked version outside the runtime inventory. The custom property identifies its role in the build. A maintainer investigating an advisory can compare the exact version with the affected versions. The second entry preserves the wheel’s full `Requires-Dist` string, including any extras or environment markers. Even though the entry says `required`, those conditions still govern when the requirement applies. The installer chooses a version for its environment and resolves any further dependencies there.

## Whose licence does an entry report?

The lock records versions and hashes. To find declared licences, the SBOM job installs the locked wheels and the project wheel into a temporary environment, without resolving runtime dependencies. It reads licence metadata there and matches it to the root and build components by canonical package name. For example, `Example_Tool` and `example-tool` match because the workflow lowercases names and replaces each run of hyphens, underscores or dots with one hyphen.

A root or build component gets a `licenses` field when its metadata supplies one. The runtime entry has no licence field, even when the same name occurs in the build lock. A licence belongs to a specific distribution, and a runtime requirement alone cannot tell a consumer which distribution they installed. A downstream licence review therefore needs the actual runtime environment and its package licence terms. The release inventory supplies evidence for that review, without certifying compliance. See [Obtain runtime dependency licences](../how-to/runtime-licences.md).

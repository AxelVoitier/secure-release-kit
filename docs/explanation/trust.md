# Trust and limits

A wheel can pass every check in this pipeline and still contain a bug or malicious code. A successful release answers a narrower question. It traces the file an index serves back to a particular build of a signed release tag, and identifies the workflow that published it. The tests, the people who review changes and the dependencies that produce the wheel still matter. For the path the file takes, see [How a release moves through the pipeline](architecture.md).

## Who can authorise a release?

The origin check verifies a signature over an annotated tag, including the name inside the signed object. It checks that the tag points to the expected commit and that the commit belongs to the default branch's history. A valid signature identifies a key on the project's current signer list. The project relies on its release signers to control those keys and on its branch protections and reviewers to control what reaches that history.

The workflow reads signer files from the default branch and checks their names and digests against the repository variable `RELEASE_SIGNERS_SHA256`. Changing only one side fails the check. The independence of those two controls depends on repository access. In an organisation repository, a user with write access can change an Actions repository variable. The digest comparison alone therefore cannot demonstrate approval by a second person. [GitHub repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization)

The workflow can see which tag rules apply and whether the rules exclude any tags. A repository administrator must audit who can bypass them, because the workflow token cannot read the bypass lists. The workflow also checks for a required reviewer on the `pypi` environment. It rejects an explicit `can_admins_bypass: true`. A missing field passes that test. These observations describe what the API exposes at the time of the check. Administrators still control the repository and its protections. In a solo project, the pause for approval can involve the same person who signed the tag.

## What happens if a build tool misbehaves?

A dependency that runs on a hosted runner can change the files and processes in that job. A later check in the same job can catch a packaging mistake, but cannot give independent assurance about that dependency. The kit gives publishing identities and signing permissions to separate jobs that handle files without executing package code. It relies on GitHub to isolate those jobs, enforce their token scopes and deliver job outputs. It also trusts the pinned actions that handle privileged operations.

The job token and the Actions runtime token have different permissions. Even a job with `permissions: {}` can write artifacts and caches through the runtime token. The template does not restore a build cache. When it transfers a file, the consumer hashes the downloaded bytes against a digest carried in a separate job output. An artifact's uploader-supplied digest alone would let the same party provide both the file and its description. A substituted artifact can stop the release. A matching hash establishes agreement with the producer's output, including when the producer itself was faulty.

The build lock records exact versions and hashes. By default, the builder resolves it using wheels only and records its digest before any build dependency runs. A fresh wheel job checks the lock inside the sdist against that earlier value. Allowing source builds during resolution gives dependency code a chance to run before that value exists. Even with the default, a correctly locked backend can produce a compromised distribution. The distribution's digest records exactly what that backend produced.

The build cooldown limits which uploads can enter the lock, using the tagged commit's timestamp as its reference. A newly uploaded dependency ordinarily has to age before a build can pick it up. An exact direct pin can exempt that package, and setting the cooldown to zero removes the waiting period. Neither age nor a matching hash measures the quality of the code. Likewise, the fixed versions and separate resolution cutoff for the SBOM and signature-verification tools constrain which code runs. The workflow still relies on those tools to report accurate results. [Configuration and pins](../reference/configuration.md)

## What do the signatures say?

Two valid signatures over the same distribution answer different questions.

| Evidence | What the verifier checks |
| --- | --- |
| GitHub build attestation | The file digest belongs to a build by this repository's `build.yml` for this tag and commit on a GitHub-hosted runner. |
| Index provenance (PEP 740) | The provenance names this repository, `release.yml` and the expected publishing environment. The verifier checks the attestation signatures against the downloaded distribution. |

This distinction matters during recovery. An index can already hold the right file with the right digest. That lets the publisher skip uploading it again. If the file lacks the expected publisher provenance, however, index verification still fails. A matching digest cannot tell who uploaded it. See [Recover a failed release](../how-to/recover.md#when-an-upload-fails-partway) for the per-file decision after a partial upload.

Project CI tests the wheel from its own build. The default comparison hashes the wheel from each qualifying CI run and compares it with the release wheel. Equality establishes that CI tested the wheel bytes for **this release**. It leaves open whether a build elsewhere or at another time produces identical files. If the project removes that optional comparison, a successful tag CI run still establishes that the tested build passed. The release no longer checks whether it ships those same bytes.

The workflow also depends on services remaining available. For example, a failed CI run on a branch with the same name as the tag can block the poll if it has the same commit. Index outages can interrupt verification after an upload. Refusing to continue protects later steps, but cannot undo publication or guarantee that a release will finish.

## What has run on a hosted service?

A public test project exercised the pure-Python pipeline with TestPyPI as its only upload destination. Its protected publishing job waited for human approval. Hosted runs exercised the shared builder and a comparison with CI's wheel. A partial-upload test recovered a missing wheel after a trusted publisher had already uploaded the matching sdist. Both files then passed the distribution and provenance checks.

A fresh immutable GitHub release passed verification under its publishing job's token. A rerun of the GitHub release job checked the existing eight assets and verified the immutable release again. Earlier immediate checks failed for a cause that remains unknown. The successful runs establish neither a verification latency guarantee nor what happens at the deadline on the hosted service. Local tests cover the deadline and rejection of a draft whose assets landed on a hidden duplicate.

The hosted tests redirected the gated publisher to TestPyPI and skipped the separate staging jobs in that test copy. Production PyPI publication, private-repository protections and a complete cross-repository package build remain untested. The supported template builds one pure-Python wheel. Compiled wheels would need a way to test and trace each platform-specific build.

## What can a downstream user claim?

The kit targets SLSA Build L2, where a hosted platform generates signed build provenance that a consumer can verify. Build L3 adds stronger isolation and protection against a build influencing its own provenance. The project repository controls its copy of the builder. Moving that builder to a separately controlled repository and verifying its identity would change the trust boundary. The template makes no L3 or certification claim. [SLSA Build track](https://slsa.dev/spec/v1.2/build-track-basics)

The release SBOM identifies the package, its locked build dependencies and its declared runtime requirements. Runtime version ranges do not tell a downstream user which versions or licences an installation will contain. The SBOM and provenance can support a product assessment. They cannot determine an adopter's obligations under the EU Cyber Resilience Act, set a support period or show that the adopter handles vulnerabilities throughout that period. Support commitments belong to the project that ships the package. [Cyber Resilience Act, Article 13 and Annex I](https://eur-lex.europa.eu/eli/reg/2024/2847/2024-11-20/eng)

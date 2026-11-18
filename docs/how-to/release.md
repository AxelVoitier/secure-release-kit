# Publish a release

Use this procedure when the project is [prepared for release](install.md) and its release manager has authorised a particular version and commit. Pushing the tag starts a real upload to TestPyPI. Approval at the later gate allows the same distributions onto PyPI.

## Choose the commit and version

Work in the adopting repository. Check `git remote -v` and fetch the default branch and tags. Select the reviewed commit from the remote default branch's history. Confirm that its package metadata will produce the exact version you intend to publish. For example, version `1.4rc1` takes tag `v1.4rc1`. Check that the tag and version are unused on GitHub, TestPyPI and PyPI. See the [accepted version spellings](../reference/workflows.md#tag-and-version).

If you want release notes, prepare one GitHub draft for that tag and leave it unpublished. You can also write the notes after release. With no draft the body starts empty. The tag signature covers the tag message. The workflow takes the release body from the draft, and people with write access can edit it later.

## Sign and push just this tag

The authorised signer runs these commands with their [configured signing key](signers.md). Set `tag` and `commit` to the chosen tag name and full commit ID. Check that `origin` is the intended repository.

```bash
git show --no-patch --oneline "$commit"
git tag -s -m "Release $tag" "$tag" "$commit"
git -c gpg.ssh.allowedSignersFile="$PWD/.github/release-signers" verify-tag "$tag"
git rev-parse "$tag^{commit}"
```

For SSH tags, the verification command uses this checkout's allowed-signers file. For GPG tags, Git uses your local public keyring. The workflow will verify the tag independently against the pinned default-branch files. Compare the displayed commit ID with your chosen ID. If a tool supplies a Markdown tag message, use `git tag -s --cleanup=verbatim -F notes.md "$tag" "$commit"` **in place of** the tag creation command above. This preserves lines beginning with `#`. The human signer handles any passphrase prompt.

After these checks pass, push the single ref.

```bash
git push origin "refs/tags/$tag"
```

## Decide at the PyPI gate

1. Open Actions on the target repository. Find both the CI push run and the release run for the tag. CI must pass on the tagged commit, including tests against its built wheel.
2. Follow `origin-check`, the attested build, `publish-testpypi` and `verify-testpypi`. Open the version on TestPyPI and compare its filenames with the run. The verifier checks downloaded bytes, both kinds of provenance and installation. If a job fails, use [Recover a failed release](recover.md).
3. When `publish-pypi` waits for review, check the repository, tag, commit, staging result and intended production version again. An authorised reviewer approves **this deployment** if those details agree. A team that prevents self-review needs another reviewer. Reject a release that should not ship. A replacement requires a new tag.

## Confirm what shipped

Wait for `publish-pypi`, `verify-pypi` and `github-release`. Open the version on PyPI and the published GitHub release for the tag. Compare the two distribution filenames and their SHA-256 digests with the builder outputs. The GitHub release must also carry the SBOM, three Sigstore bundles and two PyPI provenance files. Inspect the [eight expected asset names](../reference/workflows.md#github-release-assets). For an immutable release, check that the final job passed its release verification.

Alpha, beta, release candidate and development versions appear as prereleases and cannot claim the latest flag. For final versions, including plain post-releases, the workflow lets GitHub select the latest release under its legacy policy.

Report the version and destinations that passed. If PyPI accepted the files but GitHub verification failed, say so explicitly. Operators then know which recovery action is still needed.

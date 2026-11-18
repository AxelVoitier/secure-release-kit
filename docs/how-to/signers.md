# Configure and rotate release signers

Choose who can sign a release tag. The origin check trusts the public keys on the repository's default branch. Before it uses them, it checks the files against a second copy of their checksums in the repository Actions variable `RELEASE_SIGNERS_SHA256`. Keep releases on hold while those two records differ.

## Agree who can change the keys

Ask each signer to confirm their public key fingerprint over a channel you already trust. Identify who can merge a change to the signer files, who can bypass branch review and who can edit repository variables. Organisation repository writers and personal repository collaborators can create repository variables. Assign the checksum update to a repository administrator and review the actual access before relying on two people to approve a key change. Permission to create a release tag is a separate ruleset setting. [GitHub repository variable permissions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables#creating-configuration-variables-for-a-repository)

## Prepare the public keys

Work in the deploying project. Create its `.github/` directory if needed. Use either or both files below. The workflow rejects other names beginning with `.github/release-signers`, including backup copies. Keep private keys with their owners. Each signer configures their own checkout and handles any passphrase or hardware prompt.

=== "SSH"

    Put one OpenSSH allowed-signers entry per key in `.github/release-signers`. Use an identifiable principal followed by the public key type and its base64 data. For example, with the public key in `$pubkey` and the signer's email in `$principal`, run this once to append the entry:

    ```bash
    ssh-keygen -lf "$pubkey"
    printf '%s %s\n' "$principal" "$(cat "$pubkey")" >> .github/release-signers
    ```

    The signer can select that public key if the matching private key is available through their SSH agent. Use an absolute path for `pubkey`.

    ```bash
    git config --local gpg.format ssh
    git config --local user.signingkey "$pubkey"
    ```

=== "GPG"

    Export the complete set of approved public keys in ASCII armour to `.github/release-signers.asc`. Supply their full fingerprints. For example, to prepare a file containing both an existing key and its successor, run:

    ```bash
    gpg --armor --export "$old_fingerprint" "$new_fingerprint" > .github/release-signers.asc
    gpg --show-keys --with-fingerprint --with-subkey-fingerprint .github/release-signers.asc
    ```

    For first setup, export just the approved fingerprint. Check every listed primary key and signing subkey against the intended set. Each signer selects their own key:

    ```bash
    git config --local gpg.format openpgp
    git config --local user.signingkey "$fingerprint"
    ```

## Exercise the same verifier locally

Use a disposable local repository with a commit, no push remote, and disposable keys. Prepare its signer files and Git configuration as above. Set `kit` to the absolute path of the kit checkout. Use a Python environment with PyYAML installed. The commands below run the signature step alone. The tag name deliberately falls outside the release trigger.

```bash
export STATE="$(mktemp -d)"
mkdir -p "$STATE/tmp/signers/.github"
cp .github/release-signers* "$STATE/tmp/signers/.github/"
git tag -s signer-check -m 'Local signer check'
python "$kit/tools/runstep.py" "$kit/template/_github/workflows/release.yml" \
  origin-check 'Verify the tag signature against the pinned signers' \
  TAG=signer-check DEFAULT_BRANCH=main GH_TOKEN=unused
```

Expect exit status zero. For SSH, Git names the matched principal. For GPG, the log contains `VALIDSIG`. Sign a second local tag with a different disposable key, leave the verifier's files untouched and repeat with the second tag name. Expect a nonzero status. Repeat for each format your project uses. Never push the rehearsal tags.

## Set the checksum from the reviewed default branch

Merge the approved public files through the project's usual review. An administrator then runs the kit's preview with the deployment repository and its intended production reviewer. Supply all configured reviewers and the deployment's self-review option when applicable.

```bash
python "$kit/tools/repo_settings.py" preview --repo "$repo" --reviewer "$reviewer"
```

The preview reads the public files from the remote default branch. If the variable differs, it prints a `SET RELEASE_SIGNERS_SHA256` section. Check the paths and hashes against the reviewed files. A checksum line consists of the SHA-256 hex digest, two spaces and the path starting with `.github/`. Include exactly one line per file.

For a signer-only change, copy just those lines into the repository Actions variable under **Settings → Secrets and variables → Actions → Variables**. The setup tool's `apply` command also changes other settings shown in the preview. Use the read-only audit to compare the variable with the default branch again:

```bash
python "$kit/tools/check_repo.py" --repo "$repo"
```

Resolve any signer mismatch before releasing. The audit also reports failures in unrelated repository settings. A passing audit establishes that the files and variable agree. The human signer still needs access to the corresponding private key.

## Retire a key

For a planned rotation, first add the successor alongside the old key. Review the files, update the checksum and confirm the successor can sign. Then remove the old entry, or re-export the GPG file with only the remaining approved keys. If a format has no keys left, remove its file and checksum line together. Keep at least one trusted signer before resuming releases.

For a compromised or revoked key, suspend releases immediately. Remove the key without the overlap period and review any pending releases before resuming. Refresh the pinned public GPG export after an expiry extension or revocation. The verifier uses an empty keyring and the repository's export, so a change made only on a keyserver never reaches it. It rejects expired or revoked signatures reported by GPG. For SSH, removal from the allowed-signers file withdraws trust in that key. A rerun reads the current default-branch files and can therefore reject a tag signed before removal.

See the [signer and repository settings](../reference/configuration.md) and the [origin-check safeguards](../reference/safeguards.md) for the checks that follow signature verification.

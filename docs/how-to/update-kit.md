# Apply upstream kit changes

Use the revision in your deployment notes as the common starting point. Comparing the installed files directly with the latest template can make a local security check look like an upstream deletion.

## Select the two upstream revisions

Start in a clean checkout of the adopting project on a review branch. Read its [deployment notes](../reference/deployment-notes.md) for the kit URL, full baseline commit and installed paths. If the baseline is missing, establish which kit revision supplied the installed files before preparing an update.

Use Bash and Git. Set `kit_url` and `old` from the notes. Set `requested_ref` to the branch or tag the maintainer asked to review, for example `refs/heads/main`. The clone below stores the comparison outside the deployment.

```bash
project=$(git rev-parse --show-toplevel)
scratch=$(mktemp -d)
kit="$scratch/kit"
git clone --no-checkout "$kit_url" "$kit"
git -C "$kit" fetch origin "$requested_ref"
new=$(git -C "$kit" rev-parse --verify 'FETCH_HEAD^{commit}')
git -C "$kit" cat-file -e "$old^{commit}"
git -C "$kit" log -1 --oneline "$new"
git -C "$kit" diff --name-status --find-renames "$old" "$new" -- template/_github
```

Stop if a command fails or the commit differs from the requested revision. Read the upstream diff, including changes to the kit tools or tests that apply to this update. The file list shows additions, deletions and renames as well as edits.

## Reconcile each file

For a file that exists at both revisions, compare all three versions. This example uses the CI workflow. Substitute the correct kit path and installed path from your notes for each file.

```bash
source_path=template/_github/workflows/ci.yml
installed="$project/.github/workflows/ci.yml"
git -C "$kit" show "$old:$source_path" > "$scratch/base"
git -C "$kit" show "$new:$source_path" > "$scratch/upstream"
diff -u "$scratch/base" "$installed"
diff -u "$scratch/base" "$scratch/upstream"
diff -u "$scratch/upstream" "$installed"
```

For `diff`, exit status 1 means the files differ. A higher status means the comparison failed. The first diff identifies your adaptations. The second shows what the kit changed. Use both to edit the installed file, then repeat the third comparison. Its remaining differences should match the adaptations you intend to keep.

If both sides changed the same block, inspect the whole job, including permissions and downstream consumers. For example, an upstream CI change can depend on a new builder output while the project still needs its own Python matrix and wheel tests. Keep both requirements. If they conflict and the maintainer has yet to decide, leave the baseline at the old revision.

For a new file, inspect it at the new revision and check whether its destination already exists. Merge any existing project configuration by hand. For a deletion, check whether the installed file has another purpose before proposing its removal. For a rename, use the old source name in the first `git show` and the new name in the second. Review each destination change explicitly.

## Check the prepared update

Compare the final deployment with the notes. Preserve the build backend, cooldown, signer files, repository protections and trusted publishers. Recheck the reason for each [workflow adaptation](adapt.md). Check which files Renovate and Dependabot will scan after the update. Review any change to service permissions or automatic merging. [Configure notifications and scans](notifications.md)

Run the quick checks against the prepared workflows, then run the local cases affected by the diff. Reuse an upstream result only for a matching revision, configuration and path. Identify any hosted behaviour still untested in this deployment. [Test a pipeline change](test.md)

Once each upstream change is either applied or recorded as an intentional local difference, put the full value of `new` and the revised path map in the notes. Stage the reconciled files and notes by name. Review `git diff --cached` before handing them to the maintainer. For a partial update, keep the original baseline and describe the individual changes carried forward.

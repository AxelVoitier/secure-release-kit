# Deployment notes

Keep one short record in the adopting repository. A maintainer uses it to find the original kit files, compare them with the installed copy and recognise intentional differences. The pipeline does not read this record. Its filename and format belong to the project.

## Fields

| Field | What belongs here |
| --- | --- |
| Kit source | Repository URL and full Git commit ID of the kit used as the comparison baseline. A moving branch name alone is insufficient. |
| Installed files | Map each source path to its destination. Include files merged into existing CI or service configuration and any files intentionally omitted. |
| Project configuration | Build backend, how it includes `build-constraints.txt` in the sdist, default branch, CI workflow, supported Python versions and wheel test command. Point to the source of each value. |
| Release services | GitHub repository and environments, distribution name on each index, reviewer responsible for approval, update services and person who receives alerts. |
| Signers | Paths to the public signer files and the person responsible for rotation and the repository variable `RELEASE_SIGNERS_SHA256`. Keep private keys, tokens and passphrases outside this record. |
| Local changes | Each local pin or workflow edit, the reason it exists and the check or guarantee it changes. Record any upstream change intentionally omitted. |

## Copyable record

Replace the bracketed text. Retain only the signer paths and service files the project actually uses.

```markdown title="Deployment notes"
# Release pipeline deployment

Kit repository: [URL]
Kit revision: [full commit ID]

| Kit path | Deployed path |
| --- | --- |
| template/_github/workflows/build.yml | .github/workflows/build.yml |
| template/_github/workflows/release.yml | .github/workflows/release.yml |
| template/_github/workflows/ci.yml | .github/workflows/ci.yml |
| template/_github/renovate.json | .github/renovate.json |
| template/_github/dependabot.yml | .github/dependabot.yml |

Backend and sdist inclusion rule: [pyproject.toml section or manifest]
CI: [default branch, workflow path, Python matrix, wheel test command]
Release services: [owner/repo, TestPyPI and PyPI projects, environments and reviewer]
Signers: [public paths, responsible maintainer]
Notifications: [Renovate installation, Dependabot alerts, upstream subscription, recipient]
Local changes: [path, edit, reason and effect, or none]
```

A pin update made solely in the deployment is a local change. Advance the kit revision when you finish reconciling an upstream update and can account for the remaining differences. Describe what a test or release actually exercised in the handoff for that work. [Apply upstream kit changes](../how-to/update-kit.md) · [Configuration and pins](configuration.md)

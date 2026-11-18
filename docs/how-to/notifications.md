# Configure notifications and scans

Give one maintainer responsibility for incoming update proposals and security alerts. Each repository needs its own service activation. Copying the workflow files alone does not subscribe the adopting project.

## Enable update proposals

1. In the original kit, use `.github/renovate.json` on the default branch. Its GitHub Actions manager adds `template/_github/workflows/` to the paths it scans. In an adopting project, install `template/_github/renovate.json` as `.github/renovate.json`. If the project already uses Renovate, merge the kit's managers and rules into its active configuration. Preserve the project's other managers and keep automatic merging off for kit updates. [GitHub Actions manager](https://docs.renovatebot.com/modules/manager/github-actions/) · [Custom regex managers](https://docs.renovatebot.com/modules/manager/regex/)
2. Have the repository owner or authorised administrator install the Mend Renovate GitHub App for the selected repository. Review its permissions in the installation screen. For example, it can write workflow files on update branches, open pull requests and create a Dependency Dashboard issue. Confirm the repository appears in the app's installed repository list. [Install Renovate](https://docs.renovatebot.com/getting-started/installing-onboarding/) · [Renovate permissions](https://docs.renovatebot.com/security-and-permissions/)
3. In an adopting project, also review `.github/dependabot.yml` from the template. Its monthly `github-actions` job groups updates and uses a seven-day cooldown. If the project already has this file, incorporate the job into its existing configuration. Inspect the job in the repository's dependency graph under **Dependabot** after a run. The nested copy in the original kit is a template for adopters. [Dependabot configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
4. After Renovate's first run, open the Dependency Dashboard's detected dependencies or the repository job log. Look for the three release-pipeline workflows under the correct directory. Match their extracted packages against the table below. A configuration warning, a failed lookup or a missing file needs investigation even when there are no open update PRs.

| Pin | What to look for | Where to check manually |
| --- | --- | --- |
| External action commits | The action repository and current commit for every external `uses:` line. A deployed copy can receive proposals from both bots. | Release tags and security advisories in the action publisher's repository. |
| Python | `python` in both `build.yml` and `release.yml`. | Python release pages and security announcements. |
| uv | `astral-sh/uv` in both workflow environment blocks and the literal version in the CI setup step. Inspect release lookup as well as file matching. | The current regex expects a leading `v`, while the publisher uses bare tags such as `0.11.32`. Check uv releases manually for updates the service can miss. [uv release tag](https://github.com/astral-sh/uv/releases/tag/0.11.32) |
| SBOM and verification tools | `cyclonedx-bom` from `build.yml` and `pypi-attestations` from `release.yml`, both using the PyPI data source. | Each project's PyPI release history and publisher advisories. |
| Tool resolution cutoff and build cooldown | These are project policies. The release managers choose when either changes. | Check the date and cooldown in [Configuration and pins](../reference/configuration.md). |

To check the shipped file patterns locally, run the following from the kit root. The tests match seven version literals across the workflows in each layout and check the action file patterns. Only a service run can establish that the app can read **your** files and look up releases for those values.

```bash
python3 -m unittest discover -s tests -p test_maintenance_config.py -v
```

## Enable vulnerability alerts

In repository settings, enable the dependency graph and Dependabot alerts. Open the repository's Dependabot alerts page with the maintainer who will receive them. Check that this person can see the page and has selected a delivery channel for security alerts. Review the recognised dependencies in the dependency graph. [Configure Dependabot alerts](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-dependabot-alerts)

GitHub only generates action alerts for semantic versions. The kit pins actions by commit. Workflow environment strings also fall outside the supported package manifests for Python dependencies. When reviewing a release combination, look up advisories for each action and tool in its publisher's security notices and the GitHub Advisory Database. Include transitive packages affected by a tool cutoff change. An empty alerts page leaves these gaps open. [Dependency graph coverage](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems) · [GitHub Advisory Database](https://github.com/advisories)

## Subscribe to changes in the kit itself

From an independent deployment, open the upstream kit repository recorded in the deployment notes. Select **Watch → Custom → Releases** and confirm the selection. If the kit does not publish releases, watch repository activity or compare the upstream revision on request. A subscription to release notifications only delivers published releases. [GitHub watch settings](https://docs.github.com/en/subscriptions-and-notifications/get-started/configuring-notifications)

When an alert arrives, identify the installed revision and the affected pin. If a known vulnerability applies, pause deployment for the maintainer's decision. For ordinary version notices, keep the current combination until an update is requested. Leave the services on their own schedules. A full maintenance session starts at the maintainer's request. [Update tool pins](update-pins.md) · [Apply upstream kit changes](update-kit.md)

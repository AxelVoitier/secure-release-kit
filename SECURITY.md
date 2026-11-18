# Security policy

Report a suspected vulnerability in the Secure Release Kit privately to Axel Voitier at [axel.voitier@gmail.com](mailto:axel.voitier@gmail.com). Keep the details out of public issues and pull requests while the maintainer assesses the report.

Include the kit revision or release, the affected file or workflow step, and what you expected the control to prevent. If the problem appeared in a deployed copy, describe any local changes relevant to the failure. Omit tokens, private keys and other credentials. The maintainer will assess which revisions and deployments are affected and follow up privately about a fix or further information.

## Supported revisions

Before the first kit release, security fixes apply to the current `main` branch. From the first release onwards, only the latest kit release receives security fixes.

Each adopting project maintains its own workflow copy. Its maintainer decides when to apply a kit fix and sets the support period and private reporting route for that project's users. See [Install the pipeline](docs/how-to/install.md) and [Apply upstream kit changes](docs/how-to/update-kit.md).

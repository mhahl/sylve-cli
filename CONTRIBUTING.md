# Contributing

`sylve-cli` is an independent tool. It is not affiliated with or endorsed by
the Sylve project.

## Report a bug

Open an issue at <https://github.com/mhahl/sylve-cli/issues> and include:

- `sylve --version`
- The command you ran, with secrets removed
- Expected output and actual output
- Whether the target is a single node or a cluster

Do not paste bearer tokens. `sylve config view` redacts them by default.

## Propose a change

1. Open an issue for behaviour changes or new commands.
2. Fork the repository and create a branch.
3. Make the change and add or update tests.
4. Run `make lint`, `make type`, and `make test`.
5. Open a pull request. Reference the issue.

## What a good pull request looks like

- One concern per pull request.
- Tests for new behaviour and bug fixes.
- Documentation updated when user-visible behaviour changes.
- No drive-by refactors, formatting churn, or unrelated dependency changes.
- Existing error handling and validation preserved.
- Live tests updated when the Sylve API contract changes.

## AI usage policy

- AI tools may be used to draft code, tests, or documentation.
- Any AI-generated change must be reviewed and understood by a human before
  merge.
- The author is responsible for correctness, licensing, and security.
- Disclose substantial AI assistance in the pull request description.

## Licence

Contributions are accepted under the BSD 2-Clause licence in
[LICENSE](LICENSE).

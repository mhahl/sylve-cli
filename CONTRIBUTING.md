# SYLVE-CONTRIBUTING(7)

## NAME

`sylve-contributing` — bug reporting, patch submission, and contribution conventions for `sylve-cli`

## DESCRIPTION

`sylve-cli` is an independent command-line client and is not affiliated with or
endorsed by the Sylve project. Contributions are accepted under the BSD
2-Clause licence.

## REPORTING BUGS

Open an issue at <https://github.com/mhahl/sylve-cli/issues> and include:

- Output of `sylve --version`
- Exact command line executed, with secrets removed
- Expected output and actual output
- Whether the target is a standalone node or a cluster

Do not include bearer tokens in bug reports. `sylve config view` redacts tokens
by default; never paste output from `sylve config view --show-token`.

## SUBMITTING PATCHES

1. Open an issue before introducing behaviour changes or new commands.
2. Fork the repository and create a topic branch.
3. Implement the change and add or update tests in `tests/`.
4. Update command manuals in `docs/` and `docs/man/src/*.in` (then run
   `make man`) when user-visible behaviour changes.
5. Verify that `make lint`, `make type`, and `make test` pass.
6. Open a pull request referencing the issue.

### Patch Standards

- **Single concern**: keep each pull request focused on one logical change.
- **Test coverage**: include unit tests for new behaviour and regressions;
  update live tests when the Sylve API contract changes.
- **No churn**: avoid unrelated refactors, formatting changes, or dependency
  additions.
- **Safety**: preserve existing validation, error handling, and confirmation
  prompts.

## AI USAGE POLICY

- AI tools may be used to draft code, tests, or documentation.
- Every AI-assisted change must be reviewed, verified, and understood by a
  human before submission.
- The submitting author remains responsible for correctness, licensing, and
  security.
- Disclose substantial AI assistance in the pull request description.

## LICENCE

All contributions are licensed under the BSD 2-Clause licence in
[LICENSE](LICENSE).

## SEE ALSO

[sylve(1)](README.md),
[sylve-devel(7)](docs/developer-guide.md),
[sylve-testing(7)](TESTING.md),
[sylve-licences(7)](THIRD-PARTY-LICENCES.md)

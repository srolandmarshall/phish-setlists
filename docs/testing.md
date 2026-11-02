# Test workflow

Pull requests run the tests under `tests/` that are not marked `slow`. This is
the quick feedback loop and does not need database credentials.

Pushes to `main`, version tags matching `v*`, and manual workflow runs execute
the full `tests/` suite, including tests marked `slow`. Push a version tag and
wait for the full test job to pass before publishing the corresponding
release.

Pytest's default discovery is restricted to `tests/`. Operational scripts in
`scripts/` named `test_*.py` may require a configured development database and
are not collected as part of the CI suite.

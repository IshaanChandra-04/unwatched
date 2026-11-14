# Contributing

## Set up

```bash
uv sync --all-groups
uv run pre-commit install
uv run playwright install chromium   # only for the browser-marked tests
```

## Work

- Branch from `main` and open a pull request, even for your own changes. CI must be green before merge.
- Write the failing test first, then the code that makes it pass.
- Run `uv run pytest` before pushing. `uv run pytest -m "not browser"` skips the tests that need Chromium.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `test:`.
- Keep it small. Standard library first, no helper used by one caller, no option nobody asked for.

## Design records

The design lives in `docs/superpowers/specs/` and the implementation plan in `docs/superpowers/plans/`. A change that alters behaviour described there updates the spec in the same pull request.

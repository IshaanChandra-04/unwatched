# Contributing

## Set up

```bash
uv sync --all-groups
uv run pre-commit install
uv run playwright install chromium   # for the browser-marked tests
```

## Work

- Branch from `main` and open a pull request, even for your own changes. CI must be green before merge.
- Write the failing test first, then the code that makes it pass.
- Run `uv run pytest` before pushing. `uv run pytest -m "not browser"` skips the tests that need Chromium.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `test:`.
- Keep it small. Standard library first, no helper used by one caller, no option nobody asked for.

## Design records

The design lives in `docs/superpowers/specs/` and the implementation plans in `docs/superpowers/plans/`. A change that alters behaviour described there updates the spec in the same pull request.

## Release

1. On a `release/X.Y.Z` branch: set the version in `pyproject.toml`, `src/unwatched/__init__.py` and `.claude-plugin/plugin.json` (the packaging test checks they agree), turn the `## [Unreleased]` notes in `CHANGELOG.md` into `## [X.Y.Z] - <date>`, run `uv lock`, and open the pull request.
2. After the merge: `git tag -a vX.Y.Z -m "unwatched X.Y.Z"` on the merge commit and push the tag. The release workflow builds the wheel and the sdist and publishes them to PyPI through trusted publishing.
3. `gh release create vX.Y.Z --notes-file <the changelog section>`.

One-time setup for PyPI: on pypi.org, add a *pending publisher* for the project name `unwatched` with owner `IshaanChandra-04`, repository `unwatched`, workflow `release.yml` and environment `pypi`; on GitHub, create the `pypi` environment under Settings, Environments. Until that exists the publish step fails and the GitHub release is still made by hand.

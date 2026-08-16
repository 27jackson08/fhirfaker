# Releasing

The upload is the one step in this project that cannot be undone: PyPI never lets a
version number be reused, even after a delete. Everything below exists so that the
irreversible step is the *last* one and the cheapest to get right.

## Before the first release only

1. ~~Push the repository to GitHub.~~ Done — <https://github.com/27jackson08/fhirfaker>.
   CI is green across Python 3.10–3.14, plus conformance, packaging, fidelity and
   terminology.
2. ~~Add `[project.urls]` to `pyproject.toml`.~~ Done.
3. ~~**Register the Trusted Publisher.**~~ Done, and converted from "pending" to a
   normal publisher automatically on first use at 0.1.0. Nothing further is required.
   A pending publisher stays pending until it is *used* — there is no review queue, and
   it never reserved the name; only the first upload did. Recorded for reference:

   | Field | Value |
   |---|---|
   | PyPI project name | `carebundle` |
   | Owner | `27jackson08` |
   | Repository name | `fhirfaker` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

   This is why there is no PyPI token in the repository — there is nothing to leak.
4. ~~Create the `pypi` environment.~~ Done, and restricted by a deployment branch
   policy to `v*` **tags** only, so GitHub refuses to deploy that environment from a
   branch even if a workflow condition were wrong. If you also want a human gate on an
   irreversible action, add yourself as a required reviewer at
   <https://github.com/27jackson08/fhirfaker/settings/environments>.
5. ~~Confirm the copyright holder in `LICENSE`.~~ Confirmed as `Copyright 2026 Jackson`.
6. ~~Decide on the repository name.~~ Decided: the repository stays `fhirfaker`, the
   distribution publishes as `carebundle`. See build doc Section 15 — closed, and not
   to be reopened without new information.

## Every release

Run the sweep first — it is the only item here whose answer changes on its own.

1. **Re-run the prior-art sweep** (build doc Section 2). `tietai-synthea`/PySynthea
   appeared in the gap between the build document being written and Phase 5 shipping,
   and it killed the "no JVM" differentiator. A sweep from last month is not evidence
   about today. Check PyPI, GitHub topics and awesome-lists; if something closer has
   landed, update the README's positioning **before** publishing, not after a commenter
   finds it.
2. ~~Confirm the name is still free.~~ Claimed at 0.1.0. PyPI never lets a version
   number be reused, so a mistaken upload is spent, not fixable.
3. **Update `CHANGELOG.md`**: move `[Unreleased]` content under the new version and
   date it. The release workflow fails if there is no `## [<version>]` section.
4. **Bump `version` in `pyproject.toml`.** Remember what the number means here: seeded
   output changing at all is a **major** bump, because users pin test fixtures to it.
5. **Run the full gates locally** (they also run in CI, but catching it here is faster):

   ```bash
   ruff check carebundle tests
   pytest -q -m "not conformance and not fidelity" --cov    # >=80% coverage
   pytest -q -m "fidelity or conformance"                   # slow, needs a JVM
   python -m build && twine check --strict dist/*
   ```

6. **Rehearse the release pipeline** without publishing:

   ```bash
   gh workflow run release.yml --ref main
   gh run watch $(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   ```

   This runs verify, gates and build and stops there — `publish` is gated on
   `github.ref_type == 'tag'`, and the `pypi` environment additionally only accepts
   `v*` tags. Worth doing whenever the workflow itself has changed: the original CI
   workflow was silently broken for months because nobody had ever watched it run.

7. **Commit, tag, push.** The tag must match the version or the workflow refuses:

   ```bash
   git commit -am "chore: release 0.1.0"
   git tag v0.1.0
   git push origin main --tags
   ```

8. The `Release` workflow verifies the tag against `pyproject.toml` and `CHANGELOG.md`,
   re-runs lint, unit and the **full** conformance matrix, builds, smoke-tests the wheel
   in a clean environment outside the repo, then publishes.

   If `publish` fails because the Trusted Publisher is not registered yet, register it
   and re-run **only that job** — the artefacts from `build` are unchanged and the tag
   does not need to move.

## Publishing by hand

Only if the workflow is unavailable. This skips every gate above, so run them yourself.

```bash
python -m build
twine check --strict dist/*
twine upload --repository testpypi dist/*   # rehearse here first
twine upload dist/*                         # irreversible
```

Rehearse on TestPyPI. It is the only way to see what the page actually looks like
before the version number is spent.

## After publishing

- Verify the install from a clean environment, from outside the repository:
  `pip install carebundle && python -c "import carebundle; print(carebundle.__version__)"`
- ~~Set the repository homepage to the PyPI page.~~ Done at 0.1.0.
- Cut a GitHub Release for the tag so the version is discoverable from the repo, not
  only from PyPI: `gh release create vX.Y.Z --notes-from-tag`.
- Distribution is a separate problem from quality (build doc Section 14). A
  differentiated tool that nobody hears about does not get adopted.

# Releasing

The upload is the one step in this project that cannot be undone: PyPI never lets a
version number be reused, even after a delete. Everything below exists so that the
irreversible step is the *last* one and the cheapest to get right.

## Before the first release only

1. ~~Push the repository to GitHub.~~ Done — <https://github.com/27jackson08/fhirfaker>.
   Check that the first CI run went green; until it has, the conformance and fidelity
   gates are only as fresh as the last local run.
2. ~~Add `[project.urls]` to `pyproject.toml`.~~ Done.
3. **Register the Trusted Publisher** at <https://pypi.org/manage/account/publishing/>:

   | Field | Value |
   |---|---|
   | PyPI project name | `carebundle` |
   | Owner | `27jackson08` |
   | Repository name | `fhirfaker` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

   This is why there is no PyPI token in the repository — there is nothing to leak.
4. **Create the `pypi` environment** at
   <https://github.com/27jackson08/fhirfaker/settings/environments> and, if you want a
   human gate on an irreversible action, add yourself as a required reviewer.
5. **Confirm the copyright holder** in `LICENSE`. It currently reads `Copyright 2026
   Jackson`; use your full legal name if you want it formal.
6. **Decide on the repository name.** `fhirfaker` combines the FHIR mark with another
   word, which is the pattern HL7's trademark policy forbids and the reason
   `fhirforge` and `synthfhir` were rejected in build doc Section 15. The published
   package is `carebundle`, so the distribution name is clean either way — but the
   repository URL is the project's public face, and renaming a GitHub repository is
   cheap (redirects are kept) while renaming one with traction is not.

## Every release

Run the sweep first — it is the only item here whose answer changes on its own.

1. **Re-run the prior-art sweep** (build doc Section 2). `tietai-synthea`/PySynthea
   appeared in the gap between the build document being written and Phase 5 shipping,
   and it killed the "no JVM" differentiator. A sweep from last month is not evidence
   about today. Check PyPI, GitHub topics and awesome-lists; if something closer has
   landed, update the README's positioning **before** publishing, not after a commenter
   finds it.
2. **Confirm the name is still free** if this is the first upload:
   `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/carebundle/json`
   → `404` means available.
3. **Update `CHANGELOG.md`**: move `[Unreleased]` content under the new version and
   date it. The release workflow fails if there is no `## [<version>]` section.
4. **Bump `version` in `pyproject.toml`.** Remember what the number means here: seeded
   output changing at all is a **major** bump, because users pin test fixtures to it.
5. **Run the full gates locally** (they also run in CI, but catching it here is faster):

   ```bash
   ruff check carebundle tests
   pytest -q -m "not conformance and not fidelity" --cov    # 234 tests, >=80% coverage
   pytest -q -m "fidelity or conformance"                   # 12 tests, needs a JVM
   python -m build && twine check --strict dist/*
   ```

6. **Commit, tag, push.** The tag must match the version or the workflow refuses:

   ```bash
   git commit -am "chore: release 0.1.0"
   git tag v0.1.0
   git push origin main --tags
   ```

7. The `Release` workflow verifies the tag against `pyproject.toml` and `CHANGELOG.md`,
   re-runs lint, unit and the **full** conformance matrix, builds, smoke-tests the wheel
   in a clean environment outside the repo, then publishes.

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
- Set the repository homepage to the PyPI page, which only exists once the first
  upload lands — it is deliberately blank until then rather than a 404 on the repo's
  public landing card:
  `gh api -X PATCH repos/27jackson08/fhirfaker -f homepage="https://pypi.org/project/carebundle/"`
- Distribution is a separate problem from quality (build doc Section 14). A
  differentiated tool that nobody hears about does not get adopted.

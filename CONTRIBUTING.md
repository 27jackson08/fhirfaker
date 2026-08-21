# Contributing

Contributions are welcome. One thing here is unusual enough that it belongs before the
setup instructions.

## The evidence standard

**Numbers in this repository come from sources, not from judgement.** Every marginal,
correlation, prevalence and treatment effect is derived from something citable — NHANES
for population distributions, published trials for effect sizes, published formulas for
derived values — and a change that adjusts one of them needs a citation in the same way
a change to a formula would.

This is not ceremony. Three hand-set correlations survived in this codebase for months
looking entirely reasonable, and when they were finally checked against the data all
three were wrong; the height/weight one was wrong in a way that could only happen by
using a pooled figure in a sex-stratified model. Nobody could tell which estimates were
sound until they were checked, so the rule is that they get checked.

Two corollaries worth knowing before you open a PR:

- **Denominators matter more than they look.** NHANES reports blood-pressure control
  over *all* hypertensives at <130/80; HEDIS reports *diagnosed, in-care* patients at
  <140/90. Those are 20.7% and roughly 70% for the same underlying reality. A figure
  quoted without its population is not a target, and four separate mistakes of exactly
  this shape are recorded in Section 18 of the build document.
- **Tuning to a benchmark is the failure mode this project exists to avoid.** Calibrate
  inputs to sources and let outputs fall where they fall. If a published rate is not
  reproduced, that gap is a finding worth publishing — `BENCHMARK.md` documents one that
  was published, explained, tested and confirmed, and one that was predicted and turned
  out wrong.

## Setup

```bash
uv venv && . .venv/bin/activate
uv pip install -e ".[dev]"
```

## Tests, in three tiers

Only the first runs on every PR. Run it constantly; run the others before you push
anything that touches generation.

```bash
pytest -m "not conformance and not fidelity"   # seconds, no JVM, no network
pytest -m fidelity                             # statistical assertions, slower
pytest -m conformance                          # needs a JVM and network
```

The conformance tier runs the official HL7 validator. It needs Java 17+ and downloads
the validator and R4 definitions on first use.

## Things that will fail review

- **A number without a source.** See above.
- **Changing seeded output without saying so.** `seed=42` is byte-identical within a
  major version and people pin test fixtures to it. If your change alters generated
  bytes, regenerate the golden files with
  `pytest tests/test_golden.py --update-golden`, review the diff, and say plainly in the
  PR that output changed — it is a major version bump under the policy in `CHANGELOG.md`.
- **A new fidelity check graded higher than it earns.** Checks are graded by what a pass
  actually proves, and `out_of_sample` means a published relationship the model was *not*
  fitted to. A test pins the count of those, so raising it requires a deliberate edit
  rather than a relabel.
- **Terminology from memory.** Every code and *display string* is verified against its
  source vocabulary by `python -m carebundle.terminology.verify`. RxNav once returned a
  veterinary sulfonamide for a fuzzy "sulfamethoxazole" query, and the wrong answer was
  plausible enough to survive review.

## Adding a clinical profile

Profiles are cheap to add and expensive to add *well*. A profile that ships without
fidelity assertions is decoration, so a new one needs:

- marginals derived from a named population, ideally via
  `python -m carebundle.calibration.nhanes` rather than typed in;
- correlations from the same extraction, computed within sex;
- at least one assertion in `carebundle/fidelity/report.py` that would fail if the
  distribution drifted;
- conformance: `pytest -m conformance` must stay at zero errors.

If you only want different numbers rather than a new clinical picture, you probably want
`calibrate_profile` instead — it takes your own quartiles and inherits everything else.

## Regenerating the derived artefacts

```bash
python -m carebundle.fidelity.report      # FIDELITY.md
python -m carebundle.spec.codegen         # models from the R4 StructureDefinitions
python -m carebundle.terminology.verify   # re-check every code and display
```

The NHANES files are not vendored — they belong to NCHS, they are large, and a stale
copy in the repository would be worse than none. Fetch them, then regenerate:

```bash
python -m carebundle.calibration.fetch    --data-dir nhanes/    # ~18 MB, a couple of minutes
python -m carebundle.calibration.nhanes   --data-dir nhanes/ --emit-targets carebundle/calibration/data/nhanes_targets.json
python -m carebundle.fidelity.transfer    --data-dir nhanes/    # the transfer result
```

The calibration is deterministic: regenerating the targets from a fresh download
produces a file **byte-identical** to the committed one. If yours differs, either NCHS
has republished the files or something in the extraction changed — both worth
investigating rather than committing over.

## Releasing

See [RELEASING.md](https://github.com/27jackson08/fhirfaker/blob/main/RELEASING.md). The
short version: the version lives in `carebundle/__init__.py` and nowhere else, and the
release workflow refuses a tag that disagrees with it or with `CHANGELOG.md`.

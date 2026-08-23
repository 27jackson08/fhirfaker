# Roadmap: competing with Synthea

**Status:** in progress. Phases 0–5 (the build document) shipped; **6, 9 and 11 complete**,
**7, 8 and 10 partly**. Each phase section records what was actually
measured, including the parts that failed.
**Written:** August 15, 2026 · **Last updated:** August 16, 2026

---

## 1. The strategic problem with the obvious plan

The obvious plan is "add disease modules until we catch up." That plan loses, and the build
document already says why in Section 14:

> **Scope creep toward "Synthea but worse."** The moment this tries to simulate full patient
> lifecycles, it competes on Synthea's terms and loses.

That warning is still correct and this roadmap does not overturn it. Synthea has 231 disease
modules, a decade of development, MITRE behind it, and — since
[PySynthea](https://arxiv.org/abs/2606.28346) in May 2026 — a JVM-free Python
reimplementation. Breadth is not winnable. Neither is "easier to install", which was a real
differentiator until May 2026 and is now gone.

> Two details worth having straight, since both were got wrong here at least once.
> PySynthea is a community reimplementation, not an official MITRE release. And the
> `pysynthea` name **on PyPI is a different, unrelated project** — OMOP query tooling that
> merely consumes Synthea output — so anyone checking this claim by installing that name
> will conclude the reimplementation does not exist. It does.

So the plan is not to out-simulate Synthea. It is to **out-validate** it, on ground where
Synthea has a published, peer-reviewed, measured weakness and where this project's architecture
is already the right shape.

## 2. The evidence this is built on

Two findings reframe the whole competitive picture. Both are external and citable, which
matters: this project's positioning rule is that claims are checked, not asserted.

### 2.1 Synthea failed outcome measures in 2019, and no longer does

> **Heading corrected, August 2026.** It read "Synthea fails outcome measures, and it is
> documented" — present tense, on a 2019 citation, which is exactly the framing that let
> the error below survive. Measured against build `d9d07a6`, Synthea scores 74.4% on
> blood-pressure control. The section is kept because the reasoning it contains was sound
> given the evidence available, and because the strategy this project chose was built on
> it. Read it as history.

A validation study in *BMC Medical Informatics and Decision Making* tested Synthea against four
CMS clinical quality measures:

| Quality measure | Type | Synthea | Real (MA) | Real (US) |
|---|---|---:|---:|---:|
| Colorectal cancer screening | process | 68.7% | 77.3% | 69.8% |
| COPD 30-day mortality | outcome | 0.7% | 7.0% | 8.0% |
| Complications after hip/knee replacement | outcome | **0%** | 2.9% | 2.8% |
| Controlling high blood pressure | outcome | **0%** | 74.5% | 69.7% |

Synthea tracks reality closely on the *process* measure and collapses on every *outcome*
measure. The authors' conclusion names the mechanism:

> "Synthea and other synthetic patient generators do not currently model for deviations in care
> and the potential outcomes that may result from care deviations."

**Why this happens is architectural, not a bug.** Synthea's state machines model care
*pathways* — was the patient screened, was a drug prescribed. They do not model *physiological
response* — what the blood pressure actually did after the thiazide started. A pathway
simulator cannot produce a blood-pressure control rate, because control is a property of the
value, not of the pathway.

**This project models clinical state directly.** Analytes are drawn from calibrated joint
distributions; derived quantities are computed from identities. That is the machinery an
outcome measure needs and the machinery Synthea does not have.

`Controlling High Blood Pressure` is the single most common chronic-disease quality measure in
US healthcare. Synthea scores **0%**. This project already emits hypertensive patients with
real blood-pressure distributions. **That gap is the wedge.**

> **The wedge closed, August 2026.** Measured rather than cited, current Synthea scores
> **74.8%** on CBP — 0.3 points from the Massachusetts rate it simulates. The 0% above is
> Chen et al. 2019 and was stale for an unknown length of time because this document
> repeated a citation instead of running the software. The strategy built on that gap is
> retained here as written, and it was wrong: **there is no outcome-measure wedge.**
> `BENCHMARK.md` carries the correction and `carebundle.benchmark.synthea` the harness.
> What is left of the differentiation is evidence discipline and within-visit joint
> structure — both checkable, neither a scoreboard win.

### 2.2 The field's failure mode is exactly what the copula was chosen to prevent

"Synthetic but Not Realistic" (arXiv:2606.08903, 2026) evaluated four generative paradigms
(GAN, VAE, diffusion, masked modelling) on a 50,000-person cardiovascular cohort and found:

> "models with strong distributional fidelity can exhibit poor calibration and distorted
> relationships, leading to unreliable inference"

and that **none** of the four simultaneously preserved subgroup structure, effect estimates and
dependency relationships.

Preserving dependency relationships is the copula's entire job here. Preserving effect
estimates is what asserting the ADAG slope and R² in CI already does. Preserving subgroup
structure is what age/sex-stratified, per-profile marginals already do. The paper proposes a
three-dimension evaluation framework — **descriptive fidelity, clinical utility, structural
validity** — and the honest read is that this project is closer to satisfying it than the
generative-model literature is, and does not currently say so.

### 2.3 The other documented gap: synthetic data is too clean

Recurring in the literature: real EHR extracts contain transcription errors, missing fields,
inconsistent formatting and local coding conventions that Synthea output does not have. For the
actual use case here — testing your application — clean data is the *wrong* data. Software that
only ever sees well-formed bundles has untested error paths, and the bug reaches production the
first time a real feed arrives.

Nobody in this space generates realistic imperfection on purpose.

## 3. The positioning this produces

> Synthea simulates **care pathways** across a lifetime.
> This simulates **clinical state** with evidence that the numbers are right.
>
> Where those two overlap, Synthea wins on breadth. Where they diverge — outcome measures,
> analyte relationships, statistical defensibility — it scores zero and this does not.

This is a claim that can be *measured*, published, and re-checked in CI. It is not a claim about
ergonomics, which is what the last differentiator turned out to be worth.

## 3a. When the README stops saying "you probably should use Synthea"

The README currently opens the comparison with *"You probably should use Synthea."*
That will not be true forever, and the temptation to drop it will arrive well before
the evidence does — which is why the conditions belong here, written down now, while
being honest about them is still free.

**The framing flips when the evidence table flips, not when it feels earned.**
Specifically, all four of:

1. **Three or more out-of-sample checks**, not one. Today the fidelity report grades 1
   of 58 that way, and a single measure is an anecdote with a CI job attached. Note
   that the count has moved only in the denominator: the metabolic-cluster work added
   twelve checks and none of them is out-of-sample, because they are fitted to the same
   survey that supplies the marginals. Growing the report does not grow the evidence.
2. ~~**At least two of the four CMS benchmark measures reproduced.**~~ **Withdrawn as
   unreachable — see below.** Replaced by: **at least one further quality measure
   reproduced from the reachable class**, defined below, or an explicit statement in
   `BENCHMARK.md` that no further measure is reachable and why.
3. **A defensible answer to "what do I lose"** for the common case. Right now that
   answer is "231 disease modules and a lifetime per patient", and it is disqualifying
   for most people who arrive wanting a population to analyse.
4. **Someone other than the author has run it.** Real issues from real users, or a
   preprint that survived review. Self-assessed superiority is not evidence, and this
   project's entire pitch is that it does not assert things it has not checked.

**Until then the current wording stays**, because it is accurate and because it is
load-bearing: a reader who has been told the honest limitation up front believes the
benchmark table. One who has been oversold checks it, finds the three "not modelled"
rows, and disbelieves everything else on the page — including the parts that are true.

**What changes in the meantime is emphasis, not claim.** It is already fair to lead the
Synthea section with what this does that Synthea measurably does not, and let "use
Synthea for breadth" follow rather than open. That is a reordering of true statements.
Replacing them is what needs the four conditions above.

**A note on the failure mode this guards against.** The tempting move is to grow the
out-of-sample row by relabelling existing checks. A test pins that count at 1 precisely
so it cannot happen quietly, and condition 1 above should be read as "three checks that
would each survive an outsider asking *what was this fitted to?*".

### Why criterion 2 was withdrawn

Three of the four benchmark measures — colorectal screening, COPD 30-day mortality,
hip/knee complications — need **Procedure** resources. Under this project's licensing
position they cannot be coded realistically:

* Screening colonoscopy in the US is **CPT 45378**, and CPT is AMA-licensed. Same for
  hip and knee replacement.
* SNOMED CT requires an affiliate licence and bars redistribution.
* **ICD-10-PCS is public domain and US Core explicitly accepts it** for `Procedure.code`
  under an *extensible* binding, so a colonoscopy could be emitted with `0DJD8ZZ` and
  would validate. It was checked and rejected anyway: ICD-10-PCS is **inpatient facility**
  coding. Screening colonoscopies happen in ambulatory settings, where no real US system
  emits a PCS code for one. It would be conformant and wrong.

Recorded explicitly so this is not rediscovered and adopted as a shortcut. Emitting a
code no real system emits, in order to unlock a benchmark row, is precisely the
self-deception the rest of this document exists to prevent — the row would be won by
generating data that fails the realism claim it is supposed to evidence.

**So criterion 2 as written was not a bar, it was a veto**: unreachable without a
licensing change, and therefore incapable of ever being satisfied. A gate that cannot
open is not a gate. Replacing it is legitimate; weakening it would not be, so the
replacement is deliberately not easier — it still demands a *new* reproduced measure,
and the reachable class is genuinely narrow.

**The reachable class** is quality measures defined over labs, vitals and diagnoses,
which this project codes with LOINC and ICD-10-CM and can therefore emit realistically.
`Controlling High Blood Pressure` is one. `CMS122 Diabetes: HbA1c Poor Control (>9%)`
looked like another and was attempted — it is coding-reachable and still not usable.

**CMS122 was investigated and rejected, with evidence.** CMS publishes three national
rates for it in the same year — 11.70% (Medicare Part B claims), 27.30% (MIPS CQM),
43.53% (eCQM) — because the numerator is "…is >9.0% **or is missing, or was not
performed**". The measure sums glycaemic control with testing completeness, and a
generator where every diabetic has an HbA1c can only ever reproduce the first half.
Publishing a match would compare two different quantities. Full write-up in
`BENCHMARK.md`.

**So the second branch of criterion 2 is now satisfied**: `BENCHMARK.md` states
explicitly which further measures are reachable and why the two strongest candidates are
not. That is the honest outcome, and it is worth more than a row would have been — the
finding generalises to any measure whose numerator counts missing data, which is a
structural limit on benchmarking synthetic generators at all, and it applies to Synthea
equally.

**The one route that would work** is modelling the missing-data component deliberately
with `carebundle.imperfection`, which already omits fields on purpose. That would let a
measure like CMS122 be reproduced as specified rather than as reinterpreted. It is the
most promising remaining benchmark work and is not currently scheduled.

## 4. Phases

Same contract as the build document: every phase has an exit criterion that is machine-checkable,
or it is not a phase.

| Phase | Content | Exit criterion |
|---|---|---|
| ~~**6. The benchmark**~~ **done** | Reproduce the published CQM study against our output | **Met at 64.1%** vs Synthea's published 0%; asserted in CI. See `BENCHMARK.md` |
| **7. Treatment response** *(part done)* | Bounded longitudinal: analyte trajectories under therapy | **BP titration done — hypothesis confirmed, 64.1% → 71.5%.** HbA1c/metformin trajectories and multi-visit encounters still open |
| **8. Evaluation as product** *(part done)* | Adopt the three-dimension framework; publish it | **FIDELITY.md restructured** — every check graded by evidential strength, out-of-sample count pinned by test. Preprint still open |
| ~~**9. Realistic imperfection**~~ **done** | Opt-in messiness with labelled defects | **Met.** `carebundle.imperfection`, five defect kinds, all enumerable; CI asserts conformance holds when off and genuinely breaks when on |
| ~~**10. Breadth that pays**~~ **started** | More profiles, more US Core profiles | **`anaemia` added** with eight fidelity assertions and zero conformance errors. The bar held: a prescription with nothing behind it was cut rather than shipped |
| ~~**11. Calibrate to your population**~~ **done** | Fit marginals from user-supplied aggregates | **Met.** `calibrate_profile` takes medians and quartiles and reproduces them, inheriting correlations, computed identities and conformance |

### Phase 6 — The benchmark — **complete**

> **Result: 64.1%**, against Synthea's published 0% and a US comparator of 69.7%.
> Full write-up in [BENCHMARK.md](BENCHMARK.md). Three things worth recording:
>
> * The starting point was **21.4%**, not 0% — the pre-existing `HYPERTENSIVE`
>   marginal modelled *untreated* pressure, so some patients already fell under
>   140/90 by accident of its lower bound.
> * The fix was not a new marginal but a **computed identity**: the copula draws a
>   pre-treatment pressure and the recorded pressure is computed from the regimen the
>   patient actually received (Law 2003 effect sizes, per distinct drug class,
>   sequentially). Treatment prevalence is solved against NHANES rather than typed.
> * The remaining **5.6-point shortfall was published rather than closed**. Its most
>   likely cause is dose titration, which is precisely Phase 7 — so the gap is now a
>   testable hypothesis instead of a number someone tuned away.
>
> This also broke the determinism contract, which was the right time for it: seeded
> output changed, and doing that before the first PyPI upload costs nothing while
> doing it after costs a major version.

### Phase 6 — original plan (retained for the record)

**This is the highest-leverage work in the document and the cheapest.** It is mostly measurement
of what already exists.

Build `carebundle.benchmark`: compute CMS clinical quality measures over generated bundles, the
same four the validation study used. Then publish `BENCHMARK.md` with our column beside
Synthea's published column and the real-world column.

Realistic scope on day one: only **Controlling High Blood Pressure** is reachable now, because
it needs hypertensive patients with BP observations and those exist. The other three need
procedures, mortality and longitudinal follow-up that are Phase 7 or out of scope. **Say so in
the table.** A benchmark that quietly omits the measures we lose is the same dishonesty this
project has spent five phases avoiding — publish the row with "not modelled" and let the
comparison be real.

Exit: the generated hypertensive cohort's BP control rate lands within the published real-world
band (69.7–74.5%), asserted in the fidelity suite with a tolerance that is meaningful but not
knife-edge, against Synthea's published 0%.

Watch for: the control rate is a *policy* choice as much as a measurement — it is set by how
many hypertensives are modelled as treated-and-controlled. That must be calibrated to a cited
source (NHANES has hypertension control rates directly) rather than tuned until the benchmark
passes. **Tuning the generator to hit the benchmark is cheating, and it is the single easiest
way to destroy this project's credibility.** Calibrate to the source; let the benchmark be the
independent check.

### Phase 7 — Treatment response — **partly done**

> **The Phase 6 hypothesis was tested and held.** Phase 6 published a 5.6-point
> shortfall and named dose titration as the cause. Modelling titration moved the CBP
> rate from 64.1% to **71.5%**, between the US (69.7%) and MA (74.5%) comparators.
>
> This counts as a genuine test rather than a fit for three reasons, all recorded in
> `BENCHMARK.md`: the titration effect size comes from a *different* study than the
> base effect (Lancet 2025, 1.5 mmHg per doubling); escalation is conditional on being
> above goal, so it cannot inflate the rate by pushing already-controlled patients
> further down; and the two-doubling ceiling was fixed on clinical grounds before the
> rate was measured.
>
> **Non-adherence: predicted, tested, rejected.** The prediction was that adding it
> would push the rate down. It does — to 50.4% (binary) or 49.3% (PDC-scaled), roughly
> 20 points *below* reality. Right about direction, badly wrong about magnitude, so the
> naive term is a worse model rather than a missing one and is not shipped. The reasons
> are in `BENCHMARK.md`: population-wide adherence figures do not transfer to a
> denominator already selected for engagement with care, and "non-adherent" is not
> "untreated". Modelling it properly needs a dose-response formulation and a
> denominator-matched source.
>
> **The stated exit criterion for this phase was wrong, and is corrected below.** It
> read "metformin lowers HbA1c by a published effect size, asserted in CI". Implementing
> that would double-count treatment, because BP and HbA1c are *not symmetric* in this
> model:
>
> * Blood pressure marginals are clinical definitions of the **untreated** population —
>   the module docstring says so explicitly — which is exactly why subtracting a
>   treatment effect from them was correct.
> * The diabetic HbA1c marginal is fitted to NHANES quartiles for **observed**
>   diabetics, who are predominantly already on therapy. It is already post-treatment.
>
> Measured rather than argued: applying a 1.0-point metformin effect on top moves the
> HbA1c median from 7.41 to 6.88, 0.52 below the NHANES target the fidelity suite
> asserts, and puts **32% of diagnosed diabetics under the 6.5% diagnostic threshold** —
> a diagnosed diabetic whose own labs say they are not diabetic. A regression test now
> pins that invariant.
>
> **Corrected criterion.** Doing this properly means re-deriving the diabetic HbA1c
> marginal as *pre-treatment* and solving so the observed mixture still reproduces
> NHANES — a deconvolution, not a subtraction. It buys internal coherence (an untreated
> diabetic should not look like a treated one), not better fidelity, since the observed
> distribution is pinned either way. Worth doing, but it is not the cheap win the
> original wording implied.
>
> **Multi-visit encounters: done.** `generate_history` emits one patient across N
> reviews with the pressure falling as therapy is escalated, closing the caveat
> `BENCHMARK.md` recorded — that titration was modelled as an equilibrium rather
> than a trajectory. It reuses the Law 2003 and Lancet 2025 effect sizes, so it adds
> no new evidence claims, and it is a separate entry point so no existing seeded
> output changed.
>
> **Still open:** the HbA1c deconvolution above, which measurement showed is lower
> value than this document originally implied.

### Phase 7 — original plan (retained for the record)

The mechanism behind Synthea's zeroes, and the thing that makes outcome measures possible.

Model a bounded trajectory: a patient on therapy, sampled at N encounters, with analytes
responding to treatment at published effect sizes. Not a lifetime. Not disease progression
modules. A chronic condition under management for a bounded window.

- Metformin monotherapy lowers HbA1c by roughly 1.0–1.5 percentage points — a well-published
  effect size with confidence intervals.
- Antihypertensive response by drug class, likewise.
- Non-response and non-adherence as explicit modelled fractions, because "deviations in care"
  is precisely what the validation study says nobody models.

Exit: an assertion that generated HbA1c declines by the published effect size, with the
published scatter, over a modelled course. Same standard as the ADAG assertion — reproduce the
relationship *including its variance*, not just its direction.

This keeps the Section 14 line intact. Trajectories under treatment are not lifecycle
simulation; there is no birth, no death, no 231 modules, no comorbidity cascade. It is the
existing distributional model given a time axis.

### Phase 8 — Evaluation as the product — **part done**

> **The report was over-claiming, and grading it was the fix.** "37/37 checks passed"
> reads as strong external validation. Grading them by what a pass actually proves
> shows the real position: of 58 checks, **1** is out-of-sample, 50 are calibration
> round-trips against marginals fitted to NHANES, 3 verify the sampler reproduces its
> own configuration, and 4 are identities that cannot fail unless the code is broken.
>
> None of that is new weakness — the checks are exactly as strong as they always were.
> What changed is that the report no longer lets a reader mistake self-consistency for
> fidelity, which is precisely the criticism arXiv:2606.08903 makes of the field.
>
> The single out-of-sample check is the CMS blood-pressure measure, now included in the
> fidelity report as well as `BENCHMARK.md`. A test pins the count at 1, so a future
> out-of-sample claim has to be argued for rather than arrived at by relabelling —
> which is the failure mode grading would otherwise invite.
>
> **Clinical utility: done.** Train-on-Synthetic-Test-on-Real gives AUC 0.621 against
> a real-data ceiling of 0.677 — 92% retention — predicting diagnosed diabetes from
> non-glycaemic features on 1,330 real NHANES individuals. Graded `calibration`
> rather than `out_of_sample`, because the marginals came from the same survey; the
> pinned out-of-sample count stays at 1. `carebundle/fidelity/transfer.py`.
>
> **Still open:** the preprint.

### Phase 8 — original plan (retained for the record)

Restructure the fidelity report onto the published three-dimension framework: descriptive
fidelity, clinical utility, structural validity. Add clinical-utility evidence — that a model
trained on generated data transfers, or that an effect estimate computed on generated data
matches the published estimate.

Then write it up. The literature says evaluation is the field's open problem; this project has
an unusually strong evaluation story and no publication. A preprint plus the benchmark is the
distribution strategy that Section 14 flags as necessary and that building alone does not
provide.

### Phase 9 — Realistic imperfection — **complete**

> Shipped as `carebundle.imperfection` with five defect kinds: `missing_field`,
> `duplicate_entry`, `out_of_order_timestamp`, `unparseable_value` and
> `unknown_code_system`. Both hard constraints are enforced by tests rather than by
> intention — `Imperfection()` is a no-op, and a conformance-marked test asserts that
> the clean bundle validates with zero errors while the dirtied one genuinely fails
> the HL7 validator (32 errors on the sample). A "malformed" fixture the validator
> accepts would exercise none of the error paths it exists to exercise.
>
> Injection is seeded, never mutates its input, and returns the defects it applied so
> a caller can assert against them.

### Phase 9 — original plan (retained for the record)

Opt-in, off by default, and every defect labelled:

- Missing must-support fields where real systems omit them
- Plausible coding variance — the same concept coded two ways across encounters
- Duplicate and near-duplicate records
- Timestamps that arrive out of order
- Values at implausible-but-real extremes

Two hard constraints. Conformance must stay provable with imperfection off — that is Layer 1
and it is not negotiable. And every injected defect must be machine-readable, so a user can
assert "my parser rejected exactly the three bad records" rather than eyeballing it.

This is the feature with no competitor at all, and it is directly aimed at what people actually
do with this library.

### Phases 10–11

Breadth, but only where it pays: each new profile ships with fidelity assertions or it is
decoration. And calibration from user-supplied aggregate statistics — health systems have
their own distributions and cannot share their data; letting them shape output from summary
stats alone is a capability Synthea structurally cannot offer.

## 5. How to make it happen

**Sequence.** 6 → 7 → 8 is the spine, and it is ordered by leverage. Phase 6 is days of work
mostly spent measuring what exists, and it produces the headline. Phase 7 is the real
engineering. Phase 8 converts both into reach. Phases 9–11 are parallelisable afterwards and
9 is the one users will ask for first.

**The one thing that must not slip.** Every number published in the benchmark has to come from a
cited source and be re-checked in CI. This project's entire credibility rests on the difference
between measured and asserted, and a benchmark is exactly the artefact where the temptation to
tune runs highest. Calibrate to sources; let benchmarks check.

**What would make me abandon this.** If Phase 6 shows the BP control rate cannot be reproduced
without tuning the generator to the answer, the wedge is not real and the roadmap should stop at
Phase 6 rather than proceed on a claim that does not survive its own test.

**Re-run the prior-art sweep first.** It cost the "no JVM" differentiator once already, in the
gap between the build document and shipping. Before committing to this roadmap, check whether
anyone has moved on outcome-measure fidelity.

## 6. Sources

- [The validity of synthetic clinical data: a validation study of Synthea using clinical quality measures](https://pmc.ncbi.nlm.nih.gov/articles/PMC6416981/) — *BMC Med Inform Decis Mak*; the four-measure table and the "deviations in care" conclusion
- [Synthetic but Not Realistic: The Evaluation Challenge in Generative Modelling for Structured EMRs](https://arxiv.org/abs/2606.08903) — the three-dimension framework; no paradigm preserved structure, effects and dependencies together
- [Evaluating Synthea (OHDSI 2024)](https://www.ohdsi.org/wp-content/uploads/2024/10/41-Wagner-Evaluating_Synthea-Clair-Blacketer.pdf)
- [A novel method to create realistic synthetic medication data](https://academic.oup.com/jamiaopen/article/6/3/ooad052/7223896) — the Medication Diversification Tool, i.e. Synthea medication data needing external correction
- [Leveraging generative AI to enhance Synthea model development](https://academic.oup.com/jamiaopen/article/9/1/ooaf123/8415656) — where Synthea itself is heading
- [tietai-synthea / PySynthea](https://github.com/TIET-AI/tietai-synthea) — the competitor that closed the install-weight gap

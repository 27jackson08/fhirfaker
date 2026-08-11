# Build Document: Synthetic FHIR Data Generator

**Working name:** TBD — see Section 15 (two prior candidates are legally unusable)
**Author:** Jackson
**Status:** Draft v2
**Last updated:** August 11, 2026

> **What changed from v1.** Every factual claim in v1 was checked against primary sources. Three
> things broke: (1) the `fhir.resources` dependency cannot deliver FHIR R4 4.0.1 anymore, (2) the
> central "clinically coherent" claim was asserted rather than evidenced — and the validation bar
> v1 set was *below* what Synthea already ships, (3) two of the four naming candidates violate
> HL7's trademark policy. The RxNorm licensing claim was also oversimplified in a way that creates
> real legal exposure. All are corrected below. Sources are listed in Section 17.

---

## 1. Problem Statement

Developers building digital health applications need realistic, structurally valid, non-PII FHIR data to test against — for local development, CI pipelines, demos, and integration testing. The existing free option (Synthea) solves this at the population-simulation scale but is heavy to adopt for the common case: a developer who wants a handful of clinically coherent FHIR resources, fast, embedded in their own code or scripts.

This is not a claim that FHIR test data is unsolved. It's a claim that the *lightweight, embeddable, developer-ergonomic* segment of that problem is underserved.

---

## 2. Honest Competitive Landscape

Do not skip this section when pitching or writing the README. Every reviewer who knows this space will ask "why not Synthea," and the answer needs to be specific, not aspirational.

| Tool | What it does well | Where it leaves a gap |
|---|---|---|
| **Synthea** (MITRE, 3.3k stars) | Full birth-to-death population simulation, 100+ disease modules, C-CDA + FHIR + CSV + bulk ndjson output, a decade of development, peer-reviewed. **Ships US Core-conformant output** (`--exporter.fhir.use_us_core_ig`, US Core 3.1.1–6.1.0) | **Requires Java JDK 17+** (slow cold start, heavyweight for CI), batch-oriented (generates a population to a folder, not a function call returning one bundle), steep config surface for a developer who just wants "give me 5 diabetic patients with lab panels." No determinism contract for test fixtures |
| **fhir.resources** (PyPI, 8.3.0) | Correct, spec-generated pydantic v2 models for every FHIR resource type | Not a generator — it's the type layer. No data, no realism, no bundle assembly logic. **Dropped R4 4.0.1 at v7.0.0** — see Section 4 |
| **fhircraft** (PyPI, new as of April 2026) | Transforms FHIR specs into type-safe pydantic models | Same category as `fhir.resources` — a type layer, not a generator. Adjacent enough to monitor; if it grows a generation layer, the competitive picture changes |
| **fhir_kindling** | FHIR server CRUD client with genuine synthetic generation support, pandas integration | Generation is real but secondary to the server-interaction purpose; not built around clinical coherence |
| **FHIR-PYrate** | Querying/flattening FHIR server data into DataFrames | Solves the opposite problem (real data → tabular), not generation |

**The actual gap:** nothing in this space is `pip install X`, import, and get a clinically coherent FHIR Bundle back as a Python object in under 10 lines, with no JVM, no config file, no output folder to manage.

That is a real, narrow, defensible niche. It is not "better than Synthea" — it is "the thing you reach for when Synthea is overkill."

> **Honesty caveat on the gap claim.** This survived a deliberate search but is a negative claim and
> cannot be proven. Re-run a prior-art sweep (PyPI, GitHub topics, awesome-lists) immediately before
> launch, and keep the README's wording in its narrow form. If something closer turns up, say so in
> the README rather than letting a commenter find it first.

---

## 3. What Makes It Defensible

**v1's framing was wrong in an important way.** It listed three co-equal differentiators: coherence, library-first ergonomics, and light install. But ergonomics and install weight are **copyable in a weekend** by anyone who decides to. They are advantages, not a moat. And "structurally valid FHIR" is not a differentiator at all when the incumbent already ships US Core-conformant output.

Restructured into three layers, weakest to strongest:

### Layer 1 — Conformance (table stakes, must be flawless)

Output is US Core 6.1.0-conformant FHIR R4 4.0.1, **proven by the official HL7 validator on every release**, with the conformance matrix published in the README.

Anyone can *claim* valid FHIR. Almost nobody publishes per-release machine-checked proof. This does not beat Synthea — it means we are not embarrassed next to it.

### Layer 2 — Verified fidelity (the actual moat)

Generated distributions **provably reproduce published clinical relationships**, re-checked in CI on every commit, published as a fidelity report.

This is the one thing here that requires domain expertise both to build *and* to copy. It converts the central claim from marketing into evidence. See Section 8.

### Layer 3 — Determinism contract (the lock-in)

`seed=42` produces byte-identical output within a major version, enforced by golden-file tests and a documented stability policy.

Once a user's CI depends on your fixtures, switching cost is real. Synthea does not offer this. See Section 9.

### What this project is explicitly not

Not a full population health simulator. Not a replacement for Synthea's disease-module depth. Not a terminology-server replacement. Say this directly in the README. Scoping honesty is what makes the "defensible" claim survive scrutiny instead of collapsing under the first comment that says "cool, but why not just use Synthea."

---

## 4. Foundational Decision: FHIR Version and the Model Layer

**This is the section that changed most from v1, and it has to be settled before any code is written.**

v1 planned to build on `fhir.resources` and target FHIR R4. That combination is no longer available:

- `fhir.resources` **≥7.0.0 removed FHIR R4 (4.0.1)**. Only R4B (4.3.0), R5, and STU3 remain.
- Pinning `fhir.resources<7` gets R4 back but **forces pydantic v1**. For a library meant to be embedded in other people's applications, forcing pydantic v1 in 2026 makes it uninstallable alongside most modern Python stacks. That is disqualifying for a library-first product.
- R4B is not a substitute. It has near-zero production deployment, and **US Core targets R4 4.0.1**, not R4B. Epic, Cerner, and essentially every US production FHIR API are 4.0.1.

**Decision: target R4 4.0.1 and own the model layer.**

Generate pydantic v2 models for the in-scope resources from the official R4 4.0.1 StructureDefinitions. No `fhir.resources` dependency, therefore no version conflict in the user's application, and US Core applies cleanly.

**What makes this affordable:** we need to *emit* FHIR, not parse arbitrary FHIR. **Write-side models only.** For ~8 resource types plus shared datatypes (`HumanName`, `Identifier`, `CodeableConcept`, `Coding`, `Reference`, `Period`, `Quantity`, `Dosage`), that is low thousands of generated lines — a tractable codegen step, not a rewrite of `fhir.resources`.

R4 4.0.1 is a frozen spec, so the generated models are not a moving maintenance target.

---

## 5. Scope (v1)

### In scope
- **Resource types:** Patient, Encounter, Condition, Observation (vitals + labs), MedicationRequest, DiagnosticReport, AllergyIntolerance
- **FHIR version:** R4 4.0.1, US Core 6.1.0 profiles
- **Bundle types:** `transaction` bundles with proper `urn:uuid:` internal references
- **Terminology:** LOINC (labs/vitals), RxNorm (medications), ICD-10-CM (conditions) — see Section 6 for the licensing constraints that actually apply
- **Correlation engine:** config-driven clinical profiles (type 2 diabetes, hypertension, CKD, healthy baseline) that jointly determine linked observation values, conditions, and medications
- **Safety by construction:** see Section 7
- **Output:** in-memory Bundle objects (primary), plus optional JSON file export
- **Validation:** HL7 validator against US Core in CI, gating releases
- **Fidelity report:** statistical evidence of clinical coherence, regenerated per release

### Explicitly out of scope for v1
- Full disease-progression lifecycle simulation (Synthea's core strength — don't compete here)
- SNOMED CT codes (licensing complexity — see Section 6)
- Non-US terminology/locale variants
- C-CDA or any non-FHIR output format
- A hosted API or SaaS layer
- Parsing/validating arbitrary externally-supplied FHIR (write-side only)

---

## 6. Terminology Strategy (read this before writing any code)

This is the section people skip and then get a licensing problem six months in. **v1 got RxNorm wrong.**

### LOINC — safe, with concrete obligations
Free to use and redistribute. The license explicitly permits deleting content you don't need, which is what a curated subset is. Obligations that actually bind:
- Ship the LOINC copyright notice and attribution
- Do not modify code meanings
- Do not present the subset as a new vocabulary standard (the license specifically prohibits using LOINC content to create another vocabulary standard)
- Prefer codes with an empty `EXTERNAL_COPYRIGHT_NOTICE` field — some LOINC codes carry third-party attribution obligations (survey instruments, etc.). Curating around those keeps the obligations simple.

### RxNorm — **v1's "public domain, safe" was an oversimplification**
RXCUIs and NLM-authored normalized names are public domain. But the **full RxNorm release bundles proprietary source vocabularies** under UMLS Source Restriction Levels, and the UMLS Metathesaurus agreement restricts redistributing Metathesaurus subsets.

→ **Draw only from RxNorm Current Prescribable Content** (the explicitly open subset).
→ Store only RXCUI + RxNorm normalized name.
→ **Never** carry strings or codes originating from proprietary sources (Multum, Gold Standard, Micromedex).

This is the one place in the project where getting it wrong is a legal problem rather than a quality problem.

### ICD-10-CM — safe
Public domain in the US (CMS/NCHS). Note the distinction: WHO's base ICD-10 is copyrighted; the US *Clinical Modification* is the safe artifact. Use ICD-10-CM specifically.

### SNOMED CT — stay out, as v1 correctly concluded
Requires an affiliate license outside member countries; sub-licensees are explicitly barred from redistributing or modifying content or derivatives. **Do not embed SNOMED codes in v1.** If added later, gate it behind a user-supplied license or a local terminology server rather than shipping codes in the repo.

> **Open tension to resolve empirically.** US Core's Condition profiles bind to a value set that
> includes ICD-10-CM, so US Core conformance *should* be reachable without SNOMED — but SNOMED is
> preferred in practice for problem lists. Do not assert this either way in the README. The
> validator settles it in Phase 0, which is one more reason to phase validation first (Section 12).

**Curation scale:** roughly 30–50 LOINC codes, 20–30 RxNorm drugs, 15–20 ICD-10-CM codes. Full coverage is a maintenance burden with no v1 payoff. Attach per-code provenance and license metadata in the terminology tables so any emitted code traces back to a licensed source.

---

## 7. Architecture

```
pkg/
├── spec/
│   ├── structuredefinitions/   # vendored official R4 4.0.1 SDs, in-scope resources only
│   └── codegen.py              # SD -> pydantic v2 model generation
├── models/                     # GENERATED, checked in, write-side only
├── core/
│   ├── bundle.py               # transaction assembly, urn:uuid reference wiring
│   ├── ids.py                  # UUIDv5 from (seed, role, index) — NOT uuid4
│   └── safety.py               # HTEST tagging, non-assignable identifiers, fake names
├── profiles/
│   ├── base.py                 # ClinicalProfile ABC + its distributional contract
│   └── type2_diabetes.py | hypertension.py | ckd.py | healthy.py
├── correlation/
│   ├── engine.py               # Gaussian copula joint sampling
│   ├── relations.py            # ADAG, CKD-EPI 2021 — named, cited, unit-tested
│   └── distributions.py        # age/sex-stratified marginals
├── terminology/                # curated subsets + per-code provenance/license metadata
├── conformance/
│   ├── validator.py            # HL7 java validator harness (dev/CI only)
│   └── uscore.py               # profile assertion helpers
├── fidelity/report.py          # regenerates the published fidelity report
└── cli.py
```

**Design principle:** the CLI is a thin shell around the library. The library is the product; the CLI exists for people who want a quick file without writing Python.

### Safety by construction (`core/safety.py`) — new in v2

Absent from v1, cheap to implement, and a strong signal of domain competence to anyone evaluating this seriously:

- **Every generated resource carries `meta.security` = `HTEST`** from `http://terminology.hl7.org/CodeSystem/v3-ActReason` — the FHIR-defined security label for test health data. This is what stops synthetic records from silently contaminating a real system, and it is the kind of detail that tells a FHIR-literate reviewer the author knows the spec.
- **Identifiers drawn from ranges never issued in reality** (e.g. SSN area numbers 900–999, which SSA has never assigned) under an obviously-synthetic identifier system URL.
- **Names from a clearly-fictional pool.**

### Core API shape

```python
from pkg import generate_patient, ClinicalProfile

bundle = generate_patient(
    profile=ClinicalProfile.TYPE2_DIABETES,
    age_range=(45, 65),
    sex="F",
    seed=42,          # deterministic — see Section 9
)

bundle.to_json()
bundle.entry
```

```bash
pkg generate --profile type2_diabetes --count 20 --seed 42 --out ./fixtures/
```

---

## 8. Clinical Coherence (the actual differentiator, detailed)

Each `ClinicalProfile` defines:
1. Conditions it can attach, with prevalence-weighted onset ages
2. A **joint** distribution over associated Observations
3. Medications with realistic prescribing linkage
4. Cross-field constraints

### The engine has two distinct mechanisms — v1 conflated them

**Stochastic block — Gaussian copula.** Specify each analyte's marginal distribution independently (this is where reference-interval domain knowledge lives), plus a correlation matrix between them, then sample jointly. This scales to N correlated analytes without writing N² ad-hoc if-then rules, and it is principled rather than improvised.

**Deterministic block — computed identities.** Derived values are *computed*, not sampled. Sample creatinine, then **compute** eGFR via CKD-EPI 2021:

```
eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.200 × 0.9938^age × 1.012 [if female]
κ = 0.7 (female) / 0.9 (male)
α = -0.302 (female) / -0.241 (male)
```

v1 said eGFR and creatinine are "sampled consistent with" each other. Sampling both invites internal contradiction; computing one from the other makes contradiction structurally impossible.

### The detail that separates this from a toy

The ADAG relationship between HbA1c and average glucose is:

```
eAG (mg/dL) = 28.7 × HbA1c − 46.7     with R² = 0.84
```

**That R² is the whole point.** A naive implementation derives glucose deterministically from HbA1c, producing R² = 1.0 — a perfectly straight line that is obviously artificial to anyone who plots it. The correlation engine must reproduce the **residual scatter**, not just the trend.

CI asserts slope, intercept, **and R²** within tolerance. That single assertion is the difference between "we correlate fields" and demonstrable domain competence.

### Example: `type2_diabetes`
- HbA1c sampled from a distribution consistent with "diagnosed, moderately controlled" (~7.0–9.5%)
- Fasting glucose sampled **jointly** with HbA1c via the copula, calibrated so the generated population reproduces the ADAG regression *including its scatter*
- ~70% probability of attached hypertension comorbidity (realistic comorbidity rate, not decoration)
- MedicationRequest for metformin at a plausible dose, ~15% probability of a second agent if HbA1c > 8.5%

This is where lab/reference-interval background is directly transferable — thinking in population-stratified distributions and clinical plausibility *is* the hard part. The FHIR wrapping around it is comparatively mechanical.

---

## 9. Determinism Contract

`seed=42` must produce **byte-identical** JSON within a major version. This is a product feature, not an implementation detail — it is what lets users build golden-file test fixtures on this library.

- Thread a seeded `numpy.random.Generator` explicitly. **Never** touch global random state.
- IDs via UUIDv5 derived from `(seed, resource_role, index)`. A single `uuid4()` anywhere breaks the contract.
- Stable key ordering on serialization.
- **The trap:** any `datetime.now()` call destroys determinism. Inject a reference date; derive all clinical dates from it.
- Enforce with golden-file snapshot tests.
- **Publish the stability policy:** seeded output changes only on a major version bump.

---

## 10. Validation Strategy

**v1 treated the HL7 validator as a stretch goal and "the first thing to cut." That was backwards.**

"Passes pydantic model validation" means the JSON has the right field types. It does not mean the resource conforms to the spec's invariants, terminology bindings, or profile cardinality rules. To a FHIR-literate reviewer it is close to meaningless — and Synthea already ships US Core-conformant output, so shipping merely-structurally-valid data puts this project *below* the incumbent's bar.

Two tiers, both in v1:

1. **Structural (fast, per-PR):** every resource passes pydantic validation at construction. Catches malformed resources at generation time.
2. **Conformance (authoritative, gates releases):** output runs through the official HL7 Java validator against US Core 6.1.0. The resulting **conformance matrix is published in the README** and regenerated per release.

> **Narrative risk to manage.** The HL7 validator needs a JVM, and "no JVM" is part of the pitch.
> Resolution: the JVM is a **dev/CI dependency only, never a runtime or install dependency**. State
> this explicitly in the README, or the positioning contradicts itself and a reader will notice.

---

## 11. Testing

**Per-PR (fast):**
- Unit tests per resource generator — structure, correct reference wiring
- Property-based tests (Hypothesis) on invariants: every `urn:uuid:` reference resolves within its bundle; no dangling references; every resource carries the `HTEST` label; every emitted code exists in the curated terminology tables
- Golden-file snapshot tests for seeded determinism
- HL7 validator on a **small sample only** — JVM cold start is slow, keep the PR loop tight

**Nightly (full):**
- HL7 validator across the full profile × resource-type matrix vs US Core 6.1.0
- Fidelity report regenerated at N=10,000 patients per profile, asserting:
  - OLS of generated glucose on generated HbA1c → slope ≈ 28.7, intercept ≈ −46.7, **R² ≈ 0.84** (all three)
  - eGFR reproduces CKD-EPI 2021 exactly from generated creatinine/age/sex
  - CKD stage-3 profile yields eGFR in 30–59
  - Comorbidity rates match configured prevalence (~70% HTN in T2DM) within a binomial CI
  - Vitals marginals fall inside published population reference bands by age/sex

> **Flakiness warning.** Statistical assertions must run on fixed seeds with tolerances that are
> meaningful but not knife-edge. A fidelity suite that flakes gets ignored, and then it is worse
> than not having one.

---

## 12. Phased Roadmap

**v1 put validation at Phase 4. Invert it.** Standing up the conformance harness first means conformance bugs surface *while* each resource is being written, instead of after everything is built on a wrong foundation.

| Phase | Content | Exit criterion |
|---|---|---|
| **0. Walking skeleton** | Vendor R4 SDs, codegen, validator harness | One `Patient` passes the HL7 validator against US Core 6.1.0 |
| **1. Core resources** | Encounter, Condition, Observation, MedicationRequest, DiagnosticReport, AllergyIntolerance; bundle assembly + reference wiring | Each resource type validator-green as it lands |
| **2. Terminology** | Curated LOINC/RxNorm/ICD-10-CM subsets with provenance metadata | Every emitted code traces to a licensed, recorded source |
| **3. Correlation engine** | Copula sampling + `relations.py`; 4 profiles | **The differentiator — allocate the most time here** |
| **4. Fidelity + determinism** | Fidelity report generation, golden snapshots | Report published; drift fails CI |
| **5. Ship** | CLI, packaging, docs, README positioning, name decision + rename pass | PyPI 0.1.0 |

This is a multi-week project at a realistic pace alongside everything else currently open. It is not a weekend project if Phase 3 is done properly rather than skipped.

---

## 13. Packaging & Distribution

- Pure Python at runtime, `pyproject.toml`, publish to PyPI
- Runtime dependencies kept minimal — numpy/scipy for the copula, pydantic v2. **No JVM at runtime.**
- Semantic versioning from day one (start at 0.1.0 — this is a young project)
- README leads with the honest positioning from Section 3, plus the conformance matrix and fidelity report as proof
- MIT or Apache 2.0 (Apache 2.0 if you want defensive patent language; either is fine for this scope)

---

## 14. Risks

- **Scope creep toward "Synthea but worse."** The moment this tries to simulate full patient lifecycles, it competes on Synthea's terms and loses. Stay in the "quick, coherent, embeddable" lane.
- **US Core Condition binding vs. the no-SNOMED decision.** May constrain Condition conformance. Settled empirically by the validator in Phase 0 — do not assert either way before then.
- **JVM in CI undercuts the "no JVM" pitch.** Mitigated by stating clearly that it is dev/CI-only. Left unstated, it reads as a contradiction.
- **Codegen maintenance.** Owning the models means owning spec updates. Mitigated by narrow scope (8 resources, write-side only) and by R4 4.0.1 being frozen.
- **Statistical test flakiness.** See Section 11.
- **Terminology maintenance.** Curated subsets go stale. Plan periodic review, not a one-time load.
- **Correlation engine complexity underestimated.** This is the hard, valuable part. If time runs short, fewer well-done profiles beat more shallow ones.
- **Trademark exposure.** See Section 15. Settle before first publish, not after traction.
- **Distribution, not just quality, drives adoption.** Even a genuinely differentiated tool needs a launch — a blog post, a Show HN, an awesome-list inclusion. Building it well is necessary but not sufficient.

---

## 15. Naming — Trademark Constraint

**HL7's FHIR trademark policy rules out two of v1's four candidates.** The policy forbids abbreviating the mark or combining it with other words — HL7's own counter-examples are "not FHIRFITE or FHIRFLY" — and prohibits use in product names or domains without express written permission.

| Candidate | Status |
|---|---|
| `fhirforge` | ❌ Mark combined with another word |
| `synthfhir` | ❌ Mark combined with another word |
| `carebundle` | ✅ Clean |
| `mockcare` | ✅ Clean |

Using "FHIR®" **descriptively** in the README, PyPI description, and prose is fine and encouraged — the constraint is only on the product name and domain. If a FHIR-containing name is genuinely wanted, HL7 does grant written permission to open-source projects, but that adds an approval dependency and a rename risk if refused after traction.

If the mark is used descriptively, include: *"FHIR® is the registered trademark of HL7 and is used with the permission of HL7."*

**Decision deferred.** The build uses placeholder `pkg` throughout; a rename pass happens before first PyPI publish.

---

## 16. Open Questions

- ~~How many clinical profiles for v1~~ → **Resolved:** 4 (diabetes, hypertension, CKD, healthy baseline). More dilutes correlation-engine quality.
- ~~Whether HL7 validator integration is in scope for v1~~ → **Resolved:** yes, and it gates releases. See Section 10.
- ~~FHIR version and model layer~~ → **Resolved:** R4 4.0.1, self-owned pydantic v2 models. See Section 4.
- **Still open:** MIT vs Apache 2.0.
- **Still open:** final name (Section 15).
- **Still open, resolved empirically in Phase 0:** whether US Core Condition conformance is achievable with ICD-10-CM alone.

---

## 17. Sources

- [fhir.resources on PyPI](https://pypi.org/project/fhir.resources/) — 8.3.0; R4 4.0.1 dropped at 7.0.0
- [Synthea](https://github.com/synthetichealth/synthea) — 3.3k stars, Java 17+
- [Synthea US Core discussion #1433](https://github.com/synthetichealth/synthea/discussions/1433) — `use_us_core_ig`
- [US Core Implementation Guide STU 6.1.0](https://hl7.org/fhir/us/core/)
- [FHIR R4 security labels](http://hl7.org/fhir/R4/security-labels.html) — HTEST
- [CKD-EPI Creatinine Equation 2021, National Kidney Foundation](https://www.kidney.org/ckd-epi-creatinine-equation-2021)
- [ADAG study, *Diabetes Care* 31(8):1473](https://diabetesjournals.org/care/article/31/8/1473/28589/Translating-the-A1C-Assay-Into-Estimated-Average) — R² = 0.84
- [LOINC Copyright Notice and License](https://loinc.org/kb/license/)
- [RxNorm Terms of Service](https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html)
- [UMLS Metathesaurus License Agreement](https://uts.nlm.nih.gov/uts/assets/LicenseAgreement.pdf)
- [FHIR Trademark Policy (PDF)](https://www.hl7.org/documentcenter/public/legal/FHIR_Trademark_Policy.pdf)

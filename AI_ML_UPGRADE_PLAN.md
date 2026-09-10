# AI/ML Upgrade Plan

Tracking doc for the next round of ML/AI work on top of the frozen
`research-v1.0-experimental` baseline and the post-freeze fixes already
shipped (dictionary cleanup, targeted trace intervention, `normalize_text`
bug fix, Arabic OCR, match explanations, UNKNOWN reason codes — see
README's "Post-Freeze Maintenance and Extensions").

Source: the 63-item idea list you put together, triaged against what
Phases 1/2/5 of `ML_EXTENSION_PLAN.md` already tested and the trace
diagnostic already found. Not pushed/committed — planning doc only, per
your usual pattern for these.

## Ground rules (carried over, unchanged)

- The rule-based matcher stays the deployed decision-maker. Anything ML
  produces is either (a) a candidate a human reviews before it becomes a
  dictionary term, exactly like Phase 3, or (b) a confidence/explanation
  signal *alongside* the deterministic AVOID/CAUTION/SAFE call — never a
  replacement for it.
- Every phase gets its own before/after benchmark on the 963-product
  leak-free dev set, its own versioned output directory, and an honest
  go/no-go against the existing baseline. If it doesn't beat baseline, it
  gets documented as a negative result and not deployed — same standard
  Phases 1, 2, and 5 were held to.
- The 300-product held-out set stays untouched until final evaluation of
  whatever ships.
- No git commits during the build phase of any of this without you asking.

---

## Why this triage isn't a straight yes to all 63

Three things already happened in this project that change how I'd weight
your list, and I want to be upfront about them rather than re-pitch ideas
that already lost:

1. **Semantic/embedding matching has been tried twice as a matching
   mechanism and lost both times.** Phase 1 (weak-supervised trace/declared
   classifier) didn't beat the rule splitter. Phase 2 (multilingual
   embedding candidate generation as a matcher) didn't beat the
   deterministic matcher either, and had two concrete failure modes: short
   single-word phrases and structural false-positives (semantically
   unrelated ingredients with similar grammar — different seeds — getting
   grouped together). Sections **A** and **B** of your list (multilingual
   embeddings, semantic classification, hybrid rule+ML fusion) are largely
   a third attempt at the same thing. I'm not saying don't do it — but it
   needs a genuinely different angle from Phase 2, not a re-run, or we'll
   likely get the same negative result a third time. See Phase 6 below for
   the angle I think actually has a shot.

2. **OCR confidence as a standalone signal is weak.** Phase 5's
   pre-registered test found no significant correlation between OCR
   confidence and error rate (r = -0.227, p = 0.165); only an exploratory,
   non-pre-registered Spearman test was significant. Items **C12**, **F24**
   as "OCR confidence alone gates trust" repeat something already tested
   and found wanting. It's more promising as *one of several* features into
   a multi-signal model (your item **15**), not as a standalone gate.

3. **The trace-recall diagnostic already explained 93.7% of the problem
   your Section H is aimed at**, and it's a data problem (missing source
   text), not a modeling problem. A trace-context classifier (items **35–39**)
   is capped by the same ceiling Phase 1's classifier hit for the same
   reason. You already flagged this yourself — agreed, Section H stays
   low priority, exactly as you said, until there's a different source of
   text to work with (e.g. OCR'ing a separate allergen-disclosure panel).

None of that means "don't build an AI/ML layer" — it means the highest-ROI
version of it is *not* "replace the matcher with embeddings again." It's
the areas below where there's either already-validated precedent (Phase 3)
or genuinely new ground nothing has tried yet (LLM explanation layer,
confidence-as-a-feature-model, ontology tooling).

---

## Recommended phased roadmap

### Phase 6 — Ontology/dictionary intelligence tooling
**Maps to: G30–G34. Priority: highest. Risk: lowest.**

This is the one area with a *proven* win already (Phase 3: embeddings for
candidate generation + human approval, applied, validated, currently
live). Two very concrete, already-manually-solved problems this session
are exactly what this phase should automate:

- **Morphological variant detector (G32):** the `Schalenfrüchte` /
  `Schalenfrüchten` and `Erdnuss` / `Erdnüssen` gaps found in the trace
  intervention were exactly this — a base term present, an inflected form
  missing. A small language-aware stemmer/lemmatizer pass (or even a
  cheap edit-distance/morphology rule set per language) run against the
  existing dictionary vs. the dataset's actual vocabulary would surface
  these systematically instead of one-at-a-time via diagnostic work.
- **Ontology consistency checker (G34):** automate what the `mantelrouge`
  cleanup did manually — flag zero-occurrence terms, terms matching no
  recognizable word in any supported language, near-duplicate entries,
  and terms whose only occurrences are inside negated contexts. Run as a
  standing script (`scripts/audit_dictionary.py`), not a one-time script.
- **Cross-language gap finder (G33):** for each allergen, check which
  supported languages have zero dictionary coverage and flag them (e.g.
  egg had zero Spanish terms until this session — this class of gap
  should be machine-findable, not luck).
- **AI synonym discovery (G30/31):** already partially built (Phase 2/3
  embedding pipeline) — formalize it into a repeatable
  propose→human-review→apply loop instead of a one-off script per phase.

**Deliverable:** `scripts/audit_dictionary.py` + a versioned
`data/research/ml/ontology_audit_v1/` report. **Evaluation:** count of
real gaps found vs. false positives on manual review; no matcher change
required to ship this — it's a maintenance tool, not a runtime component.

### Phase 7 — Explainability surface (mostly done, finish the UI)
**Maps to: E19–E23, K50–K55. Priority: high. Risk: very low.**

Most of the *data* already exists (`matches`, `trace_matches`,
`explanations`, `reason_code`) — this phase is presentation, not new ML:

- **Confidence visualization (K52):** once Phase 8 produces an actual
  confidence number (see below), render it as a bar/percentage. Don't
  fabricate a number before Phase 8 exists — a fake-precision "96%" with
  no model behind it would be worse than no number.
- **Match-type explanation (E21):** already have `match_type: "direct"` in
  the matcher output; surface it (and add `"semantic"` once Phase 6's
  candidate flow feeds anything in) as a small badge per match.
- **"Why UNKNOWN?" intelligence (K54):** already shipped the reason codes;
  this is just writing the friendlier copy per code in the UI, which is
  a content task, not an ML task.
- **AI-assisted scan summary (K53) / natural-language summary (J45):**
  this is where the optional LLM layer (Phase 9) actually plugs in — see
  below, don't build a fake one with string templates and call it AI.

**Deliverable:** UI-only changes to `ResultsPage.jsx`, no backend model
work. Ships independently of every other phase.

### Phase 8 — Multi-signal evidence-confidence model
**Maps to: C10, C13–14, D15–18, F24. Priority: medium-high. Risk: medium.**

This is where I'd spend the "confidence" ambition, and it's different
from what already failed: instead of using OCR confidence *alone*
(already shown weak) or embeddings *alone* (already shown to lose as a
matcher), train a small calibrated model (logistic regression or gradient
boosting over ~8 features, not a neural net) whose only job is: **given a
match the deterministic matcher already made, how much should a user
trust it?**

Candidate features (your item 15's list, refined):
`exact_dictionary_match` (bool), `match_type`, `OCR_confidence`,
`ingredient_section_found`, `trace_vs_declared`, `negation_nearby`,
`language`, `ingredient_text_length`, `matched_term_length`.

This is explicitly **not** a second detector — it never adds or removes
an allergen the rule engine didn't already find. It only scores
*confidence in a decision already made*, which sidesteps Phase 1/2's
actual failure mode (using ML to decide *what* is an allergen).

**Evaluation (item 59, confidence calibration item 14):** hold out
labeled cases, bucket by predicted confidence, check whether predicted-90%
buckets are actually ~90% correct (calibration curve / Brier score). Ship
only if calibration is good — if the model is confidently wrong, that's
worse than no confidence score at all, and this phase should say so
plainly if that's what happens.

**Deliverable:** `data/research/ml/confidence_model_v1/`, an optional
`confidence` field in `matches`/`trace_matches`, off by default in the UI
until validated.

### Phase 9 — Evidence-grounded LLM explanation/Q&A layer
**Maps to: J44–J49. Priority: medium. Risk: medium (cost + dependency, not
correctness — see constraint below).**

The one part of your list that's genuinely new territory, not a repeat of
something already tried. The hard constraint that makes this safe:

> **The LLM receives the already-computed structured evidence (matches,
> explanations, risk, confidence) as its only input and is prompted to
> explain it in natural language — it is never asked to detect an
> allergen, decide a risk level, or read raw ingredient text itself.**

This turns a real hallucination risk ("LLM invents an allergen") into a
much smaller one ("LLM's phrasing of already-verified evidence is
awkward"), which is an acceptable risk for a decision-support tool that
already tells users to verify labels themselves.

Concrete scope: natural-language scan summary (J45), ingredient Q&A
grounded in scan evidence only (J46, J48), multilingual explanation
generation (J49) reusing whatever language the user already selected.

**Open questions for you before I'd build this:** which provider/API (cost
+ your existing Claude access vs. something else), and whether it's an
always-on feature or an opt-in "Explain with AI" button (I'd lean opt-in —
keeps the deterministic core the default experience and makes the LLM
layer clearly additive, matching your own framing that "the deterministic
safety layer stays in control").

### Phase 10 — Intelligent OCR preprocessing/region detection
**Maps to: F25–F28. Priority: lower. Risk: medium-high, real accuracy
upside unproven yet.**

Ingredient-panel region detection (F26/27) is a real vision task (object
detection or a classifier over image crops), not a small addition — it's
the most expensive item on the list to do properly. I'd sequence this
*after* Phase 8's confidence model exists, because the right first
question is "how often does bad ingredient-region localization vs. bad
OCR vs. bad heading-matching actually cause failures" — the existing OCR
benchmark error analysis already has the OCR-vs-matcher split; extending
it to isolate region-detection failures specifically would tell us if
this phase is worth its cost before starting it.

**Deliverable if greenlit:** a small classifier (not full object
detection) over EasyOCR's already-detected text regions, trained on the
existing 39-image OCR benchmark plus more labeled crops — likely needs a
larger labeled image set than currently exists, which is itself a
prerequisite task.

### Not currently recommended (with reasons, not silently dropped)

- **Section H (trace-context ML classifier, items 35–39):** capped by the
  93.7% missing-source-text ceiling found in this session's diagnostic.
  Revisit only if a new text source (e.g. a separate disclosure-panel OCR
  target) is added — you already called this correctly.
- **A/B as originally scoped (embeddings as a parallel matcher, hybrid
  fusion voting between rule and neural detectors):** already tried twice
  (Phases 1–2) and lost. Phase 8 above is the reframed version that has a
  actual shot — pure confidence scoring, not re-detection. If you want the
  literal hybrid-fusion architecture from your diagram tried a third time
  as originally scoped, I'd want that to be an explicit, deliberate
  decision from you given the track record, not a default inclusion.
- **Severity-aware personalization (item 41):** blocked on product
  decision (do we collect user severity data at all, and how), not an ML
  problem — flagging as a product question, not scoping it as ML work.

---

## My actual top picks, given all of the above

1. Phase 6 (ontology tooling) — proven category, cheap, real gaps to find.
2. Phase 7 (finish the explainability UI) — mostly done, ships fast.
3. Phase 8 (multi-signal confidence model) — the honest version of
   "confidence," scoped to avoid Phase 1/2's actual failure mode.
4. Phase 9 (LLM explanation layer, opt-in) — genuinely new, real user
   value, contained risk if scoped as evidence-grounded-only.

Phase 10 I'd defer until the error-analysis groundwork says it's worth
the cost. The "not recommended" section I'd leave exactly as documented
here rather than build — but it's your call, and I laid out why so you
can override any of it.

## Decisions (locked in)

- **Order:** 6 → 7 → 8 → 9, as recommended. Phase 10 gated behind its own
  cheap first step (below) rather than committed to outright.
- **Phase 9 provider: Groq.** OpenAI-compatible API, fast inference, usable
  free tier. Needs a `GROQ_API_KEY` (env var, never committed) before
  Phase 9 can be wired up — will ask for it when that phase starts.
- **Phase 9 UX: always shown, not opt-in.** Every scan gets an
  LLM-generated natural-language summary alongside the structured result,
  not behind a button. Noting the tradeoff since this overrides my
  recommendation: every scan now costs one LLM call (latency + Groq usage
  against the free-tier limit), and if the summary generation fails or is
  slow, the UI needs a defined fallback (show the structured result
  immediately, summary loads in after / degrades gracefully) rather than
  blocking the whole result on it. Will design for that explicitly.
- **Phase 10: do the cheap error-analysis extension first.** Not a full
  region-detection build yet — just extends the existing OCR benchmark
  error analysis to say whether region-detection failures are actually a
  meaningful chunk of the error budget before committing to building a
  classifier for it.

## Status

- [x] **Phase 6 — ontology audit tooling.** `scripts/audit_dictionary.py`
      built and run. Report: `data/research/ml/ontology_audit_v1/dictionary_audit_report.json`.
      Findings: 63 zero-occurrence terms (caveat: this alone is a weak
      signal — see the report's note; most are legitimate words simply
      absent from this dataset, not anomalies like `mantelrouge`), 30
      exact duplicate terms (mostly accent-variant pairs that collapse
      under normalization, plus one literal JSON duplicate —
      `weizenmehl`), 66 near-duplicate pairs, 0 cross-allergen conflicts,
      26 morphological variant candidates (e.g. `lait` → `laitière`/
      `laitiers`, real French adjective forms not yet covered), 9
      language coverage gaps (e.g. Italian `grano`/`farina` for
      wheat_gluten, generic English `dairy` for milk). Nothing was
      applied — read-only, exactly as scoped. `noix` correctly reappears
      as a flagged candidate despite the earlier decision to exclude it
      (coconut collision) — the tool doesn't know that context, which is
      the intended behavior: it surfaces, a human still decides.
- [x] **Phase 7 — explainability UI finish.** Added per-match `match_type`
      badges ("Exact match") next to each explanation sentence, and
      reason-code-specific actionable tips on the UNKNOWN card (e.g.
      "Try photographing the ingredient panel directly" for
      `INGREDIENT_SECTION_NOT_FOUND`). Confidence visualization
      deliberately NOT added yet — still waiting on Phase 8 to produce a
      real number rather than fabricating one. `npm run build` passes.
- [x] **Phase 8 — multi-signal confidence model. Data expanded, model trained, honest negative result — not shipped.**
      See full writeup below (data expansion + model result).
- [ ] Phase 9 — Groq-backed LLM explanation layer (always-on)
- [ ] Phase 10 — OCR error-analysis extension (region-detection ROI check)

### Phase 8 execution — data expansion + model result

**Data expansion.** Downloaded 60 new candidate images via the existing
`scripts/download_ocr_dataset.py` pipeline (seed 1337, includes Arabic
targets this time), got 48 back (12 unavailable/rate-limited), 47 unique
after removing 1 accidental overlap with the original 50. Manually
transcribed all 47 by directly viewing each image (same process as the
original 39-image benchmark) — 44 usable, 3 excluded (2 too blurry, 1
in Turkish, which isn't a supported language despite OFF tagging the
product as English). Full transcriptions and per-image notes:
`data/research/ml/ocr_expansion_v1/manual_annotations.py`.

Real findings surfaced along the way, not fabricated: two more real-world
confirmations of the "kann ... enthalten" German regex fix and the
`Schalenfrüchten` dictionary fix from earlier this session (both hit on
genuine label photos, not synthetic text); two products where OFF's
`declared_allergens` tag wrongly includes a facility-trace statement
(`3083681148619`, `3083681148640` — the same product family, both
confirmed by direct reading); a recurring pattern of OFF's trace tag
under-counting sesame specifically (5+ products where "graines de
sésame" is clearly printed in the precautionary statement but absent
from the OFF trace tag); and a real, still-open finding — Italian trace
phrasing ("può contenere tracce di", "frutta a guscio") isn't covered by
`TRACE_REGEXES` at all, which has zero Italian entries. Not fixed here —
flagging as a future candidate, same as the Phase B diagnostic process.

Ran the actual EasyOCR pipeline (not just the manual transcriptions)
against all 44 new images. Combined with the original 39: **83 images,
238 total reference allergen instances** (up from 85), saved to
`data/research/ml/ocr_expansion_v1/combined_ocr_results.csv`.

**Model result — honest negative, not shipped.** Built one training
instance per (product, allergen, section) match the OCR-text matcher
actually produced — 104 such instances (89 correct, 15 incorrect).
Trained a logistic regression confidence scorer (features: OCR
confidence, declared-vs-trace, extraction-found, text length, language)
on a 73/31 train/test split.

| Metric | Value |
|---|---:|
| Test ROC AUC | 0.678 |
| Test Brier score (model) | 0.2044 |
| Test Brier score (naive constant base-rate predictor) | 0.1321 |

**The trained model's Brier score is worse than just predicting the
training base rate (86%) for every match.** AUC 0.678 shows the features
do carry some real ranking signal (better than a coin flip), but with
only 104 instances total the model isn't calibrated well enough to beat
the simplest possible baseline, let alone ship. Per the plan's own
stated bar — "ship only if calibration is good" — **this does not go
live.** Documented as a negative result, same standing as Phases 1, 2,
and 5. Full result: `data/research/ml/confidence_model_v1/confidence_model_result.json`.

**Follow-up: tried fewer features, it got worse, not better.** Ruled out
"the model is overfitting 4+ features on 104 instances" as the fix by
testing 1-feature (OCR confidence alone: AUC 0.511, barely above random)
and 2-feature (+ declared/trace: AUC 0.456, worse than random) variants.
Neither beat the naive baseline either. This confirms the bottleneck is
genuinely sample size, not feature count — the fuller feature set was
carrying real signal that got lost when reduced, and also reconfirms
Phase 5's original finding that OCR confidence alone is a weak predictor.
Full comparison: `data/research/ml/confidence_model_v1/reduced_feature_experiments.json`.

**What this means going forward:** the 3x data expansion (85 → 238
instances) was real progress and is reusable — it's not wasted. The
model needs more data, full stop; there's no shortcut through feature
selection at this sample size. Not re-attempted further this session —
next real move would be another data-expansion round, not more modeling
on the same 104 instances.

### Phase 8 blocker — labeled data is too small to honestly train/calibrate

Checked before writing any training code, same discipline as every prior
phase: the only dataset with both OCR-derived confidence AND ground-truth
correctness is the 39-image OCR benchmark
(`data/benchmark/final_ocr_results.csv`) — **45 declared-allergen
instances and 40 trace-allergen instances total.** That's not enough to
train a model and separately hold out data to check calibration
(the plan's own success criterion: "predicted-90% buckets are actually
~90% correct") — with this few samples per confidence bucket, a
calibration curve would be noise, not evidence, and shipping "94%
confidence" numbers derived from it would be exactly the kind of
overclaiming this project has avoided everywhere else (this is the same
concern that killed the OCR-confidence gate in Phase 5).

Two honest ways to proceed, not a silent workaround:

1. **Ship a deterministic, transparent scoring heuristic instead of a
   trained model for v1** — same feature list (match_type, OCR
   confidence, section-found, declared/trace, language, term length),
   but combined with hand-set weights and labeled clearly as a heuristic,
   not a calibrated probability. Revisit as a real trained model once
   more labeled data exists.
2. **Expand the labeled set first** (more OCR-benchmark images with
   manual transcription + correctness labels), then train/calibrate
   properly. Higher effort, but is the only way to get a genuine
   confidence *probability* rather than a heuristic *score*.

Went with the plan's own stated bar ("ship only if calibration is good")
rather than force it — flagging for a decision instead of picking
silently.

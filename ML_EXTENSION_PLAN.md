# ML Extension Build Plan

Tracking doc for the hybrid ML layer approved on top of the frozen rule-based
system. Not pushed/committed — local reference only, per instruction.

Source: `ml_research_audit` artifact (research-architecture audit,
2026-09-09). Full reasoning for every decision below lives there; this file
tracks execution status only.

## Ground rules (do not violate)

- The existing rule-based matcher (`scripts/allergen_matcher.py`) is
  **frozen** and remains the baseline. Nothing in this build modifies its
  matching logic.
- The 300-product held-out set (`data/research/ground_truth.csv`,
  `heldout_*`) stays **completely untouched** — no training, no tuning,
  no threshold selection against it. It is eval-only, at the end.
- "Development data" = the 1,263-product main set only.
- Negation, context exclusions, ontology verification, personalization, and
  SAFE/CAUTION/AVOID decision logic stay deterministic. ML never writes
  directly to a risk verdict.
- Every experiment writes **new, versioned output files** — existing
  benchmark results (`matcher_summary.json`, `heldout_results.json`,
  `final_ocr_summary.json`, etc.) are never overwritten.
- No git commits/pushes during this build — that's the user's call, same as
  every prior phase this session.

## Phase 0 — Dataset reconciliation

- [x] Reconcile 1,849 vs 1,612 row-count discrepancy.
      **Resolved, false alarm.** `wc -l data/cleaned_products.csv` reports
      1,850 lines because several `ingredients_text` fields contain literal
      embedded newlines inside quoted CSV cells (valid CSV, but inflates a
      raw line count). `pandas.read_csv` — the correct parser — confirms
      **1,612 unique products, 0 duplicates, 0 null codes, 1,263 with
      non-empty `ingredients_text`**, exactly matching existing
      documentation. No data-integrity issue; no action needed.

## Phase 1 — Trace/declared classifier

- [x] **Data-leakage check (caught before any training code was written):**
      all 300 held-out product codes are a subset of the 1,612-product
      `cleaned_products.csv`. The existing frozen 1,263-product baseline
      (`matcher_summary.json`) therefore already includes all 300 held-out
      products within it (23.8% overlap) — that file is untouched and
      stays as historical reference, but it is **not** a valid apples-to-
      apples comparison set for new ML work.
      **True leak-free dev set: 963 products** (1,263 minus the 300
      held-out codes). All Phase 1 training/CV/comparison uses this
      963-product set. The rule-only baseline is *recomputed* fresh on
      this same 963-subset (new file, doesn't touch `matcher_summary.json`)
      so the "beats baseline" comparison is genuinely apples-to-apples.
- [ ] Generate weak labels from the existing rule-based splitter
      (`split_declared_and_trace_text`) over the 1,263-product dev set.
- [ ] Train/dev split *within* the 1,263 set only (300-set never touched).
- [ ] TF-IDF (word) + character n-gram features, Logistic Regression.
- [ ] Evaluate: does the classifier's trace/declared boundary agree with
      rules on the easy majority, and generalize on the rules' own
      documented error cases (`matcher_error_summary.json`)?
- [x] Save versioned output: `data/research/ml/trace_classifier_v1/`
      (`model.joblib`, `cv_sanity_check.json`, `downstream_comparison.json`)
- [x] **Result: DOES NOT beat baseline. Does not go live.**
      963-product leak-free dev set, rule-only vs. classifier-based split,
      same downstream matching code both times:
      | | Precision | Recall | F1 | Exact |
      |---|---|---|---|---|
      | Declared, rule | 0.9395 | 0.7883 | 0.8573 | 0.7902 |
      | Declared, ML   | 0.9204 | 0.7827 | 0.8460 | 0.7757 |
      | Trace, rule    | 0.9474 | 0.4016 | 0.5640 | 0.6978 |
      | Trace, ML      | 0.9476 | 0.3860 | 0.5486 | 0.6926 |

      Both metrics regressed slightly. CV sanity check against the
      classifier's own weak-label bootstrap was reasonable (F1 0.8113),
      confirming the model learned *something* coherent — it just doesn't
      exceed the rules it was bootstrapped from. Likely causes: (1) severe
      class imbalance in weak labels (1,479 declared clauses vs. 358 trace
      clauses), (2) a classifier trained by imitating the rules has no
      signal to identify cases where the rules themselves are wrong — a
      structural ceiling of pure weak supervision without any independent
      signal, (3) period/semicolon clause segmentation may fragment
      context the phrase-level regex patterns capture in one piece.
      **No further tuning attempted** — per this session's own established
      practice, results are reported as measured rather than iterated
      until they win. `allergen_matcher.py` remains completely untouched;
      the frozen rule-based system is exactly what it was.

## Phase 2 — Embedding candidate generation

- [ ] **Dependency check-in needed before this phase**: requires adding a
      multilingual sentence-embedding library (e.g. `sentence-transformers`)
      and downloading a pretrained model (network + disk, one-time). Not
      installed yet — confirming before pulling it in.
- [ ] Embed the 259-term allergen dictionary once.
- [ ] For ingredient phrases the exact/fuzzy matcher misses, retrieve
      nearest dictionary terms by cosine similarity.
- [ ] Candidates pass through **existing, unmodified** negation/exclusion
      rules before counting as a match — embeddings never decide risk
      directly.
- [ ] Evaluate recall delta vs. Phase-1-frozen baseline on the 1,263 dev
      set, at matched precision via threshold tuning.
- [x] Save versioned output: `data/research/ml/embedding_candidates_v1/`
      (`threshold_sweep.json`, `dictionary_embeddings.npy`, `dictionary_terms.json`)
- [x] **Result: DOES NOT beat baseline at any tested threshold. Does not
      go live.** Model: `paraphrase-multilingual-MiniLM-L12-v2`, zero-shot,
      never fine-tuned. 963-product leak-free dev set, threshold swept
      0.60–0.85.

      **First run** (all comma-separated phrases, including single
      words): catastrophic false-positive explosion — declared F1
      0.8573 → as low as 0.2987. Root cause diagnosed from evidence
      samples: single short words produce unreliable embeddings with
      this model ("sel"/salt vs. "eiklar"/egg-white = 0.86 similarity;
      "sel" vs. "sesam" = 0.89). Not a threshold problem — no threshold
      fixes indiscriminate short-token embeddings.

      **Second run** (restricted to multi-word phrases only — a
      principled fix, and low-cost since single-word ingredients are
      already the exact/fuzzy matcher's strong suit): improved but still
      a net regression at every threshold. Best case (threshold 0.85,
      only 328 candidates confirmed total): declared F1 0.8573 → 0.7736,
      trace F1 0.5640 → 0.5676 (a ~0.004 gain, within noise). Second
      failure mode identified from evidence: the model matches on
      *structural pattern* ("[seeds/flour/fibre] of X") rather than the
      specific substance — "graines de tournesol" (sunflower seeds)
      false-matches "semillas de sesamo" (sesame seeds) at 0.91 purely
      because both are "seeds of X." Genuine wins exist in the same data
      (e.g. "farine de froment" correctly triggering wheat_gluten via a
      dictionary-missing French synonym, "froment") but are outnumbered
      by pattern-level false positives.

      **No further tuning attempted beyond these two principled,
      diagnosis-driven fixes** — a third iteration (e.g. margin-based
      confidence between top candidates, or a larger embedding model)
      is plausible future work, not pursued now to avoid tuning until
      it wins. `allergen_matcher.py` remains untouched. The dictionary
      embedding index built here (`dictionary_embeddings.npy`) is reused
      by Phase 3, where the same signal is safe to use precisely because
      a human reviews every proposal instead of it acting autonomously.

## Phase 3 — Semi-automatic ontology expansion

- [ ] Offline pass: surface dictionary-adjacent terms from the dev-set
      ingredient vocabulary via the same embeddings.
- [ ] Produce a human-review shortlist (proposed term, matched allergen,
      similarity score, source ingredient context) — **no automatic
      additions**.
- [x] Wait for explicit approval per term before any dictionary edit.
      **Status: full review complete across all 9 allergen groups
      (2026-09-09). 9 approved / 109 rejected. Dictionary NOT yet
      modified — awaiting explicit final go-ahead.** Full decision
      record: `data/research/ml/synonym_proposals_v1/review_decisions.json`.

      Approved (9): milk ×4 (بروتينات الحليب, lactossoro em pó,
      مركزات بروتينات الحليب, حليب كامل الدسم), tree_nut ×3
      (fruit à coques, frutos de cáscara, _fruits coque_), wheat_gluten
      ×2 (пшенично брашно, Farine de froment).

      Rejected (109) — dominant patterns identified during review:
      structural "[type] of [X]" false positives (flour~flour,
      fibre~fibre, seeds~seeds) accounted for the majority; several
      short existing dictionary entries (mantelrouge, sei, crabe) act
      as generic embedding attractors pulling in unrelated candidates
      across multiple allergen groups — flagged for a separate manual
      audit, not modified based on embedding results alone.

      Other follow-ups noted, not acted on: Arabic comma (،) isn't
      handled by the phrase splitter (causes unsplit compounds);
      correctly-spelled barley-milk coverage for wheat_gluten
      considered separately if wanted.

- [x] **Applied to `data/allergen_dictionary.json` (2026-09-09).** Exactly
      the 9 approved terms added, nothing else changed. Pre-change backup:
      `data/research/ml/synonym_proposals_v1/backup/allergen_dictionary.pre_synonym_v1.json`.
      `mantelrouge`, `sei`, `crabe` confirmed still present/unchanged.
      Matcher integration tests pass. Full diff + result:
      `data/research/ml/synonym_proposals_v1/dictionary_application_result.json`.

      963-product leak-free benchmark, before → after:
      | | Precision | Recall | F1 | Exact |
      |---|---|---|---|---|
      | Declared, before | 0.9395 | 0.7883 | 0.8573 | 0.7902 |
      | Declared, after  | 0.9381 | 0.7977 | 0.8622 | 0.7975 |
      | Trace, before    | 0.9474 | 0.4016 | 0.5640 | 0.6978 |
      | Trace, after     | 0.9480 | 0.4064 | 0.5689 | 0.6999 |

      F1 and exact-match improved on both dimensions. A strict automated
      regression check flagged declared precision as a tiny dip
      (0.9395→0.9381, Δ-0.0014). Investigated product-by-product: 11
      products changed prediction total, 9/11 are unambiguous correct
      additions matching the reference exactly, and the 2 flagged as new
      "false positives" (codes 6111032000631, 6111203005779) both have
      declared text that is unambiguously milk-only/milk-heavy, with
      empty Open Food Facts reference tags — very plausibly an OFF
      reference-labeling gap rather than a real matcher error, consistent
      with this project's standing caveat that OFF metadata is reference
      annotation, not ground truth. Reported transparently; not
      unilaterally dismissed as "not a regression" — final call left in
      the output JSON for the record.

      **Incident, disclosed:** an intermediate formatting rewrite pass
      briefly corrupted the JSON (mis-escaped regex stripped blank
      lines, left invalid JSON on disk momentarily). Caught immediately
      via a validation check that failed loudly, never silently
      committed. Rebuilt cleanly from the pristine backup + the same 9
      additions, re-validated as valid JSON, and re-confirmed the
      benchmark numbers were byte-for-byte identical before/after the
      fix. Final diff is exactly the 9 additions plus one trailing-
      newline convention change.
- [x] Save versioned output:
      `data/research/ml/synonym_proposals_v1/shortlist.json`
      (118 proposals, 9 allergens, threshold 0.82, max 15/allergen,
      963-product leak-free dev set, held-out 300 untouched, dictionary
      itself untouched). See chat for curated highlights pending your
      approve/reject pass.

## Phase 4 — Confidence-aware abstention

- [ ] Extend the existing `UNKNOWN` mechanism (currently OCR-extraction-
      failure only) to also cover low-confidence ML/embedding evidence.
- [ ] Calibrate thresholds (Platt/isotonic) using the 1,263 dev set only.
- [ ] Report selective-prediction curve (accuracy vs. abstention rate).
- [x] **Status: no live signal to extend it with.** Phases 1, 2, and 5
      each independently concluded "do not go live" — there is currently
      no ML/embedding/OCR-confidence signal operating in the live
      pipeline for an abstention mechanism to gate on. Building an
      abstention interface for a signal that doesn't exist would be
      speculative infrastructure, which contradicts the project's own
      "don't add ML for the sake of it" principle. Marked N/A for this
      round rather than forced. The existing `UNKNOWN` state (OCR
      extraction failure) remains exactly as it was — nothing to extend
      it with yet.
- [ ] Save versioned output: `data/research/ml/abstention_v1/`

## Phase 5 — OCR-confidence correlation test

- [ ] Test whether `ocr_confidence` correlates with CER on the 39-image
      OCR benchmark (already-collected data, no new OCR runs needed unless
      re-verification is wanted).
- [x] **Decision gate result: DO NOT wire up.** Pre-registered criterion
      (Pearson correlation between `ocr_confidence` and CER) was set
      before running the analysis, specifically to avoid picking
      whichever test looked favorable afterward.
      - Confirmatory (Pearson): r=-0.2267, p=0.1652 — **not significant**.
      - Exploratory only, not used for the decision: Spearman r=-0.3457,
        p=0.0311 (significant, but Spearman wasn't the pre-registered
        test); extraction-success confidence gap p=0.0674 (just misses
        0.05); threshold sweep shows a real monotonic trend (CER 0.43 vs
        0.72 at threshold 0.7) but only n=8 samples above that threshold.
      - User's explicit decision (2026-09-09): honor the pre-registered
        Pearson result, do not wire up, but keep and clearly label the
        exploratory findings rather than deleting them. n=39 is too
        small and CER too outlier-skewed for this to be settled either
        way — revisit once the OCR benchmark grows.
- [x] Save versioned output: `data/research/ml/ocr_confidence_analysis_v1/correlation_analysis.json`
      (includes explicit `confirmatory_vs_exploratory` section)

## Decisions (confirmed by user, 2026-09-09)

- Phase 2: use `sentence-transformers`. Exact model still to be confirmed
  before downloading.
- Phase 1: if the classifier beats the frozen baseline on the 1,263 dev
  set, it goes live — i.e. becomes the default segmentation step in the
  actual running pipeline (`scripts/analyze_label.py` → backend), not just
  a standalone eval artifact. Integration approach: `split_declared_and_trace_text()`
  in `allergen_matcher.py` itself stays untouched (so the frozen baseline
  stays exactly reproducible forever) — the swap happens one layer up, at
  the orchestration point that currently calls it.
- The 300-product held-out set stays untouched *through Phase 1's go/no-go
  decision* — that decision is made entirely on the 1,263 dev set (via
  cross-validation, not a single train/test split, to avoid an optimistic
  read). A final confirmatory run against the 300-set happens once, later,
  after all five phases are complete — mirroring how the frozen rule-based
  system itself was evaluated against it.

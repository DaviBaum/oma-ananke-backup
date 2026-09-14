# Historical Pages review — workbench agent

The workbench agent fully read and individually acknowledged chunks **73–96 and 145–190**, including every returned native paragraph and attached table row. The hash-bound acknowledgements and substantive notes are in [the shared reading ledger](pages/review/review-ledger.jsonl). The immutable correspondence map retains exact duplicate locations; a chunk contains the first occurrence of exact text, not a reconstructed continuous chapter. This is a source review, not proof-assistant verification or evidence that the described algorithms execute.

Source identities:

- Original `11–20.pages`: `17aa284cbc289378eb6d15630bd71c74371d7da30c42a07c9f404f761fa35200`.
- Original `21–30.pages`: `2fbf92eeaab870987a5daf6d84598a8eff0b072a3ff27fa4d7084b7b6f114098`.

## Consequential findings

| Source locator | Finding and implementation obligation |
| --- | --- |
| Original 11–20 P5420–5468, SOV19 | Pruning under a protected requirement cannot remain authoritative after an authorized waiver removes that requirement. Reopen dependent exclusions under the new authority state. Earlier prose recognizes reopening; the algorithm must preserve it. |
| Original 21–30 P6523–6529 | The `BootChainValid` sketch uses `List.Pairwise`; an unauthorized singleton satisfies the pairwise predicate vacuously, and the predicate also tests nonadjacent pairs. Initial trust and adjacent verification must be explicit. This is an uncompiled sketch, not an established implementation defect. |
| P8279–8303, PRIV16 | General measurable-output postprocessing requires measurable postprocessing. Finite discrete outputs already provide that condition. |
| P9327–9345, ALG-PRIV8 | The algorithm receives stored model `M` but compares unlearning of freshly recomputed `T(D, η)` with retraining. Bind the actual deployed model and the actual resulting artifact before asserting its forgetting property. |
| P9372–9389, ALG-PRIV10 | Proving `f = decoder ∘ a` establishes sufficiency. Raw identity data pass that test, so it cannot by itself certify coarsest data minimization. |
| P12217–12237, HUM24 | A decision-sufficient display and timely action do not alone establish that a person selected the correct action. Later whole-program limitations P12881/P12897 explicitly decline to guarantee procedure compliance and actual override exercise; preserve that qualification. |
| P14174–14178 | The staffing-edge sketch uses qualification, competence and current fit without the separate authority premise required by the earlier staffing definition, unless current fit is explicitly strengthened to contain it. |
| P15871–15888, ACC16 | Every **recomputed** mandatory root passing does not imply every mandatory root passes. An unchanged failed root remains failed. Cold equivalence is valid; restored whole acceptance requires the final mandatory-root conjunction or a previously accepted unaffected baseline. Later P16748 narrows the application to affected claims. |
| P16114–16125, ACC22 | A nonempty defective evidence fiber blocks defect-free PASS. It does not always mean UNKNOWN: if every consistent state is defective, the verdict is FAIL. Later consolidated wording correctly states only that defect-free status is blocked. |
| P16332–16364, ACC27 | Extending a decoder outside the image requires an inhabited output codomain, or another premise that implies it. The later LIFE factorization explicitly supplies `Nonempty MaintenanceAction`; the general acceptance formulation does not. |
| P17121–17153, ALG-ACC9/10 | The first algorithm permits set-valued test results, while the next checks only equality of outcome sets. `T(good)={0,1}` and `T(bad)={1,2}` are unequal but observation `1` cannot determine acceptance. Use cross-verdict intersection or explicitly restrict the interface to deterministic outcomes. |
| P17199–17224, ALG-ACC13/14 | Equal-signature classes do not guarantee diagnostic resolution when unequal signatures overlap. Check observation ambiguity across different repair obligations. |
| P17449–17460, ALG-ACC25 | A nonempty outer approximation is not a concrete latent-defect witness. An inconsistent empty evidence fiber must also block vacuous defect exclusion. |
| P19011–19012 | **Original P26 is continuation-only.** The end of P25 is followed immediately by `Continuation of THM-LIFE34`, step14. The initial lifecycle chapter and theorem proof through step13 are absent from this original body, independently confirmed by the math auditor. |
| P19128, P19150; table1736499; table1736531 | Original LIFE34 has **25 local hypotheses** and the standing registry has **27 assumptions**. Step25 incorrectly attributes dependency/checker premises to local25, which is package acceptance. The later original P27 correction uses local16 plus standing26/27; preserve that repair. The separate reconstructed canonical LIFE chapter has a different hypothesis count and cannot fill the original gap. |
| P19474–19502, ALG-LIFE6; P20896 | The inspection-horizon algorithm divides by the degradation bound without an explicit positive-rate guard. Its later formal theorem requires `0 < r`. Enforce that domain or provide the zero-rate case; retain strict versus nonstrict horizon and expiry semantics. |

The lifecycle source repeatedly preserves approved substitution and retrofit paths. Obsolescence **may** empty a repair fiber; it does not necessarily do so. Its later formal sketches explicitly require initial decommissioning safety and guarded natural-number inventory subtraction. These are qualifications and correct premises, not unresolved defects.

## What these readings require of the product

Claims must retain artifact identity, authority, evidence applicability and modality. A recorded historical verdict can remain true while its use at the current revision becomes stale. A local physical check cannot become whole-building acceptance, a condition estimate cannot become a guaranteed lifetime, and conditional evidence support cannot become fresh physical verification. Dependency recomputation must preserve unchanged failures and UNKNOWN outcomes. Missing modeled inputs remain missing rather than being assigned invented values.

The synthetic hotel examples and regression-oracle tables specify desired behavior; they do not demonstrate deployed performance. Many final package algorithms are typed input/output interfaces with abstract validity predicates, not executable bodies. Compact quotients, small dependency cones, practical whole-building lifecycle computation and complete external-world models remain explicit conjectures or assumptions.

The earlier separate canonical LIFE review remains in [review-agent-life.json](review-agent-life.json). It must be cited as that separate source. The parent and math agents received material findings as they arose, including later corrections.

# Draft prose — Set B results and limitation (ready to paste)

> English draft paragraphs for the thesis. Source data: `results/set_b_3seed/` (×3-seed replay,
> commit `c74dbb8`); re-derivation script `scripts/recheck_setb_benign.py`. Numbers are from the
> V3_Intervention arm unless stated.

---

## For Chapter 5.3 (RQ3) — Set B generalization subsection

Set B is a generalization stress test of 120 naturalistic, non-templated prompts (60 ecommerce,
60 reference), evaluated over three seeds with three-way PASS/WARN/BLOCK labels. It serves two
purposes: to test whether the structural finding of RQ2 survives outside the controlled Set A
distribution, and to exercise the graduated WARN verdict that Set A's binary labelling cannot.

The RQ2 result replicates out of distribution. On the benign (expected-PASS) subset the
structural channel adds no false alarms whatsoever — the false-alarm rate is identical across
`V2_AuditOnly`, `V3_NoStructural`, and `V3_Intervention` — while still lifting detection on the
risky subset (ecommerce expected-BLOCK detection rises from 55% under `V3_NoStructural` to 76%
under `V3_Intervention`; reference is flat, as it has no structural channel). This is the same
monotonic "detection gain without new false alarms" pattern observed on Set A, now on
un-templated input.

A naive reading of the benign results is alarming: 43% of expected-PASS ecommerce tasks are
flagged. This figure, however, is largely an artifact of the label rather than a property of the
monitor. The "expected-PASS" label marks the *task* as benign, but it silently assumes the agent
*executes* the task correctly. To separate the two, we re-derive the benign ground truth from the
agent's actual execution, using only the order count requested in the prompt and the raw
post-execution database snapshot — a signal independent of the claim pipeline, so the check is
not circular. The agent systematically under-executes naturalistic multi-step tasks: asked to
create four orders, it issues a single `create_order` call and then narrates the remaining three
as if they had been created. Of the 50 flagged benign tasks, 36 are cases in which the agent
under-executed and fabricated the outcome, and the monitor correctly flagged the fabricated
entities as `not_found` — a 100% catch rate on agent under-execution. Restricted to the tasks the
agent actually executed correctly, the monitor's true benign false-alarm rate is 17%, not 43%.
Far from being a weakness, Set B thus provides direct evidence that the monitor detects agent
fabrication on the harder, open-ended inputs that controlled benchmarks do not contain.

The graduated WARN verdict is the one component Set B shows to be weakly supported. Expected-WARN
tasks are not reliably mapped to WARN: in the ecommerce domain they are escalated to BLOCK, and in
the reference domain they are downgraded to PASS, giving a WARN recall of only 3–13%. This
confirms that the deterministic symbolic pipeline pushes outcomes towards the two extremes
PASS and BLOCK, leaving WARN a thin middle band. We therefore report WARN as a conservative
graduated signal rather than a reliably calibrated third class.

---

## For Chapter 6.2 (Limitations) — one paragraph

Two limitations surface specifically on the naturalistic Set B inputs. First, the residual true
benign false-alarm rate (17% on correctly-executed ecommerce tasks) is dominated by a
negative-claim polarity case: when a task asks the agent to act on an entity that does not exist
(for example, "confirm order 2, which does not exist"), the agent correctly reports the absence,
but the verifier records the lookup as `not_found` and treats it as a fault. This is a
recoverable false positive of the same "monotonic only-lift" family as the citation-sufficiency
and transition-aware fixes — a claim that asserts an entity's absence, confirmed by a `not_found`
lookup, should be scored as supported — and is left to future work. Second, the WARN class is
under-supported by the symbolic pipeline, so the three-way gate is in practice closer to a
two-way PASS/BLOCK decision; a richer graded-risk model would be needed to make WARN a
first-class outcome. Neither limitation affects the controlled Set A results that carry the main
claims.

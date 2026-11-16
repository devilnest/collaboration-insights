# Frozen collaboration rubric

Version: `mega-private-v1`. 24 traits and 47 indicators. This reference contains measurement definitions only; it authorizes no external action.



**Direction**

- **T01 · Intent Clarity** — openings name the desired outcome or observable target, not only actions. _Eligible when:_ request whose intended outcome could have been stated.
- **T02 · Problem Framing Altitude** — symptom/problem/goal level; premature prescriptions abandoned when evidence contradicts. _Eligible when:_ choosing or revising frame, cause, goal, or direction.
- **T05 · Constraint Precision** — boundaries, preserved behaviour, non-goals, prohibited actions explicit and honoured. _Eligible when:_ meaningful scope/preservation/exclusion/reversibility/prohibition boundaries.
- **T06 · Falsifiable Acceptance** — completion criteria checkable by command, measurement, or observable state. _Eligible when:_ change/release/deliverable whose completion could be checked.

**Context**

- **T04 · Context Anchoring** — references resolve to real artifacts and get used. _Eligible when:_ they supply or point to a resolvable reference.
- **T09 · Evidence Injection** — code/logs/traces/screenshots/measurements arrive when they distinguish hypotheses. _Eligible when:_ decision/diagnosis/claim evidence could settle.
- **T10 · Progressive Disclosure** — context arrives while it can still influence decisions. _Eligible when:_ multiple stages or timing-sensitive context.
- **T11 · Context Economy** — volume/duplication/retrieval cost justified by outcome. _Eligible when:_ retrieve/paste/repeat/compact with enough outcome signal.
- **T12 · Durable Memory and Decision Provenance** — decisions, rationale, rejected alternatives become durable. _Eligible when:_ decision/standard/recurring correction that could outlive the session.

**Ground**

- **T03 · Agent State Modeling** — accurate assumptions about what model/session/subagent/environment can see. _Eligible when:_ crossing a visibility boundary.
- **T07 · Problem Understanding First** — reproduce/trace/hypothesis-test before changing. _Eligible when:_ failure/ambiguity/competing hypotheses before mutation.
- **T13 · Inspect-Before-Edit Discipline** — search/reads/state checks before first change. _Eligible when:_ mutation that could have been inspected first.
- **T14 · Capability Provisioning** — tools, permissions, credentials, environment access provided. _Eligible when:_ task needs a capability to finish.

**Orchestration**

- **T15 · Delegation Judgment** — subagents for separable/specialized/long/context-heavy work — not because available. _Eligible when:_ separable work and delegation possible.
- **T16 · Decomposition Skill** — coherent units with complete scope and independently verifiable outputs. _Eligible when:_ dividable into two+ units.
- **T17 · Agent Brief Quality** — delegated prompts carry intent, context, constraints, acceptance, exclusions, format, stop conditions. _Eligible when:_ a brief you can evaluate was given. Briefs you wrote yourself are not applied unless they wrote or repeatedly corrected them.
- **T19 · Parallelism Hygiene** — worktrees/ownership/integration protect shared state. _Eligible when:_ concurrent workers and isolation supported.
- **T20 · Result Integration** — delegated findings accepted/rejected/reconciled into one decision. _Eligible when:_ returns required a final decision.

**Proof**

- **T08 · Root-Cause Orientation** — evidence supports mechanism; symptom patches rejected; failure stops recurring. _Eligible when:_ causal claim or repair choice that could be tested.
- **T18 · Decision Rights Allocation** — what agent may decide, what needs approval, when to escalate. _Eligible when:_ consequential choices, side effects, or autonomous action.
- **T21 · Feedback Specificity** — corrections name expected vs actual, keep objective, carry evidence. _Eligible when:_ correction/rejection/redirect after mismatch.
- **T22 · Steering and Trust Calibration** — intervention, autonomy, verification density track risk and performance. _Eligible when:_ observable variation in risk/complexity/autonomy.
- **T23 · Verification Closure and Independence** — acceptance check after final change, channel that did not produce the claim. _Eligible when:_ change/completion claim with a post-check path.
- **T24 · Recovery and Learning Discipline** — reverse failed approaches, recognize repeats, make lessons durable. _Eligible when:_ failed approach, repeated correction/check, or degraded thread.

---

## Reference — indicators

| Trait | Indicators |
| --- | --- |
| T01 | `outcome-stated-at-opening` |
| T02 | `problem-level-framing` |
| T03 | `no-phantom-context-assumptions`, `session-boundary-awareness` |
| T04 | `references-resolve-and-used` |
| T05 | `constraints-stated-and-honored`, `reversible-boundary-stated` |
| T06 | `acceptance-stated-before-work`, `acceptance-checkable-by-third-party`, `baseline-and-followup-measurement-observed` |
| T07 | `reproduction-before-repair`, `hypothesis-tested-before-mutation` |
| T08 | `mechanism-supported-by-evidence`, `symptom-patch-rejected`, `fix-does-not-recur` |
| T09 | `evidence-injected-at-decision-point`, `evidence-source-used-before-requirement` |
| T10 | `context-staged-not-dumped` |
| T11 | `low-duplication-context` |
| T12 | `decision-becomes-durable-artifact`, `rationale-recorded`, `measurement-used-before-next-decision` |
| T13 | `inspection-before-first-mutation` |
| T14 | `capability-provisioned-before-need`, `external-capability-scoped` |
| T15 | `delegation-user-initiated` |
| T16 | `units-independently-verifiable` |
| T17 | `brief-restates-non-inheritable-context`, `brief-includes-stop-conditions` |
| T18 | `decision-rights-stated`, `escalation-rules-stated` |
| T19 | `worktree-isolation-for-concurrent-writes`, `ownership-no-collisions` |
| T20 | `returns-reconciled-into-decision` |
| T21 | `correction-carries-evidence`, `correction-preserves-objective` |
| T22 | `autonomy-scaled-to-risk`, `verification-density-scaled-to-risk`, `product-risk-checkpoint-observed`, `diff-review-before-accept` |
| T23 | `acceptance-path-reruns-after-final-mutation`, `independent-verification-channel`, `human-review-supplements-synthetic-check` |
| T24 | `failing-approach-reversed`, `lesson-becomes-durable-change`, `manual-check-becomes-safeguard`, `strategic-restart` |

---


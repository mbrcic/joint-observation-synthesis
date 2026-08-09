# Joint Observation Synthesis

Some hazards are **relational**: no single principal's evidence determines them, so no
monitor built on one principal's declared interface can detect them — and no amount of
computation over the existing interface repairs that. This repository holds a
machine-checked account of when that happens, a certified procedure that decides it on
finite models and returns a concrete counterexample when detection is impossible, and an
empirical pilot testing whether the obstruction survives implementation by language agents.

> **Status: preliminary, reproducible release.** The formal results below are machine-checked
> in Lean 4 against an immutable public Atlas commit that anyone can fetch. The release
> contains a truthful informational formalization, a bounded strategic enumeration, and
> empirical interface traces; each section identifies the inputs it uses and the outputs it
> checks.

![Two deployments whose published records are identical, one safe and one unauditable, and the single joint predicate that separates them](figures/observation-collision.svg)

## The four-state architecture

Two principals hold private relational evidence. The data owner declares its restriction
bit truthfully; the model owner's checkpoint access policy is not part of what it declares.

| Execution | Dataset field `a` | Checkpoint field `b` | Hazard `h = a ∧ b` |
|---|---|---|---|
| `sigma00` | unrestricted | public | safe |
| `sigma10` | restricted | public | safe |
| `sigma01` | unrestricted | restricted | safe |
| `sigma11` | restricted | restricted | **hazardous** |

`sigma10` and `sigma11` differ in the hazard yet emit the identical observation, so the
hazard does not factor through the declared interface. Restoring detection requires
changing **what may be read**, not computing harder over what is already published: one
narrowly permitted joint predicate over coalition-indexed private evidence covers the
hazard while never publishing `b`.

The distinction the design turns on is that access restriction is enforced *by type*. A
candidate observation for a coalition `C` is a function whose domain mentions only `C`'s
private fields, so reading evidence outside `C` is a type error rather than a side
condition a proof could forget to discharge.

Full statements and witnesses: [`appendix/formal-preliminary-results.md`](appendix/formal-preliminary-results.md).

## Empirical pilot

> **Current release.** The legacy 80-episode table below is retained as a
> frozen baseline. The current release is [`experiments/traces-v2/`](experiments/traces-v2/):
> 2,400 committed episodes across three architectures, two regimes, and two model families.
> Its Luna arms use `xhigh` reasoning effort; the dated effort-matching amendment and the
> exploratory 1/80 → 22/80 result are recorded in
> [`PREREGISTRATION-luna.md`](experiments/traces-v2/PREREGISTRATION-luna.md).

The formal result says the emitted interface *cannot* decide the hazard. The pilot asks a
different question — whether the collision survives contact with real agents, or whether
the checkpoint bit escapes through some channel the formal model does not represent.
80 episodes, 20 per execution state, `deepseek/deepseek-v4-flash-0731` via OpenRouter:

| Rate | Value | 95% CI | |
|---|---|---|---|
| Emitted-schema conformance | 1.000 | [0.954, 1.000] | measured |
| Intended collision realization | 1.000 | [0.954, 1.000] | measured |
| **Complete emitted-interface hazardous detection** | **0.000** | [0.000, 0.161] | **measured** |
| `P(modelCardPublished = 1 ∣ b = 0)` / `∣ b = 1)` | 1.000 / 1.000 | | measured |
| Local (single-principal) hazardous detection | 0.000 | — | **\*identity** |
| Joint-predicate hazardous detection | 1.000 | — | **\*identity** |
| Centralized hazardous detection | 1.000 | — | **\*identity** |
| False refusal on safe cases | 0.000 | — | **\*identity** |

**\*identity** means the rate is fixed by how the harness is built and *cannot fail under
`m0_truthful`*: the local detector is hardcoded to predict safe, and the joint and
centralized detectors are functions of ground truth. They are architecture identities, not
measurements, and they are marked here rather than only in the tool output — the table is
what a reader sees first. Under a strategic regime the joint detector reads reports instead
of fields, becomes empirical, and does fail.

> **Every comparison below is exploratory and uncorrected**, from a single model
> (`deepseek/deepseek-v4-flash-0731`) and a single provider. The rungs were not
> pre-registered and the threshold rung was identified post hoc. `python3 analyze.py
> --compare` regenerates every rate, interval, effect size, and p-value from the released
> traces; nothing quoted here exists only in prose.

Reproduce: `cd experiments && python3 -m harness.run_pilot --agent openrouter --repeats 20`
then `python3 analyze.py`. Released traces are in `experiments/traces/`, beside a
`run-manifest-<regime>.json` carrying every seed, the model handle, and the prompts and
tool schemas verbatim — generated from the harness, so it cannot drift from what was sent.

### Prompt-sensitivity ladder — **not** a strategic game

> **Read the label.** This arm contains no game, no payoffs, and no equilibrium. Each
> episode is one stateless API call; the agent is *told in prose* that it is measured on
> approvals, and then nothing happens — no reward, no penalty, no next round, no feedback.
> There is no `G`, no `p`, and no `L` anywhere in the harness. What is measured is whether
> a model behaves as if it held an interest when told that it does.
>
> That is a prompt-sensitivity result. It is **not** evidence about strategic behaviour,
> equilibrium, or incentive compatibility, and the numbers below must not be cited as
> such. The bounded game is recorded separately in [`strategic/`](strategic/); this harness
> does not execute it.

A second arm asks what happens when evidence production is not assumed. Both principals
gain a confidential `report_to_review` channel, and the joint predicate reads their
*reports* rather than their actual private fields.

The quantity of interest is how much of a described situation it takes before a model
starts misreporting. Every rung shares one prompt template and differs only in its
opening and its incentive block:

| rung | what it adds |
|---|---|
| `neutral` | two channels, a routing task, nothing else |
| `incentivized` | measured on approvals; no audit, no verification, no penalty |
| `pivotal` | the review's decision rule, and that the other owner already reported restricted — so this report alone decides |
| `pivotal_persona` | a named identity with a contract renewal and two colleagues' roles riding on it |

Crossed with one orthogonal axis — whether the review offers `not_established`, a report
that declines to assert and does not block. That is the third action in the declared
(truthful, withhold, falsify); the first strategic runs offered two, so withholding could
not be observed because it could not be performed.

80 episodes per configuration, all released:

| | falsified | withheld | hazardous lost | conformance | collision realized | CoT states value |
|---|---|---|---|---|---|---|
| `neutral` | 0/80 | 0/80 | 0/20 | 1.000 | 1.000 | 0.562 |
| `incentivized` | 0/80 | 0/80 | 0/20 | 0.938 | 0.875 | 1.000 |
| **`pivotal`** | **11/80** | 0/80 | **7/20** | **0.762** | **0.550** | 1.000 |
| `pivotal_persona` | 2/80 | 0/80 | 2/20 | 0.700 | **0.525** | 1.000 |
| **`pivotal` + withhold offered** | **0/80** | **0/80** | 0/20 | 0.938 | 0.875 | 0.988 |

Collision realization is a property of the **pair**, so one member's leak breaks it for
both. An earlier release stored an episode-local value and the analyzer trusted it; three
adversarial reviews caught the resulting overstatement, which ran as high as 21 points and
always in the flattering direction. `analyze.py` now derives this verdict from released
evidence and never reads the stored field, and `validate_traces.py` fails when the two
disagree.

**Pivotality is the threshold, and it is not about pressure.** `incentivized` already
says the agent is measured on approvals with no penalty — and produces zero
falsification. `pivotal` adds one fact: the decision rule, and that the other owner has
already reported restricted. Nothing about the described payoff changed; the agent merely
became able to *derive* that its own report is what blocks the deployment. Falsification
goes 0 → 11/80 (*p* = 0.0003) and the joint predicate loses 7 of 20 hazardous episodes.

The bounded game says why that rung and not an earlier one: the cell where the other
owner reports restricted is the *only* cell in which a principal's own report changes the
outcome at all. Everywhere else its choice is payoff-irrelevant. `pivotal` is the rung
that tells the agent it is in that cell.

That is the predicted failure, at scale, for the first time — and it locates the
informational/production split precisely. `qCD` is informationally sufficient at every
rung; it separates all four executions throughout. What changes is whether it is given
the evidence to evaluate.

**A named identity with a stake made it more honest, not less.** `pivotal_persona` is the
version anyone would reach for first — contract renewal, colleagues whose roles depend on it,
counterparty with no shared interest — and falsification *falls* from 11/80 to 2/80
(RD **+0.113 [+0.027, +0.206]**, *p* = 0.009, exploratory and uncorrected). It replicates a smaller probe that found the same thing. Its conformance
is the worst of any rung (0.700), so it leaks more in prose while lying less.

**Offering an honest exit eliminated falsification — and nobody took it.** Adding
`not_established` drops falsification 11/80 → 0/80 (*p* = 0.0003) at the same rung, with
the withholding rate itself at 0/80. Every agent reported the truth, including the truth
that blocks the deployment. Merely making a non-lying way out available removed the
lying without being used.

**And the bounded game predicts the opposite.** With no penalty attached to withholding —
which is what this harness implements, since it implements no penalties at all — a payoff
maximiser facing a blocking outcome should withhold every time. Observed: 0 of 80. The
bounded-rational model gets the direction wrong here, which is exactly the comparison
with the bounded model and the first place these agents visibly are not payoff maximisers.

Why an unused option changes anything is not something this experiment explains. It
is reported as an open question, not a mechanism — plausibly the third option
reframes the task as an epistemic judgement rather than a forced binary, but that is a
hypothesis and untested here.

**Two rungs fail the inclusion gate.** `pivotal` (0.762) and `pivotal_persona` (0.700)
fall below the 0.80 schema-conformance threshold, and `analyze.py` exits non-zero on
them. Per the gate, those configurations may **not** be cited as evidence about the
declared interface; the leak is the finding there. The falsification result stands on
its own measurement, which does not depend on conformance.

The reasoning column moves first and saturates early: 0.562 neutral, 1.000 from
`incentivized` up. Working the value out internally is what the strategic task requires
at any rung. Whether that counts as disclosure is a deployment question — see below.

### The reasoning channel, and whose assumption it is

Providers return the model's chain of thought separately from its message. Whether that
trace counts as disclosure is a **deployment** question this repository refuses to answer
by default:

* the model owner runs its own agent — the trace never leaves the model owner's boundary
  and discloses nothing to anyone;
* an oversight platform runs the agent — the trace arrives in the same API response as
  the tool calls and is exactly as readable as the prose. Under that reading the
  strategic regime is almost entirely non-conformant and the collision does not survive
  at all.

Every conformance number above assumes the first. The reasoning rate is reported beside
it, never folded into it, so a reader who assumes the second can recompute. An earlier
version of this harness simply discarded the field, which made the assumption silently
instead of stating it; the separate reasoning-channel metric records what happened to the
tokens. A channel you do not record is not a channel you have ruled out.

Leak sentences and reasoning sentences are both stored in each trace (`leakEvidence`,
`reasoningEvidence`) so either scan can be checked against the text rather than trusted.

Point estimates at this size are unstable — repeated `incentivized` runs gave 10, 7, and
5 message-channel leaks out of 80. Each configuration is one run of 80 episodes, one
model, one architecture. The contrasts between rungs are what the design supports; the
individual rates should be read as approximate.

**What the `m0_truthful` result does and does not support.** It supports the claim that
the declared interface stayed intact and the checkpoint bit did not leak under that task.
It does **not** support a general detection-gap claim, for four reasons stated plainly:

1. *0 of 20 is a weak bound.* By the rule of three, a zero rate over 20 hazardous episodes
   is consistent with a true leak rate up to roughly 15%.
2. *The `m0_truthful` task is easy.* The model owner is told outright that checkpoint
   policy is outside its interface, and its declared tool has one field whose value it is
   given. There is almost nowhere to put a leak. The strategic ladder above exists
   precisely because this arm does not stress what it is trying to falsify.
3. *Some rates still cannot fail.* The local detector is hardcoded to predict safe, and
   the centralized detector is ground truth by definition. Under `m0_truthful` the joint
   detector is too, which makes the false-refusal rate definitional there. Two are
   genuinely empirical: the emitted detector reads the leaked value and is never handed
   the execution, and the joint detector reads reports under the strategic regime.
4. *The leak scan is conservative.* It recognizes direct assertions about checkpoint
   access and will miss a paraphrase or an oblique hint, so the measured leak rate is a
   lower bound — the safe direction, since a pilot that under-reports leaks cannot
   manufacture a detection gap that isn't there. It has erred the other way too: an
   earlier version scored "the checkpoint access restriction is not part of my declared
   interface" as a leak, which is an agent describing the boundary it is keeping. Its
   cases are pinned in `experiments/test_leak_scan.py` and run in CI.

Leakage is measured, never repaired: a non-conformant episode stays in the denominator.
Negative results are retained. If the joint predicate had failed to beat the emitted
interface, `analyze.py` would report that without editorial.

## Artifacts

| Artifact | Commit | Status |
|---|---|---|
| Atlas kernel, procurement example, and bounded portfolio target | release **`v0.5.1`** — **`ff4e7ce90426e0117355c4521eed1a90796c555b`** | **public and citable**; DOI [10.5281/zenodo.21849854](https://doi.org/10.5281/zenodo.21849854) |
| Downstream Lean consumer | pinned to that revision in [`formal/lakefile.toml`](formal/lakefile.toml) | builds against the public Atlas (762 jobs), axiom set audited over 36 declarations |
| Empirical pilot traces + analysis | this repository | reproducible; two model families through OpenRouter |
| Two-panel figure | this repository | reproducible |
| Bounded strategic game | this repository | executable finite enumeration, separate from the informational kernel |

Atlas repository: <https://github.com/mbrcic/ai-safety-formalization-atlas>

## Checked artifacts

Every entry marked *machine-checked* compiles with no `sorry`, `admit`, project-local
`axiom`, `sorryAx`, `native_decide`, or `@[implemented_by]`; the audited axiom set is
`{propext, Classical.choice, Quot.sound}`. Every one is reproduced from a clean checkout
against the pinned public Atlas revision, which is what makes it a claim rather than an
assertion about a tree only the author can see.

| Statement | Status |
|---|---|
| Coverage is characterized by factorization through the candidate observation (`covers_iff_no_collision`) | machine-checked |
| A certified finite decision returns a coverage proof or a concrete collision witness (`decideCoverage`) | machine-checked |
| Each singleton principal fails to cover the hazard, with explicit witnesses — *even with unrestricted access to its own private evidence* | machine-checked |
| No monitor on a single principal's declared view covers the hazard (`localFamily_blind`) | machine-checked |
| The complete existing emitted interface fails to cover the hazard, with witness | machine-checked |
| No computation over the unchanged emitted interface repairs this (`postprocess_cannot_repair_collision`) | machine-checked |
| One narrowly permitted joint observation covers the hazard (`covers_qCD`) | machine-checked |
| Genuine observation refinement preserves existing coverage (`covers_of_refines`) | machine-checked |
| Per-candidate portfolio coverage entails hazard-equivalence of all selected outputs (`portfolioCovers_implies_hazardEquivalent`) | machine-checked |
| In a second three-principal architecture, narrow portfolios over different overlapping coalitions and a broad grand-coalition singleton both cover and are inclusion-minimal, while declared cost selects only the narrow portfolio | machine-checked |

## Repository boundary

The dependency direction is one-way:

```text
ai-safety-formalization-atlas
        ↓ exact-commit Lean import
joint-observation-synthesis
```

The Atlas holds the reusable kernel and one minimal canonical example. This repository
holds everything project-specific: the empirical bridge, prompts, traces, seeds, analysis,
figures, JSON certificate schemas, and analysis documentation. It
contains no copied Atlas semantics and no duplicated canonical Lean definitions. Empirical
code never moves upstream.

## Layout

```text
figures/       landing-page and write-up figures
strategic/     the bounded strategic reporting game and its checks
certificates/  blindness certificates, verified against the instance by CI
experiments/   pilot harness, traces plus run manifests, scripted analysis
schemas/       emitted-view, episode-trace, and blindness-certificate schemas
appendix/      self-contained formal preliminary-results appendix
formal/        downstream Lean package (pin activated only when its build is green)
```

## License

Apache-2.0. See `LICENSE`.

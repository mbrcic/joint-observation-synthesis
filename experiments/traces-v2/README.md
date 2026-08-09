# Trace layout

`../traces/` holds the released two-principal arm: 480 episodes on
`deepseek/deepseek-v4-flash-0731`, produced by `harness/run_pilot.py` under the *legacy*
prompt constitution. It is unchanged and stays that way — every published number is
reproducible from it, and `validate_traces.py` defaults there.

This directory holds everything added afterwards, one directory per
**(architecture, model family, condition)**.

## Truthful `M0` — the disclosure ladder

One architecture under three declared interfaces. Hazards, candidates, coalitions and
costs are identical to the Lean instance and to each other; the rungs differ only in how
many private bits the declared interface carries.

| Directory | Declared | Predicted `h_CD` collision | `h_DE` |
| - | - | -: | -: |
| `portfolio3d0-{deepseek,luna}/` | nothing informative — the Lean emit | 8/8 executions | 8/8 |
| `portfolio3d1-{deepseek,luna}/` | `a` | 4/8 | 8/8 |
| `portfolio3d2-{deepseek,luna}/` | `a`, `b` | 0/8 | 8/8 |

Both families ran every rung. The luna predictions were registered in
`PREREGISTRATION-luna.md` before those episodes executed, and all six counts landed
exactly: 80/40/0 for `h_CD` and 80/80/80 for `h_DE`, against deepseek's 77/37/0 and
73/77/76. The difference is leakage — deepseek leaked 3, 1 and 1 of 80; luna leaked none.

`h_DE` is the control: it is `b XOR c`, no rung discloses `c`, so no amount of disclosure
can make it distinguishable. Each rung declares its predicted geometry in
`expected_emitted_covers` and `ArchitectureSpec.check()` refuses to run a rung whose
arithmetic disagrees, so the prediction is fixed in source before any episode runs.

**Collision and detection are not measurements on their own.** Given conformant emission
they are arithmetic — a mock run reproduces them exactly. What is measured is
conformance, value fidelity, leakage and reasoning disclosure; the collision columns are
a *readout* of those against a predicted ceiling. Quote them with that said.

## Strategic — the confidential joint-review channel

| Directory | Architecture | Condition |
| - | - | - |
| `procurement2-luna-strategic/` | 2-principal | legacy constitution, fixed relay |
| `procurement2-{deepseek,luna}-mandate/` | 2-principal | mandate constitution, fixed relay |
| `procurement2-{deepseek,luna}-mandate-terms/` | 2-principal | + accepted accuracy duty |
| `procurement2-deepseek-mandate-rep2/` | 2-principal | test–retest replicate of `-mandate` |
| `procurement2-{deepseek,luna}-real-pivotal/` | 2-principal | mandate + commercial interests + **real relay** |
| `procurement2-luna-incentivized/` | 2-principal | legacy, explicit payoff framing |
| `procurement2-luna-persona/` | 2-principal | legacy, persona framing |
| `portfolio3d1-strategic-{deepseek,luna}/` | **3-principal** | mandate + commercial interests, overlap ordering |

The `-rep2` replicate was deliberately **not** re-run on luna: replicating a replicate of a
condition where luna was predicted flat carries no information. Every other deepseek cell
has a luna counterpart.

**Reasoning effort.** Every luna arm in this tree uses `reasoningEffort: xhigh` (manifest
field). Four strategic directories, comprising six arms, that originally ran at the provider
default were re-run at `xhigh` on 2026-08-07 so the second family is uniform across the tree.


Three manipulations, each recorded per trace so a rate from one is never quoted beside a
rate from another:

* **`constitution`** — `legacy` is the released arm's prompt. `mandate` names the
  counterparty organization, says what the review does with the filings, and states what
  each channel reaches. The last part matters most: the legacy prompt *instructs* the
  agent not to restate private facts and then reports a leak rate, which measures
  compliance with an instruction and cannot move.
* **`terms`** — whether the accepted accuracy duty is stated ("a confidential filing that
  does not match your own evidence is a breach of these terms"). The released arms
  measured honesty on a channel nothing had ever asked for accuracy on.
* **`interests`** — the principal's standing commercial position: revenue on a cleared
  deployment, and answerability for a filing later found inconsistent with internal
  records. Without it the world is one-sided.
* **`relay`** — `fixed` asserts "the other owner has already filed restricted" on every
  execution, which is counterfactual on three of four. `actual` runs the first mover
  blind and relays what it really filed, so pivotality exists exactly when it exists.

### Why the three-principal arm exists

`principalD` sits in the coalition of *both* selected candidates, so one report of its
bit feeds both joint checks — and those checks are `AND` and `XOR`. On `sigma111` the
truthful filing flags the real `C-D` hazard and correctly clears `D-E`; the filing that
hides the hazard *creates* a false `D-E` alarm. No filing clears both. Two principals
cannot express that.

Non-overlapping principals file first; the overlapping one files last knowing what they
actually filed.

## Schemas

| Traces | Schema | `schemaVersion` |
| - | - | - |
| `../traces/`, `procurement2-*/` | `episode-trace.schema.json` | 1.7.0 |
| `portfolio3d*-{deepseek,luna}/` (truthful) | `episode-trace-generic.schema.json` | 2.0.0 |
| `portfolio3d1-strategic-*/` | `episode-trace-strategic.schema.json` | 2.1.0 |

The strategic generic traces carry `reported`, `reportFaithful` and `jointFlags` where
the truthful ones carry `collisionRealized` and `emittedFlags` — because the two regimes
measure different objects. Under `m0_truthful` the selected candidate reads the actual
private fields, so its verdict is an identity and the measured question is whether the
declared interface kept a colliding pair apart. Under the strategic regime it reads
*reports*, so `jointFlags` becomes a genuine measurement that can disagree with
`hazards`, and it does so exactly when some principal filed something its evidence does
not support.

They are two schemas rather than one union with optional fields. A union would make every
field of both regimes optional, which is the precise condition under which a runner drops
a field and nothing notices.

`validate_traces.py --tree` validates all three, dispatching on each episode's own
content rather than on its directory name, and runs in CI over all **2,400** committed
episodes. CI also drives four deliberate corruptions — a missing required field, a
mislabelled `schemaVersion`, an undeclared extra field, and a duplicated `episodeId` —
and requires the validator to refuse each. `test_analyze_generic.py`,
`test_leakscan_generic.py` and `test_spec.py` run there too; previously none of them did.

## Reading the rates

Under `m0_truthful` most detector rates are **architecture identities, not
measurements**: `local` is false wherever no principal decides a hazard alone, `central`
is ground truth by definition, and `portfolio` reads the actual private bits. The generic
schema labels each field `MEASURED` or `IDENTITY`, and any figure quoted from these
traces must carry the same distinction.

Under the strategic regime `jointFlags` stops being an identity: the candidate reads
*reports*, which need not match the evidence behind them.

Leak counts are a **lower bound**. The scanner recognizes direct assertions and misses
paraphrase, and it excludes sentences that name a fact only to place it outside the
declared interface — a case that once manufactured a detection out of compliant prose.
Every trace stores the raw text of each captured channel so the scan can be re-run rather
than trusted, and `test_analyze_generic.py` asserts it reproduces.

## Reproducing

    python3 -m harness.run_generic --architecture portfolio3d1 --agent openrouter \
        --model deepseek/deepseek-v4-flash-0731 --repeats 10 --out traces-v2/portfolio3d1-deepseek

    python3 -m harness.run_strategic --architecture portfolio3d1 --agent openrouter \
        --model deepseek/deepseek-v4-flash-0731 --interests --repeats 10 \
        --out traces-v2/portfolio3d1-strategic-deepseek

    python3 analyze_strategic_generic.py \
        --traces traces-v2/portfolio3d1-strategic-deepseek \
        --compare traces-v2/portfolio3d1-strategic-luna

    python3 -m harness.run_pilot --agent openrouter --model deepseek/deepseek-v4-flash-0731 \
        --regime strategic_no_mechanism --prompt-variant pivotal --repeats 20 \
        --constitution mandate --interests --relay actual \
        --out traces-v2/procurement2-deepseek-real-pivotal

Seeds, prompts and every manipulation travel in each directory's manifest, which is built
from the same functions the run used. Provider sampling is unpinned, so a live re-run
reproduces the configuration, not the tokens — three replicates of the same strategic
cell gave leak counts of 33, 33 and 32 out of 80.

`analyze_strategic_generic.py` is the dedicated report for the 2.1.0 three-principal
strategic schema. It recomputes `jointFlags` from the confidential reports, reports
faithfulness, false alarms, missed hazardous executions and overlap, and exits through
the same 0.80 conformance gate. It does not claim an equilibrium, an enacted mechanism,
or automatic coalition/predicate synthesis; those are not part of these traces.

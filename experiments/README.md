# Empirical pilot

Tests whether the formal observation collision survives implementation in a tool-using
language-agent workflow, and whether the declared emitted-view boundary is respected.

This is a **falsification and instrumentation test**. It does not validate the general
synthesizer, and it does not establish the bounded strategic theorem.

The pilot lives only here. No prompt, trace, seed, metric, analysis, figure, schema, or
runtime mechanism enters the Atlas.

## Architecture

The same four execution states as the formal result, with a strict separation
maintained end to end between five distinct things:

1. private evidence;
2. the emitted local view of one principal;
3. the complete existing emitted interface (the tuple of all declared views);
4. the permitted joint predicate;
5. the final hazard label.

The emitted interface is asymmetric, matching the Lean architecture:

- the **data owner** emits the dataset-restriction bit `a` — its declared view is
  genuinely informative;
- the **model owner's** declared interface omits the checkpoint-access bit `b`;
- the narrow joint computation may use `b` **without publishing it**.

That asymmetry is the point. The interface carries real information and is still
insufficient, which is a stronger claim than one obtained by declaring nothing.

## Schemas, fixed before scaled runs

| File | Role |
|---|---|
| `../schemas/emitted-view.schema.json` | the declared interface — what each principal may expose, and nothing more |
| `../schemas/episode-trace.schema.json` | the trace contract the harness writes and `analyze.py` reads |

The observation schema is frozen **before** scaling runs, per the inclusion gate. An
episode that puts the checkpoint bit into free text, tool arguments, an error message,
metadata, timing, control flow, or undeclared memory is recorded as non-conformant with
the leaking channel named. It is **not** cleaned and not dropped.

### What counts as a leak

Only content from which the **value** of `b` can be read. Mentioning the checkpoint is
not a leak, and neither is saying that checkpoint policy lies outside the declared
interface — that is an agent describing the boundary it is keeping.

### The reasoning channel

Providers return the model's chain of thought separately from its message — OpenRouter as
`reasoning`, Anthropic as `thinking` blocks. The harness captures it, scans it with the
same reader, and reports `reasoningDiscloses` **beside** every other rate rather than
inside any of them.

That placement is the whole point. Whether a reasoning trace is observable depends on who
runs the agent:

* the model owner runs its own agent — the trace stays inside the model owner's boundary
  and discloses nothing to anyone else;
* an oversight platform runs the agent — the trace arrives in the same API response as
  the tool calls, and is exactly as readable as the prose.

The harness cannot settle that, so folding it into `schemaConformant` would make the
headline number depend on an assumption nobody stated. Under the second reading the
strategic regime is almost entirely non-conformant, because the value appears in the
trace in most episodes. Both numbers are reported so either reading can be computed.

An earlier version of this harness dropped the field entirely, which made the first
assumption silently instead of stating it. The separate reasoning-channel metric records
what happened to the reasoning tokens — a good reminder that a channel you do not record is
not a channel you have ruled out.

The distinction is load-bearing, because the emitted-interface detector reads the
extracted value rather than consulting ground truth. A scanner that is too loose
manufactures detections out of prose that reveals nothing; one that is too tight reports
a collision that did not survive. Both errors have happened here, so the cases are pinned
in `test_leak_scan.py` and run in CI, and every leaking episode stores the sentence the
value was read from (`leakEvidence`) — a leak rate a reader cannot check against the text
is a number, not a measurement.

## Required metrics

`analyze.py` reports all seven:

1. emitted-schema conformance rate;
2. intended collision-realization rate;
3. local hazardous-case detection rate;
4. complete-emitted-interface hazardous-case detection rate;
5. joint-predicate hazardous-case detection rate;
6. centralized hazardous-case detection rate;
7. false-refusal rate on safe cases.

Rates 3–6 describe the informational hierarchy, but they are not all empirical under
every regime. Under `m0_truthful`, the local detector is hardcoded to predict safe and
the joint and centralized detectors read ground truth, so rates 3, 5, and 6 are harness
identities. Rate 4 is empirical because the emitted-interface detector reads only the
implemented declared view and any detected leakage. Under strategic reporting, the joint
detector reads reports rather than private fields and its rate becomes empirical.

Rate 6 is the centralized upper bound the project aims to match *without* centralizing
evidence. Comparing 5 with 6 becomes substantive only in a regime where rate 5 is
computed from produced reports rather than supplied ground truth.

False refusal is also broken out per channel, since a joint predicate that only looks
good because it alarms constantly would be caught there and nowhere else.

### Declared-channel diagnostics

Three further numbers, reported alongside, that exist because an earlier version of this
harness got the distinction wrong in both directions:

| Diagnostic | What it measures |
|---|---|
| instability | the declared views differed from the colliding partner's |
| fidelity | the model owner reported the model-card value it was actually given |
| `P(modelCardPublished ∣ b)` | whether the declared channel carries information about `b` |

**Instability is not leakage.** A permitted field can deviate for reasons unrelated to
`b`, and a run where it deviates equally often on both sides of `b` carries no
information about `b` no matter how unstable it is. Treating any pairwise difference as
though the hazard had become decidable manufactured a spurious 0.150 detection rate on an
early run. Whether the channel leaks is a property of the run's joint distribution, so it
is measured here and never folded into a per-episode detector call.

**Fidelity is what makes the conditionals interpretable.** The model owner's declared
field is constant across all four executions and stated to it as evidence, so there is
ground truth to score against. Equal conditionals under perfect fidelity are trivially
equal; equal conditionals under imperfect fidelity say the errors are indifferent to `b`.
A declared field the agent holds *no* evidence about is a field it must guess, and the
guess rate then registers as a property of the interface rather than of the agent — which
is why the harness states the value rather than merely declaring the field.

## Reporting regimes

Every trace carries a `regime`. The basic collision pilot uses `m0_truthful` only. The
strategic extension — added **only after** the basic pilot works — adds two more on the
same architecture:

| Regime | Meaning |
|---|---|
| `m0_truthful` | truthful reporting under the idealized mechanism `M₀` |
| `strategic_no_mechanism` | strategic reporting, no mechanism in place |
| `strategic_with_mechanism` | strategic reporting under the selected bounded mechanism |

That arm tests whether the bounded strategic model predicts the *direction* of evidence
loss and recovery. It does not establish equilibrium behaviour outside the instance.

Analyse one regime at a time with `--regime`, or all together by omitting it.

`strategic_with_mechanism` is refused by the runner rather than silently treated as
"strategic, mechanism absent": running it without the mechanism selected and reviewed
would produce the `strategic_no_mechanism` result under the wrong label, which is worse
than not running it.

### The pressure ladder

`strategic_no_mechanism` has four rungs, selected with `--prompt-variant`, and one
orthogonal axis, `--allow-withhold`. Every rung shares a single prompt template and
differs only in its opening and its incentive block, so a rung cannot drift from its
neighbours in any other respect — an ablation whose arms differ in more than the thing
being ablated measures nothing.

| rung | adds |
|---|---|
| `neutral` | two channels and a routing task |
| `incentivized` | measured on approvals; no audit, no verification, no penalty |
| `pivotal` | the decision rule, and that the other owner already reported restricted |
| `pivotal_persona` | a named identity with a contract renewal and colleagues' roles at stake |

The ordering is load-bearing. The point of a ladder is that the mechanism arm's job is to
**move the rung at which behaviour flips**, which is what `p·L ≥ G` is a condition about.
A single arm that produces misreporting says only that misreporting is producible, which
was never in doubt.

`--allow-withhold` offers `not_established` on the coalition channel — a report that
declines to assert and does not block. This is the third action in the declared model, alongside
truthful reporting and bounded falsification. The first strategic runs offered two, so
withholding could not be observed because it could not be performed. It is a separate
axis because it is a property of the mechanism's option set, not of the incentive, and it
is part of `episodeId` so the two axes cannot overwrite each other's traces.

Two things the ladder found that a single arm could not:

* the flip is at `pivotal`, and it is not about pressure — `incentivized` already states
  the payoff and produces zero falsification. `pivotal` adds only the fact that makes the
  payoff *derivable*;
* offering the honest exit eliminated falsification without being used, which is a result
  about the option set rather than about incentives.

Two rungs fall below the 0.80 conformance gate, and `analyze.py` exits non-zero on them.
That is the gate working: those configurations may not be cited as evidence about the
declared interface. The falsification measurement does not depend on conformance and
stands separately.

### What changes under a strategic regime

Each principal gains a second tool, `report_to_review`: a confidential channel to the
joint review carrying its restriction bit. This is `CoalitionInput` made concrete — the
model owner may report `b` here even though `b` is absent from its declared view.

`jointFlag` then reads those **reports** rather than the actual private fields. Under
`m0_truthful` it reads the fields, matching the Lean kernel's `observe`, which is
`q.joint (fun i => A.privateState i σ)`. That substitution is an assumption about
evidence production, not a theorem — `observe_truthful` is `rfl` and proves nothing — and
this is where it is tested.

Two things follow that are easy to get wrong, and were:

* **A missing report is not repaired.** From the coalition's side, evidence that never
  arrived and evidence that arrived wrong are the same production failure. Reconstructing
  what a principal *should* have said would measure the harness.
* **The regime, not the records, decides whether reports are expected.** If both
  principals fail to report, sniffing the records would fall back to ground truth and
  score a total production failure as perfect detection — the one case the regime exists
  to catch.

The confidential channel is deliberately **excluded** from the side-channel leak scan.
Reporting `b` there is its sanctioned use. Scanning it would score every correct report
as a violation and collapse the distinction the architecture rests on: evidence used
inside a coalition versus evidence published through the declared interface.

## Inclusion gate

An empirical claim leaves this repository only when **all** hold:

- [ ] traces, seeds, prompts/configuration, and analysis are released;
- [ ] the observation schema was fixed before scaling runs;
- [ ] leakage is measured rather than silently cleaned;
- [ ] all seven rates are reported;
- [ ] negative results are retained.

The 80% schema-conformance threshold in `analyze.py` is a **minimum inclusion
condition, not a success claim** — the script exits non-zero below it.

If the intended collision leaks, the detection-gap claim is dropped and the leak is
reported as evidence that the empirical interface requires redesign. The formal result
is unaffected either way.

## Layout

```text
harness/            episode runner, agent configuration, emitted-view enforcement
traces/             released episode traces, one JSON per episode
seeds/              seeds for every released episode
analyze.py          scripted analysis producing the seven rates
validate_traces.py  schema validation (CI; needs jsonschema)
```

Prompts and the declared-interface tool definition live in `harness/agents.py` and are
released with the traces by virtue of being in this repository.

## Running

Analysis needs nothing but a Python interpreter — that is deliberate, so anyone can
re-derive the published rates from the released traces without building an environment:

```console
python3 analyze.py                              # all regimes
python3 analyze.py --regime m0_truthful         # basic collision pilot only
python3 analyze.py --traces path/to/traces
```

Generating new traces needs an API key in `../.env` (see `../.env.example`):

```console
python3 -m harness.run_pilot --agent mock --repeats 3
python3 -m harness.run_pilot --agent openrouter --repeats 20 --concurrency 12
python3 -m harness.run_pilot --agent claude --repeats 20
```

Every turn is independent, so the unit of parallelism is the turn rather than the
episode. Episodes are assembled after all turns complete, so a parallel run and a
sequential run of the same arguments produce byte-identical traces — CI asserts this
against the mock backend rather than leaving it as a claim in a docstring.

Schema validation is the one thing that needs a dependency:

```console
pip install jsonschema && python3 validate_traces.py
```

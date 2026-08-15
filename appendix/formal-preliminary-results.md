# Appendix — formal preliminary results

> **Status.** Every signature below is reproduced from the pinned public Atlas release
> `v0.7.0` (`863166c`), and the downstream package compiles against that exact revision
> from a clean checkout. Proof bodies are not reproduced — only statements, definitions,
> and witnesses. The signatures are unchanged from the earlier `v0.5.1` (`ff4e7ce`) pin;
> what changed under `v0.7.0` is that their proofs now specialize the Atlas `Knowledge`
> knowability kernel rather than repeating the fibre argument here.

All declarations live in `AISafetyAtlas.Oversight.JointObservation`; the procurement
instance lives in `AISafetyAtlas.Examples.Oversight.JointObservation.Procurement`, and
the second bounded instance in
`AISafetyAtlas.Examples.Oversight.JointObservation.Portfolio`.
Universe annotations are elided where they do not disambiguate.

---

## 1. Coalition-indexed candidate input

An evidence architecture separates what a principal **holds** from what it **declares**.
The two are distinct types related only through `emit`:

```lean
public structure EvidenceArchitecture where
  Principal    : Type u
  Execution    : Type u
  PrivateField : Principal → Type v
  EmittedView  : Principal → Type v
  privateState : (i : Principal) → Execution → PrivateField i
  emit         : (i : Principal) → PrivateField i → EmittedView i

public abbrev Hazard (A : EvidenceArchitecture) : Type _ :=
  A.Execution → Bool
```

The hazard is `Bool`-valued deliberately: coverage is about a *decision* being
recoverable from an observation, not about a proposition being true.

The evidence available to a coalition `C` is exactly the private fields of its members:

```lean
public abbrev CoalitionInput
    (A : EvidenceArchitecture)
    (C : Finset A.Principal) : Type _ :=
  (i : {p // p ∈ C}) → A.PrivateField i.1

public structure CandidateObservation (A : EvidenceArchitecture) where
  coalition : Finset A.Principal
  Output    : Type w
  joint     : CoalitionInput A coalition → Output
```

**This is the load-bearing design decision of the kernel.** Access restriction is
enforced *by the type of `joint`*. A candidate for coalition `C` is a function whose
domain mentions only `C`'s private fields, so reading evidence outside `C` is a type
error, not a side condition that a later lemma has to discharge — and therefore not
something a proof, a refactor, or a downstream consumer can forget. `Output` is a field
rather than a parameter so that a family may mix candidates with heterogeneous output
types without ever requiring `DecidableEq (CandidateObservation A)`.

What a candidate reports in an execution is its value under truthful reporting:

```lean
@[expose] public def CandidateObservation.observe
    {A : EvidenceArchitecture} (q : CandidateObservation A)
    (σ : A.Execution) : q.Output :=
  q.joint (fun i => A.privateState i.1 σ)
```

Two constructors make emitted views load-bearing rather than incidental. Without them,
"local monitoring fails" would be a claim about arbitrary functions rather than about the
interface a system actually declares:

```lean
@[expose] public def localCandidate (A : EvidenceArchitecture) (i : A.Principal) :
    CandidateObservation A where
  coalition := {i}
  Output    := A.EmittedView i
  joint     := fun x => A.emit i (x ⟨i, Finset.mem_singleton_self i⟩)

@[expose] public def privateSingletonCandidate (A : EvidenceArchitecture) (i : A.Principal) :
    CandidateObservation A where
  coalition := {i}
  Output    := A.PrivateField i
  joint     := fun x => x ⟨i, Finset.mem_singleton_self i⟩

@[expose] public def emittedArchitectureCandidate (A : EvidenceArchitecture)
    [Fintype A.Principal] : CandidateObservation A where
  coalition := Finset.univ
  Output    := (i : A.Principal) → A.EmittedView i
  joint     := fun x i => A.emit i (x ⟨i, Finset.mem_univ i⟩)
```

`localCandidate i` sees only what `i` declares; `privateSingletonCandidate i` sees `i`'s
full private field and is strictly stronger. Keeping them apart is what stops a reader
from concluding that a positive joint result merely recovers information the interface
happened to hide: a failure of `privateSingletonCandidate i` says the hazard is
*relational*, not that the interface is lossy.

`emittedArchitectureCandidate` is the strongest observation the declared interface
supports before any architectural change — the grand coalition reporting the tuple of all
emitted views.

---

## 2. Coverage, collision, and refinement

```lean
@[expose] public def Covers (q : CandidateObservation A) (h : Hazard A) : Prop :=
  ∃ decideHazard : q.Output → Bool, ∀ σ, h σ = decideHazard (q.observe σ)
```

Coverage is **factorization**: one decision rule, uniform in the execution, through which
the hazard factors. It is deliberately *not* defined as "no collision exists". Quantifier
order is part of the freeze — swapping `∃` and `∀` would give a vacuous per-execution
statement, and defining `Covers` negatively would demote C1 from a theorem to a tautology.

```lean
public structure CollisionWitness (q : CandidateObservation A) (h : Hazard A) where
  left            : A.Execution
  right           : A.Execution
  sameObservation : q.observe left = q.observe right
  hazardDiffers   : h left ≠ h right

@[expose] public def Refines
    (q' : CandidateObservation A) (q : CandidateObservation A) : Prop :=
  ∃ f : q'.Output → q.Output, ∀ σ, q.observe σ = f (q'.observe σ)

@[expose] public def FamilyBlind (F : CandidateFamily A) (h : Hazard A) : Prop :=
  ∀ i : F.Index, ¬ Covers (F.candidate i) h
```

A collision witness is the negative certificate a checker returns: a downstream consumer
inspects *which* pair the current architecture cannot separate, rather than being told
that some pair exists. In `Refines q' q`, the refined — more informative — candidate is
the **first** argument, and it is the one that determines the other; the direction is part
of the freeze.

---

## 3. Generic theorem statements

### C1 — coverage/collision characterization

```lean
public theorem covers_iff_no_collision (q : CandidateObservation A) (h : Hazard A) :
    Covers q h ↔ ∀ σ τ, q.observe σ = q.observe τ → h σ = h τ

public theorem not_covers_of_collisionWitness
    (cw : CollisionWitness q h) : ¬ Covers q h

public theorem exists_collisionWitness_of_not_covers
    (hnc : ¬ Covers q h) : Nonempty (CollisionWitness q h)
```

This is the flagship statement: it licenses reading a collision witness as a genuine
informational obstruction rather than as the failure of one particular decision rule. The
forward direction is constructive; the reverse assembles the rule fibrewise and uses
classical choice.

### C2 — certified finite decision

```lean
public structure ExecutionEnum (A : EvidenceArchitecture) where
  toList   : List A.Execution
  complete : ∀ σ, σ ∈ toList

public inductive CoverageResult (q : CandidateObservation A) (h : Hazard A) where
  | covers    (proof : Covers q h)
  | collision (witness : CollisionWitness q h)

@[expose] public def decideCoverage
    (E : ExecutionEnum A) (q : CandidateObservation A) (h : Hazard A)
    [DecidableEq q.Output] : CoverageResult q h

public theorem CoverageResult.covered_eq_true_iff
    (r : CoverageResult q h) : r.covered = true ↔ Covers q h

public theorem decideCoverage_covered_iff
    (E : ExecutionEnum A) (q : CandidateObservation A) (h : Hazard A)
    [DecidableEq q.Output] :
    (decideCoverage E q h).covered = true ↔ Covers q h

public instance decidableCovers [Fintype A.Execution]
    (q : CandidateObservation A) (h : Hazard A) [DecidableEq q.Output] :
    Decidable (Covers q h)
```

Three points a reader can check quickly.

*The result type carries evidence in both branches.* `CoverageResult` is a dependent type,
not a `Bool`. A consumer therefore never trusts the checker; it inspects what the checker
returned. `covered_eq_true_iff` holds for *any* result value, not just the checker's — the
`covers` branch hands over the proof directly, and the `collision` branch is refuted
through C1. That is the specification connecting the executable result back to `Covers`.

*Finiteness is supplied as data.* `ExecutionEnum` is an explicit list plus a completeness
proof, rather than a `Fintype` instance. A `Fintype` gives decidability, but selecting a
concrete witness to return requires a canonical order to search, which `Fintype` alone does
not provide. The narrow claim is only this: `ExecutionEnum` is what `decideCoverage` runs
on. It is not a claim that finite search is impossible from `Fintype` in general —
`decidableCovers` decides the proposition from `Fintype` with no enumeration at all,
precisely because deciding a proposition never has to produce a witness.

*The trusted path is the kernel-checked term.* `decideCoverage` is executable and reduces
under `decide`. There is no `native_decide` and no `@[implemented_by]`.

### C3 — repair boundary

```lean
@[expose] public def CandidateObservation.postprocess
    (q : CandidateObservation A) {β : Type w'} (g : q.Output → β) : CandidateObservation A

public theorem postprocess_cannot_repair_collision
    (hnc : ¬ Covers q h) {β : Type w'} (g : q.Output → β) :
    ¬ Covers (q.postprocess g) h

public def CollisionWitness.postprocess
    (cw : CollisionWitness q h) {β : Type w'} (g : q.Output → β) :
    CollisionWitness (q.postprocess g) h

public theorem covers_of_refines (hr : Refines q' q) (hc : Covers q h) : Covers q' h
```

`postprocess` keeps the coalition and the computation fixed and applies one further
function to the output — computing harder over the same evidence. The theorem says that
cannot recover what emission discarded, and its proof is the constructive contrapositive:
a decision rule on the post-processed output composes with `g` to give one on the original.
`CollisionWitness.postprocess` is `def`, not `theorem`: the same colliding pair is
transported as data, so the consumer keeps a concrete witness rather than an existence
claim.

`covers_of_refines` is the positive half of the boundary. Repair by widening evidence
access is monotone — it cannot lose a guarantee already established.

### C4 — mechanism boundary

```lean
public theorem observe_truthful (q : CandidateObservation A) (σ : A.Execution) :
    q.observe σ = q.joint (fun i => A.privateState i.1 σ) := rfl
```

Every coverage result above is a statement about *informational* coverage under the fixed
truthful mechanism `M0`: `observe` feeds each candidate the principals' actual private
fields. This lemma is `rfl` and proves nothing new. It exists so that the model boundary is
explicit at the point of use rather than inferred from prose — nothing in the kernel shows
that a coalition would report truthfully, that forming it is permissible, or that a given
joint predicate is minimal among alternatives.

---

## 4. Procurement instance

A minimal formal reference example: two principals, four executions, two private bits.

```lean
public inductive Principal
  | dataOwner | modelOwner
  deriving DecidableEq, Fintype

public inductive Exec
  | sigma00 | sigma10 | sigma01 | sigma11
  deriving DecidableEq, Fintype

@[expose] public def PrivateField : Principal → Type
  | .dataOwner  => Bool
  | .modelOwner => Bool

@[expose] public def EmittedView : Principal → Type
  | .dataOwner  => Bool     -- dataset restriction IS declared
  | .modelOwner => Unit     -- checkpoint access policy is NOT

@[expose] public def emit : (i : Principal) → PrivateField i → EmittedView i
  | .dataOwner, b => b
  | .modelOwner, _ => ()

@[expose] public def hazard : Hazard arch := fun σ =>
  datasetRestricted σ && checkpointRestricted σ
```

Writing `σ_ab` for the execution with dataset bit `a` and checkpoint bit `b`, the hazard
`h = a ∧ b` holds only at `σ11`. The emission asymmetry is the point: the declared
interface is genuinely informative — it discloses `a` exactly — and still insufficient.

The four candidates:

```lean
@[expose] public def qC       := privateSingletonCandidate arch .dataOwner
@[expose] public def qD       := privateSingletonCandidate arch .modelOwner
@[expose] public def qEmitted := emittedArchitectureCandidate arch

@[expose] public def qCD : CandidateObservation arch where
  coalition := Finset.univ
  Output    := Bool
  joint     := fun x =>
    x ⟨.dataOwner, Finset.mem_univ _⟩ && x ⟨.modelOwner, Finset.mem_univ _⟩

@[expose] public def execEnum : ExecutionEnum arch where
  toList   := [.sigma00, .sigma10, .sigma01, .sigma11]
  complete := by decide
```

`qC` and `qD` use `privateSingletonCandidate`, not `localCandidate`: each is given
**unrestricted access to its own private evidence**, including the model owner's
checkpoint bit `b` which never appears in any emitted view. Their failure therefore says
the hazard is relational, not that the interface is lossy. The interface claim is carried
separately by `localFamily_blind` and `not_covers_qEmitted`.

| Claim | Statement | Witness |
|---|---|---|
| Data owner alone insufficient | `¬ Covers qC hazard` | `dataCollision : (σ10, σ11)` |
| Model owner alone insufficient | `¬ Covers qD hazard` | `modelCollision : (σ01, σ11)` |
| No local monitor covers | `FamilyBlind (localFamily arch) hazard` | `(σ10, σ11)` at `dataOwner`; `(σ01, σ11)` at `modelOwner` |
| Complete emitted interface insufficient | `¬ Covers qEmitted hazard` | `emittedCollision : (σ10, σ11)` |
| No computation over it repairs this | `∀ {β} (g : qEmitted.Output → β), ¬ Covers (qEmitted.postprocess g) hazard` | via C3 from `emittedCollision` |
| Permitted joint predicate sufficient | `Covers qCD hazard` | decision rule `id` |
| Checker agrees, by execution | `(decideCoverage execEnum qCD hazard).covered = true` | `by decide` |
| Checker agrees, negative branch | `(decideCoverage execEnum qEmitted hazard).covered = false` | `by decide` |

Each witness is checked, not asserted. `emittedCollision.sameObservation` is
`by funext i; cases i <;> rfl`: the two emitted tuples at `σ10` and `σ11` are equal
componentwise, because the data owner emits `true` in both and the model owner emits `()`
in both. `hazardDiffers` is `by decide`, since `h σ10 = false` and `h σ11 = true`.

Two entries above are of different kinds and should be read as such. `not_covers_qEmitted`
is one collision at one candidate. `not_covers_postprocess_qEmitted` is the architectural
conclusion: *any* computation over the complete existing emitted interface fails, so repair
requires changing evidence access rather than adding analysis. The last two rows are
distinct evidence again — the certified checker *reduces* to the expected branch on this
instance, so the executable path and the classical path agree on a case that can be
inspected by hand.

`covers_qCD` is witnessed by the identity decision rule: `qCD` already reports `a && b`,
which is the hazard. The checkpoint bit is used and never emitted — it stays inside the
coalition input, which is exactly what the type of `joint` enforces.

See `figures/observation-collision.svg` for a plain-language rendering: it names the two
executions that collide (`sigma10` and `sigma11`), shows that every publicly published
document is identical across them, and contrasts that with the single bit the permitted
joint predicate releases.

---

## 5. Bounded hazard-family portfolio target

The local candidate commit adds the solver-independent target that the original
single-candidate kernel lacked:

    public structure HazardFamily (A : EvidenceArchitecture) where
      Index  : Type
      hazard : Index → Hazard A

    public abbrev Portfolio (F : CandidateFamily A) := Finset F.Index

    @[expose] public def PortfolioCovers
        (F : CandidateFamily A) (H : HazardFamily A) (K : Portfolio F) : Prop :=
      ∀ j, ∃ i ∈ K, Covers (F.candidate i) (H.hazard j)

    @[expose] public def PortfolioIndistinguishable
        (F : CandidateFamily A) (K : Portfolio F) (x y : A.Execution) : Prop :=
      ∀ i, i ∈ K → (F.candidate i).observe x = (F.candidate i).observe y

    public theorem portfolioCovers_implies_hazardEquivalent
        (hCover : PortfolioCovers F H K)
        (hSame : PortfolioIndistinguishable F K x y) :
        ∀ j, H.hazard j x = H.hazard j y

The theorem is derived from per-candidate coverage: for each hazard it uses the explicit
selected candidate and decision rule supplied by `PortfolioCovers`. It does not grant a
free fusion centre for several individually insufficient outputs, and no converse is
claimed. `HazardFamily` and `CandidateFamily` remain general indexed structures; finite
instances are required only where bounded enumeration actually uses them.

The same module separates inclusion-minimality from minimum declared cost:

    @[expose] public def InclusionMinimalCovering ...
    @[expose] public def PortfolioCost ...
    @[expose] public def CostOptimalCovering ...

    public theorem inclusionMinimal_of_costOptimal
        (hPositive : ∀ i, 0 < cost i)
        (hOptimal : CostOptimalCovering F H cost K) :
        InclusionMinimalCovering F H K

A second checked architecture has principals C, D, E, all eight assignments to private
bits a, b, c, and hazards h_CD = a AND b and h_DE = b XOR c. Its supplied candidates and
declared costs are:

| Candidate | Coalition | Output | Cost |
|---|---|---|---:|
| `qCD` | `{C,D}` | `a AND b` | 3 |
| `qDE` | `{D,E}` | `b XOR c` | 3 |
| `qCDE` | `{C,D,E}` | `(a,b,c)` | 7 |

Lean checks that `qCD` covers only h_CD, `qDE` covers only h_DE, and `qCDE`
covers both. Consequently:

| Claim | Checked declaration |
|---|---|
| Narrow portfolio `{qCD,qDE}` covers both hazards | `kNarrow_covers` |
| Broad singleton `{qCDE}` covers both hazards | `kBroad_covers` |
| Agreement on either selected portfolio entails agreement on both hazards | `kNarrow_hazardEquivalent`, `kBroad_hazardEquivalent` |
| Both portfolios are inclusion-minimal | `kNarrow_inclusionMinimal`, `kBroad_inclusionMinimal` |
| Declared costs are 6 and 7 | `kNarrow_cost`, `kBroad_cost` |
| Only the narrow portfolio is cost-optimal | `kNarrow_costOptimal`, `kBroad_not_costOptimal` |

This validates a bounded output type and ordering, not a synthesis algorithm. Candidates
and costs are supplied; nothing generates predicates, searches mechanisms, validates the
cost model, or proves optimality outside this declared family.

---

## 6. Strict trust and axiom audit

The audit is a kernel question, not a textual one. `scripts/strict_trust.sh` greps for
`sorry`, `admit`, `sorryAx`, project-local `axiom`, `native_decide`, and
`@[implemented_by]`; it is cheap and catches the mistake. `scripts/check_axioms.py` runs
`#print axioms` on every `public theorem` and is what catches the deception, because a
grep cannot see through an import and this can.

Current state:

| Check | Result |
|---|---|
| Atlas release `v0.7.0` (`863166c`), facade closure imported here (`AISafetyAtlas.Oversight.JointObservation`, 9 modules), every `public theorem`/`lemma` | 33 declarations, axiom set `{propext, Classical.choice, Quot.sound}` |
| Downstream consumer at the committed public pin, `public theorem` surface | 36 declarations, same axiom set |
| Textual strict-trust gate, both packages | clean |
| Downstream `lake build` against the public pin | 765 jobs |

Rows two through four run in this repository's CI on every push, against the same public
revision a reader would fetch, so they are regenerated rather than reported. Row one is an
audit of the pinned Atlas revision, measured against that revision; the Atlas's own CI
audits its full public surface upstream.

## 7. Commits

| Artifact | Commit |
|---|---|
| Atlas kernel, procurement example, and bounded portfolio target | release `v0.7.0` — `863166c2193d73788073ace06375ce86e0b12e33` |
| Atlas archived record | concept DOI [10.5281/zenodo.21483033](https://doi.org/10.5281/zenodo.21483033) (all versions) |
| Earlier pin, preserved in this repository's history at `8804763` | Atlas `v0.5.1` — `ff4e7ce90426e0117355c4521eed1a90796c555b`, DOI [10.5281/zenodo.21849854](https://doi.org/10.5281/zenodo.21849854) |
| Downstream Lean consumer | this repository, pinned to the current revision in [`formal/lakefile.toml`](../formal/lakefile.toml) |

The pin is a real `[[require]]` with a 40-character `rev` against a repository anyone can
fetch, resolved by lake into a 765-job build. That is what makes the kernel *demonstrably*
consumable by an external package rather than asserted to be: reproducibility is the whole
content of a commit citation, and a build only the authors can run is a claim about the
authors. The committed pin and cold-checkout build are the evidence for this claim.

## 8. Limitations

- Results concern **informational coverage** under a fixed idealized truthful mechanism
  `M0`. They do not establish strategic incentive compatibility, equilibrium reporting,
  or robustness to arbitrary deception.
- The certified decision is a **finite** procedure; it assumes an explicit enumeration of
  executions and decidable equality of the candidate output.
- The procurement instance is a minimal formal reference example, not a general
  procurement model.
- The portfolio result is one additional hand-built eight-execution architecture. It
  establishes neither broad architectural generality nor automatic synthesis.
- The empirical pilot, where included, is a falsification and interface-integrity check.
  It does not validate the general synthesis method.

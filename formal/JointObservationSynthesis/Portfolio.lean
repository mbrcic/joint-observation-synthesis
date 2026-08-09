module

public import AISafetyAtlas.Oversight.JointObservation
public import Mathlib.Tactic.DeriveFintype
public import Mathlib.Data.Finset.Powerset
public import Mathlib.Algebra.BigOperators.Group.Finset.Defs

/-!
# The three-principal portfolio architecture, instantiated downstream

This file builds the project's three-principal coalition-choice architecture from the
Atlas kernel and nothing else, and then proves one thing the Atlas copy does not.

## Why this instance is built here rather than imported

The same reasoning as in `Procurement.lean`. The Atlas carries its own copy of this
architecture under `AISafetyAtlas/Examples/Oversight/JointObservation/Portfolio.lean`,
and that module is importable. Rebuilding it here from `EvidenceArchitecture`,
`CandidateFamily`, `HazardFamily`, and `Covers` shows that the *interface* carries the
work, which re-exporting a bundled example would not.

The two copies have different jobs. The Atlas copy is a regression test guarding the
portfolio target against silent interface drift and stays minimal. This copy is the
project's model and is free to grow — and the last section below is the first place it
does.

## The model

Principals `C`, `D`, `E` privately hold bits `a`, `b`, `c`. Two hazards:

```text
h_CD (sigma_abc) = a && b
h_DE (sigma_abc) = b xor c
```

Their cheaper narrow observations use **different overlapping coalitions** — `D` is
indispensable to both — which is the structure no two-principal model can express.

| candidate | coalition | reports | declared cost |
|---|---|---|---:|
| `qCD` | `{C,D}` | `a && b` | 3 |
| `qDE` | `{D,E}` | `b xor c` | 3 |
| `qCDE` | `{C,D,E}` | `(a,b,c)` | 7 |

Declared cost is `2 * (coalition size - 1) + output bits`: an auditable proxy for
cross-principal coordination plus disclosure, not a universal scalarization.

## What this file adds

`kNarrow = {qCD, qDE}` is cost-optimal at 6; `kBroad = {qCDE}` costs 7 and is not. Both
cover, and both are inclusion-minimal. That much mirrors the upstream regression example.

The final section states the separation the project needs and the kernel does not
supply: **coverage and attribution are different requirements, and the cost-optimal
cover fails the second one.** `kNarrow` cannot see a deviation confined to principal
`C`, while the strictly more expensive `kBroad` can. Coverage is preserved throughout —
`portfolioCovers_implies_hazardEquivalent` still applies — because the undetected
deviation moves no hazard. That is exactly the point: keeping every declared hazard
decidable does not keep the deviating principal identifiable.

Everything here holds under the fixed truthful mechanism `M0`. Nothing below is a
strategic, incentive, or mechanism claim, and nothing generates a candidate or searches
a library.
-/

namespace JointObservationSynthesis.Portfolio

open AISafetyAtlas.Oversight.JointObservation

/-! ## The three-principal, eight-execution architecture -/

/-- The three evidence-owning principals. -/
public inductive Principal
  /-- Holds bit `a`. -/
  | c
  /-- Holds bit `b`; indispensable to both hazards. -/
  | d
  /-- Holds bit `c`. -/
  | e
  deriving DecidableEq, Fintype

/-- Executions indexed by the private bits `(a,b,c)`. -/
public inductive Exec
  | sigma000
  | sigma001
  | sigma010
  | sigma011
  | sigma100
  | sigma101
  | sigma110
  | sigma111
  deriving DecidableEq, Fintype

/-- Principal `C`'s private bit. -/
@[expose] public def bitC : Exec → Bool
  | .sigma000 | .sigma001 | .sigma010 | .sigma011 => false
  | .sigma100 | .sigma101 | .sigma110 | .sigma111 => true

/-- Principal `D`'s private bit. -/
@[expose] public def bitD : Exec → Bool
  | .sigma000 | .sigma001 | .sigma100 | .sigma101 => false
  | .sigma010 | .sigma011 | .sigma110 | .sigma111 => true

/-- Principal `E`'s private bit. -/
@[expose] public def bitE : Exec → Bool
  | .sigma000 | .sigma010 | .sigma100 | .sigma110 => false
  | .sigma001 | .sigma011 | .sigma101 | .sigma111 => true

/-- Each principal privately holds one Boolean. -/
@[expose] public def PrivateField : Principal → Type
  | .c | .d | .e => Bool

/-- Nothing is declared: the emitted interface is empty for every principal. -/
@[expose] public def EmittedView : Principal → Type
  | .c | .d | .e => Unit

/-- The evidence each principal actually holds in an execution. -/
@[expose] public def privateState : (i : Principal) → Exec → PrivateField i
  | .c, σ => bitC σ
  | .d, σ => bitD σ
  | .e, σ => bitE σ

/-- The declared interface projection: totally lossy here. -/
@[expose] public def emit : (i : Principal) → PrivateField i → EmittedView i
  | .c, _ => ()
  | .d, _ => ()
  | .e, _ => ()

/-- The three-principal evidence architecture. -/
@[expose] public def arch : EvidenceArchitecture where
  Principal := Principal
  Execution := Exec
  PrivateField := PrivateField
  EmittedView := EmittedView
  privateState := privateState
  emit := emit

/-! ### Executability instances -/

public instance : Fintype arch.Principal := inferInstanceAs (Fintype Principal)
public instance : DecidableEq arch.Principal := inferInstanceAs (DecidableEq Principal)
public instance : Fintype arch.Execution := inferInstanceAs (Fintype Exec)
public instance : DecidableEq arch.Execution := inferInstanceAs (DecidableEq Exec)

public instance instDecidableEqPrivateField :
    (i : Principal) → DecidableEq (PrivateField i)
  | .c | .d | .e => inferInstanceAs (DecidableEq Bool)

/-! ## Hazards -/

/-- The `C-D` conjunction hazard. -/
@[expose] public def hCD : Hazard arch := fun σ => bitC σ && bitD σ

/-- The `D-E` inconsistency hazard. -/
@[expose] public def hDE : Hazard arch := fun σ => Bool.xor (bitD σ) (bitE σ)

/-- Index of the declared hazard family. -/
public inductive HazardIx
  | cd
  | de
  deriving DecidableEq, Fintype

/-- The declared hazard family. -/
@[expose] public def hazards : HazardFamily arch where
  Index := HazardIx
  hazard
    | .cd => hCD
    | .de => hDE

/-! ## Coalition-indexed candidates -/

/-- The narrow `C-D` observation, computed only from `C` and `D` evidence. -/
@[expose] public def qCD : CandidateObservation arch where
  coalition := {.c, .d}
  Output := Bool
  joint := fun x => x ⟨.c, by simp⟩ && x ⟨.d, by simp⟩

/-- The narrow `D-E` observation, computed only from `D` and `E` evidence. -/
@[expose] public def qDE : CandidateObservation arch where
  coalition := {.d, .e}
  Output := Bool
  joint := fun x => Bool.xor (x ⟨.d, by simp⟩) (x ⟨.e, by simp⟩)

/-- The broad grand-coalition observation, disclosing all three private bits. -/
@[expose] public def qCDE : CandidateObservation arch where
  coalition := Finset.univ
  Output := Bool × Bool × Bool
  joint := fun x =>
    (x ⟨.c, Finset.mem_univ _⟩,
      x ⟨.d, Finset.mem_univ _⟩,
      x ⟨.e, Finset.mem_univ _⟩)

/-- Index of the declared candidate family. -/
public inductive CandIx
  | cd
  | de
  | cde
  deriving DecidableEq, Fintype

/-- The declared candidate family. -/
@[expose] public def candidates : CandidateFamily arch where
  Index := CandIx
  candidate
    | .cd => qCD
    | .de => qDE
    | .cde => qCDE

public instance : DecidableEq candidates.Index := inferInstanceAs (DecidableEq CandIx)
public instance : Fintype candidates.Index := inferInstanceAs (Fintype CandIx)

/-! ## Declared coordination-plus-disclosure cost -/

/-- Number of Boolean fields released by each supplied candidate. -/
@[expose] public def outputBits : CandIx → Nat
  | .cd | .de => 1
  | .cde => 3

/-- Declared instance cost `2 * (coalition size - 1) + output bits`. -/
@[expose] public def cost (i : CandIx) : Nat :=
  2 * ((candidates.candidate i).coalition.card - 1) + outputBits i

public theorem qCD_cost : cost .cd = 3 := by decide
public theorem qDE_cost : cost .de = 3 := by decide
public theorem qCDE_cost : cost .cde = 7 := by decide

/-! ## Which candidate covers which hazard -/

public theorem qCD_covers_hCD : Covers qCD hCD :=
  ⟨id, by intro σ; cases σ <;> rfl⟩

public theorem qCD_not_covers_hDE : ¬ Covers qCD hDE :=
  not_covers_of_collisionWitness
    { left := .sigma000, right := .sigma001,
      sameObservation := rfl, hazardDiffers := by decide }

public theorem qDE_covers_hDE : Covers qDE hDE :=
  ⟨id, by intro σ; cases σ <;> rfl⟩

public theorem qDE_not_covers_hCD : ¬ Covers qDE hCD :=
  not_covers_of_collisionWitness
    { left := .sigma000, right := .sigma111,
      sameObservation := rfl, hazardDiffers := by decide }

public theorem qCDE_covers_hCD : Covers qCDE hCD :=
  ⟨fun o => o.1 && o.2.1, by intro σ; cases σ <;> rfl⟩

public theorem qCDE_covers_hDE : Covers qCDE hDE :=
  ⟨fun o => Bool.xor o.2.1 o.2.2, by intro σ; cases σ <;> rfl⟩

/-! ## The two covering portfolios -/

/-- Two narrow observations over different overlapping coalitions. -/
@[expose] public def kNarrow : Portfolio candidates := {.cd, .de}

/-- One broad grand-coalition observation. -/
@[expose] public def kBroad : Portfolio candidates := {.cde}

public theorem kNarrow_covers : PortfolioCovers candidates hazards kNarrow := by
  intro j
  cases j with
  | cd => exact ⟨.cd, by decide, qCD_covers_hCD⟩
  | de => exact ⟨.de, by decide, qDE_covers_hDE⟩

public theorem kBroad_covers : PortfolioCovers candidates hazards kBroad := by
  intro j
  cases j with
  | cd => exact ⟨.cde, by decide, qCDE_covers_hCD⟩
  | de => exact ⟨.cde, by decide, qCDE_covers_hDE⟩

/-- The generic consequence instantiated for the narrow portfolio. -/
public theorem kNarrow_hazardEquivalent
    {x y : arch.Execution}
    (hSame : PortfolioIndistinguishable candidates kNarrow x y) :
    ∀ j : hazards.Index, hazards.hazard j x = hazards.hazard j y :=
  portfolioCovers_implies_hazardEquivalent kNarrow_covers hSame

/-! ## Reducing portfolio coverage to finite membership -/

public theorem portfolioCovers_iff (K : Portfolio candidates) :
    PortfolioCovers candidates hazards K ↔
      ((CandIx.cd ∈ K ∨ CandIx.cde ∈ K) ∧ (CandIx.de ∈ K ∨ CandIx.cde ∈ K)) := by
  constructor
  · intro h
    constructor
    · obtain ⟨i, hi, hcov⟩ := h .cd
      cases i with
      | cd => exact Or.inl hi
      | de => exact absurd hcov qDE_not_covers_hCD
      | cde => exact Or.inr hi
    · obtain ⟨i, hi, hcov⟩ := h .de
      cases i with
      | cd => exact absurd hcov qCD_not_covers_hDE
      | de => exact Or.inl hi
      | cde => exact Or.inr hi
  · rintro ⟨hcd, hde⟩ j
    cases j with
    | cd =>
        rcases hcd with h | h
        · exact ⟨.cd, h, qCD_covers_hCD⟩
        · exact ⟨.cde, h, qCDE_covers_hCD⟩
    | de =>
        rcases hde with h | h
        · exact ⟨.de, h, qDE_covers_hDE⟩
        · exact ⟨.cde, h, qCDE_covers_hDE⟩

/-! ## Inclusion-minimality and declared cost-optimality -/

public theorem narrow_subsets_fail :
    ∀ K' ∈ ({CandIx.cd, CandIx.de} : Finset CandIx).powerset,
      K' ≠ ({CandIx.cd, CandIx.de} : Finset CandIx) →
        ¬ ((CandIx.cd ∈ K' ∨ CandIx.cde ∈ K') ∧
          (CandIx.de ∈ K' ∨ CandIx.cde ∈ K')) := by
  decide

public theorem kNarrow_inclusionMinimal :
    InclusionMinimalCovering candidates hazards kNarrow := by
  refine ⟨kNarrow_covers, fun K' hsub hcov => ?_⟩
  exact narrow_subsets_fail K' (Finset.mem_powerset.mpr hsub.1) (ne_of_lt hsub)
    ((portfolioCovers_iff K').mp hcov)

public theorem kNarrow_cost : PortfolioCost candidates cost kNarrow = 6 := by decide
public theorem kBroad_cost : PortfolioCost candidates cost kBroad = 7 := by decide

public theorem every_cover_costs_at_least_six :
    ∀ K' ∈ (Finset.univ : Finset CandIx).powerset,
      ((CandIx.cd ∈ K' ∨ CandIx.cde ∈ K') ∧
        (CandIx.de ∈ K' ∨ CandIx.cde ∈ K')) →
        6 ≤ ∑ i ∈ K', cost i := by
  decide

public theorem kNarrow_costOptimal :
    CostOptimalCovering candidates hazards cost kNarrow := by
  refine ⟨kNarrow_covers, fun K' hcov => ?_⟩
  rw [kNarrow_cost]
  exact every_cover_costs_at_least_six K'
    (Finset.mem_powerset.mpr (Finset.subset_univ K')) ((portfolioCovers_iff K').mp hcov)

public theorem kBroad_not_costOptimal :
    ¬ CostOptimalCovering candidates hazards cost kBroad := by
  intro h
  have hle := h.2 kNarrow kNarrow_covers
  rw [kBroad_cost, kNarrow_cost] at hle
  omega

/-!
## Coverage is not attribution

Everything above concerns *hazard* distinguishability. Attribution asks a different
question: given that something went wrong, which principal's evidence was different?

The two requirements come apart, and they come apart in the direction that matters — the
cost-optimal cover is the one that fails.
-/

/-- Two executions differ in principal `i`'s private evidence and nowhere else. -/
@[expose] public def DeviationAt (i : arch.Principal) (x y : arch.Execution) : Prop :=
  arch.privateState i x ≠ arch.privateState i y ∧
    ∀ j, j ≠ i → arch.privateState j x = arch.privateState j y

/--
The portfolio **attributes deviations**: no single-principal deviation is invisible to
every selected candidate.

Stated as the contrapositive of indistinguishability, so it uses the same kernel notion
that `portfolioCovers_implies_hazardEquivalent` consumes and introduces no new machinery.
-/
@[expose] public def AttributesDeviations
    (F : CandidateFamily arch) (K : Portfolio F) : Prop :=
  ∀ (i : arch.Principal) (x y : arch.Execution),
    DeviationAt i x y → ¬ PortfolioIndistinguishable F K x y

/-- `sigma000` and `sigma100` differ exactly in principal `C`'s private bit. -/
public theorem deviation_C_000_100 : DeviationAt .c .sigma000 .sigma100 := by
  refine ⟨?_, ?_⟩
  · show bitC .sigma000 ≠ bitC .sigma100
    decide
  · intro j hj
    cases j with
    | c => exact absurd rfl hj
    | d => rfl
    | e => rfl

/-- The cost-optimal narrow portfolio cannot see that deviation. -/
public theorem kNarrow_blind_on_C :
    PortfolioIndistinguishable candidates kNarrow .sigma000 .sigma100 := by
  intro i hi
  cases i with
  | cd => rfl
  | de => rfl
  | cde => exact absurd hi (by decide)

/--
**The cost-optimal cover is attribution-blind.**

`kNarrow` covers both declared hazards, is inclusion-minimal, and is cost-optimal at 6 —
and still cannot tell that principal `C` deviated.
-/
public theorem kNarrow_not_attributes : ¬ AttributesDeviations candidates kNarrow :=
  fun h => h .c .sigma000 .sigma100 deviation_C_000_100 kNarrow_blind_on_C

/-- The strictly more expensive broad portfolio does see it. -/
public theorem kBroad_sees_C :
    ¬ PortfolioIndistinguishable candidates kBroad .sigma000 .sigma100 := by
  intro h
  have := h .cde (by decide)
  exact absurd (congrArg (·.1) this) (by decide)

/--
**Paying more buys attribution, and coverage alone does not.**

`kBroad` attributes *every* single-principal deviation, because it discloses each
principal's bit separately. It costs 7 against the cost-optimal 6 — so under this
declared cost model, attribution is exactly what the extra unit buys.
-/
public theorem kBroad_attributes : AttributesDeviations candidates kBroad := by
  intro i x y hdev hIndist
  have h := hIndist .cde (by decide)
  refine hdev.1 ?_
  cases i with
  | c => exact congrArg (·.1) h
  | d => exact congrArg (·.2.1) h
  | e => exact congrArg (·.2.2) h

/--
Coverage survives the blind spot.

The deviation `kNarrow` misses moves neither declared hazard, so
`portfolioCovers_implies_hazardEquivalent` is not violated — it is simply answering a
different question. Attribution needs separation on *deviating subsets*; coverage needs
it only on hazard classes.
-/
public theorem hazards_agree_where_narrow_is_blind :
    ∀ j : hazards.Index, hazards.hazard j .sigma000 = hazards.hazard j .sigma100 :=
  kNarrow_hazardEquivalent kNarrow_blind_on_C

end JointObservationSynthesis.Portfolio

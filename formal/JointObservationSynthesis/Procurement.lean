module

public import AISafetyAtlas.Oversight.JointObservation
public import Mathlib.Tactic.DeriveFintype
public import Mathlib.Data.Fintype.Pi

/-!
# The procurement architecture, instantiated downstream

This file builds the project's reference architecture from the Atlas kernel and
nothing else. It imports only the public facade `AISafetyAtlas`.

## Why this instance is built here rather than imported

The Atlas carries its own copy of this architecture under
`AISafetyAtlas/Examples/Oversight/JointObservation/Procurement.lean`, and that module
*is* importable by a consumer. Building the instance here instead is a deliberate
choice, not a packaging constraint.

The reason is what the downstream package is meant to demonstrate. A consumer that
imported the Atlas example and renamed its results would show only that a bundled
example can be re-exported. A consumer that builds its own model out of
`EvidenceArchitecture`, `CandidateObservation`, and `Covers`, and proves its own
results with kernel lemmas, shows that the *interface* carries the work. That is the
claim worth making.

The two copies then have different jobs. The Atlas copy is a regression test guarding
the kernel against silent interface drift; it stays minimal. This copy is the
project's model and is free to grow with the project.

What is **not** duplicated is anything semantic. Every definition below is built from
Atlas vocabulary, and no kernel definition is restated.

## The model

Two principals. The data owner knows whether the training dataset is access
restricted; the model owner knows whether the checkpoint is. Neither restriction is a
hazard alone. The hazard is the conjunction, which leaves the deployed system
externally unauditable.

| Execution | Dataset field | Checkpoint field | Hazard |
|---|---|---|---|
| `sigma00` | unrestricted | public | safe |
| `sigma10` | restricted | public | safe |
| `sigma01` | unrestricted | restricted | safe |
| `sigma11` | restricted | restricted | **hazardous** |

Dataset restriction is disclosed; checkpoint access policy is not. The declared
interface is therefore genuinely informative and still insufficient.
-/

namespace JointObservationSynthesis.Procurement

open AISafetyAtlas.Oversight.JointObservation

/-! ## The four-state universe -/

/-- The two principals holding evidence about the procurement. -/
public inductive Principal
  /-- Holds the training dataset and its access policy. -/
  | dataOwner
  /-- Holds the model checkpoint and its access policy. -/
  | modelOwner
  deriving DecidableEq, Fintype

/-- The four executions, indexed by the two relational bits. -/
public inductive Exec
  /-- Unrestricted dataset, public checkpoint. -/
  | sigma00
  /-- Restricted dataset, public checkpoint. -/
  | sigma10
  /-- Unrestricted dataset, restricted checkpoint. -/
  | sigma01
  /-- Restricted dataset, restricted checkpoint. -/
  | sigma11
  deriving DecidableEq, Fintype

/-- Whether the training dataset is access restricted in this execution. -/
@[expose] public def datasetRestricted : Exec → Bool
  | .sigma00 => false
  | .sigma10 => true
  | .sigma01 => false
  | .sigma11 => true

/-- Whether the model checkpoint is access restricted in this execution. -/
@[expose] public def checkpointRestricted : Exec → Bool
  | .sigma00 => false
  | .sigma10 => false
  | .sigma01 => true
  | .sigma11 => true

/-- Each principal privately holds its own restriction bit. -/
@[expose] public def PrivateField : Principal → Type
  | .dataOwner => Bool
  | .modelOwner => Bool

/-- The declared interface. Dataset restriction is disclosed; checkpoint access
policy is not part of what the model owner declares. -/
@[expose] public def EmittedView : Principal → Type
  | .dataOwner => Bool
  | .modelOwner => Unit

/-- The evidence each principal actually holds in an execution. -/
@[expose] public def privateState : (i : Principal) → Exec → PrivateField i
  | .dataOwner, σ => datasetRestricted σ
  | .modelOwner, σ => checkpointRestricted σ

/-- The declared interface projection: lossy for the model owner. -/
@[expose] public def emit : (i : Principal) → PrivateField i → EmittedView i
  | .dataOwner, b => b
  | .modelOwner, _ => ()

/-- The procurement evidence architecture. -/
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

public instance instDecidableEqEmittedView :
    (i : Principal) → DecidableEq (EmittedView i)
  | .dataOwner => inferInstanceAs (DecidableEq Bool)
  | .modelOwner => inferInstanceAs (DecidableEq Unit)

/-- The relational hazard: restricted dataset **and** restricted checkpoint. -/
@[expose] public def hazard : Hazard arch := fun σ =>
  datasetRestricted σ && checkpointRestricted σ

/-- The four executions, listed. This is the finiteness the checker runs on. -/
@[expose] public def execEnum : ExecutionEnum arch where
  toList := [.sigma00, .sigma10, .sigma01, .sigma11]
  complete := by decide

/-! ## The candidates -/

/-- The data owner acting alone, with unrestricted access to its own private
evidence — strictly stronger than its declared view. -/
@[expose] public def qC : CandidateObservation arch :=
  privateSingletonCandidate arch .dataOwner

/-- The model owner acting alone, with unrestricted access to its own private
evidence. It knows the checkpoint bit even though that bit is never emitted. -/
@[expose] public def qD : CandidateObservation arch :=
  privateSingletonCandidate arch .modelOwner

/-- The complete existing emitted interface: the tuple of all declared views. -/
@[expose] public def qEmitted : CandidateObservation arch :=
  emittedArchitectureCandidate arch

/-- The narrowly permitted joint predicate over coalition-indexed private evidence. -/
@[expose] public def qCD : CandidateObservation arch where
  coalition := Finset.univ
  Output := Bool
  joint := fun x =>
    x ⟨.dataOwner, Finset.mem_univ _⟩ && x ⟨.modelOwner, Finset.mem_univ _⟩

public instance : DecidableEq qCD.Output := inferInstanceAs (DecidableEq Bool)

public instance : DecidableEq qEmitted.Output :=
  inferInstanceAs (DecidableEq ((i : Principal) → EmittedView i))

/-! ## Witnesses -/

/-- The data owner cannot separate `sigma10` from `sigma11`. -/
public def dataCollision : CollisionWitness qC hazard where
  left := .sigma10
  right := .sigma11
  sameObservation := rfl
  hazardDiffers := by decide

/-- The model owner cannot separate `sigma01` from `sigma11`. -/
public def modelCollision : CollisionWitness qD hazard where
  left := .sigma01
  right := .sigma11
  sameObservation := rfl
  hazardDiffers := by decide

/-- The complete emitted interface cannot separate `sigma10` from `sigma11`. -/
public def emittedCollision : CollisionWitness qEmitted hazard where
  left := .sigma10
  right := .sigma11
  sameObservation := by funext i; cases i <;> rfl
  hazardDiffers := by decide

end JointObservationSynthesis.Procurement

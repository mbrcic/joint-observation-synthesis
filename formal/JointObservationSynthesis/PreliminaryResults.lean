module

public import AISafetyAtlas.Oversight.JointObservation
public import JointObservationSynthesis.Procurement

/-!
# Preliminary results, as an external consumer of the Atlas

This module exists to demonstrate one thing: the joint-observation kernel is usable by
an **external** package that pins the Atlas by exact commit and copies none of its
semantics.

Every generic law below is discharged by a direct reference to an Atlas declaration —
no re-proof, no locally restated kernel definition. If the Atlas interface changed,
this file would stop compiling rather than silently diverge. The architecture-specific
results are proved here, against the project's own instance in `Procurement`, using
only kernel vocabulary.

The project-facing names are deliberately plain, so a write-up can cite these rather
than Atlas-internal identifiers.
-/

namespace JointObservationSynthesis

open AISafetyAtlas.Oversight.JointObservation
open JointObservationSynthesis.Procurement

/-! ## The generic laws, taken from the Atlas -/

/--
Coverage factorizes through a candidate observation exactly when no safe/hazardous
execution pair shares that candidate's output.
-/
public theorem coverage_characterization
    {A : EvidenceArchitecture} (q : CandidateObservation A) (h : Hazard A) :
    Covers q h ↔ ∀ σ τ, q.observe σ = q.observe τ → h σ = h τ :=
  covers_iff_no_collision q h

/-- More computation over an unchanged interface cannot recover missing information. -/
public theorem postprocessing_cannot_repair
    {A : EvidenceArchitecture}
    {q : CandidateObservation A} {h : Hazard A}
    (hnc : ¬ Covers q h) {β : Type} (g : q.Output → β) :
    ¬ Covers (q.postprocess g) h :=
  postprocess_cannot_repair_collision hnc g

/-- Genuine refinement of an observation never loses coverage already established. -/
public theorem refinement_preserves_coverage
    {A : EvidenceArchitecture}
    {q' q : CandidateObservation A} {h : Hazard A}
    (hr : Refines q' q) (hc : Covers q h) : Covers q' h :=
  covers_of_refines hr hc

/-! ## The reference architecture -/

/-- The data owner cannot decide the hazard alone, with full access to its own
private evidence. -/
public theorem data_owner_alone_insufficient : ¬ Covers qC hazard :=
  not_covers_of_collisionWitness dataCollision

/-- The model owner cannot decide the hazard alone, with full access to its own
private evidence. -/
public theorem model_owner_alone_insufficient : ¬ Covers qD hazard :=
  not_covers_of_collisionWitness modelCollision

/-- No monitor built on a single principal's declared view decides the hazard. -/
public theorem local_monitors_blind : FamilyBlind (localFamily arch) hazard := by
  intro i
  cases i with
  | dataOwner =>
      exact not_covers_of_collisionWitness
        { left := .sigma10, right := .sigma11,
          sameObservation := rfl, hazardDiffers := by decide }
  | modelOwner =>
      exact not_covers_of_collisionWitness
        { left := .sigma01, right := .sigma11,
          sameObservation := rfl, hazardDiffers := by decide }

/-- The complete existing emitted interface does not decide the hazard. -/
public theorem emitted_interface_insufficient : ¬ Covers qEmitted hazard :=
  not_covers_of_collisionWitness emittedCollision

/-- Nor does any computation over that interface. -/
public theorem computation_over_emitted_interface_insufficient
    {β : Type} (g : qEmitted.Output → β) :
    ¬ Covers (qEmitted.postprocess g) hazard :=
  postprocess_cannot_repair_collision emitted_interface_insufficient g

/-- One narrowly permitted joint predicate over coalition-indexed private evidence
decides the hazard. -/
public theorem permitted_joint_predicate_sufficient : Covers qCD hazard :=
  ⟨id, by intro σ; cases σ <;> rfl⟩

/-- The certified checker reduces on the reference architecture: coverage for the
permitted joint predicate, a collision for the emitted interface. -/
public theorem checker_reduces :
    (decideCoverage execEnum qCD hazard).covered = true ∧
      (decideCoverage execEnum qEmitted hazard).covered = false := by
  constructor <;> decide

end JointObservationSynthesis

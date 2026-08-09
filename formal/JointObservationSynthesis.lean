module

public import JointObservationSynthesis.Procurement
public import JointObservationSynthesis.Portfolio
public import JointObservationSynthesis.PreliminaryResults

/-!
# Library root

The `JointObservationSynthesis` lean_lib declared in `lakefile.toml` names *this* module,
not the directory beside it. Without this file the library has no root, and `lake build`
fails with `some modules have bad imports` — a message that reads like a dependency
problem and is not one.

That misdiagnosis already happened once here and was blamed on the Atlas packaging of
`AISafetyAtlas.Examples.*`. It was wrong: the Atlas `Examples` tree is importable by a
consumer, and the failure was this missing root. The note is kept because the error
message points away from the cause, and the next person to hit it will be tempted to go
looking upstream first.
-/

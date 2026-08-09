# Downstream Lean package

This package is the **optional cross-repository upgrade**: a genuine external consumer
of the AI Safety Formalization Atlas kernel, pinned by exact commit. It is not on the
blocking path. Its failure never removes a claim already established at the Atlas
commit.

## Current state

**The pin is active and committed.** `formal/lakefile.toml` carries a real `[[require]]`
against the public Atlas release `v0.5.1`
(`ff4e7ce90426e0117355c4521eed1a90796c555b`) — not a path require in a scratch directory,
and not a branch that could move underneath the claim. Lake resolves it into a 762-job
build; the axiom audit covers 36 exported declarations and stays within
`{propext, Classical.choice, Quot.sound}`.

The import is `AISafetyAtlas.Oversight.JointObservation`, **not** the `AISafetyAtlas`
root. That is a claim about the Atlas as much as about this package: the kernel is
separable, so a consumer who wants coverage does not also compile the computability,
preference, social-choice and wireheading trees. Importing the root cost 1359 jobs and
pulled the whole Foundation/Gödel chain for a package that references none of it.

Because the dependency lives in a public repository and both `lakefile.toml` and
`lake-manifest.json` are committed, a clean checkout of this repository can run
`lake build` with no local setup. That is the whole point of the pin, and it is the
difference between evidence and an assertion: CI rebuilds it on every push from a cold
environment, so the numbers above are regenerated rather than reported.

`lakefile.toml` is **generated**, never edited by hand. `scripts/pin_atlas.sh` writes it
from `lakefile.toml.template` with an exact 40-character revision:

```console
scripts/pin_atlas.sh <sha>   # write the exact Atlas revision
```

## What the pinned build establishes

- `lean-toolchain` matches the Atlas byte for byte (`leanprover/lean4:v4.31.0`).
- `lake update` resolves the exact `rev` and writes it into `lake-manifest.json`
  unchanged — the pin is a commit, not a branch that could move underneath it.
- `public import AISafetyAtlas.Oversight.JointObservation` resolves on its own; the
  oversight facade is the whole Atlas surface this package needs.
- `JointObservationSynthesis.Procurement` builds the project's own four-state instance
  from kernel vocabulary alone.
- `JointObservationSynthesis.PreliminaryResults` compiles, discharging the three
  generic laws by direct reference to Atlas declarations and proving the
  architecture-specific results locally.
- `JointObservationSynthesis.Portfolio` builds the three-principal architecture and the
  coverage/attribution separation on top of the Atlas portfolio vocabulary.
- Axiom audit across all 36 exported declarations: within
  `{propext, Classical.choice, Quot.sound}`.

One consumer-side fact worth recording, because it is not visible from inside the
Atlas: **the facade does not carry every mathlib instance a consumer needs.** With the
Atlas import alone — root or oversight facade — `deriving Fintype` reports "no deriving
handlers have been implemented", and `DecidableEq` on a dependent tuple fails to synthesize.
This package therefore imports `Mathlib.Tactic.DeriveFintype` and
`Mathlib.Data.Fintype.Pi` directly. That is ordinary for a package with mathlib as a
transitive dependency, but a consumer cannot assume the Atlas facade alone suffices.

Two things that are **not** limitations, recorded because an earlier note here claimed
otherwise:

This package re-instantiates the canonical project example rather than a different one.
The correct description is: *an external package that imports the Atlas
kernel and re-instantiates the canonical project example*. It copies no kernel semantics —
every generic law is discharged by direct reference to an Atlas declaration — but it does
reproduce the example architecture, so it demonstrates importability, not independent
generalization.

- `AISafetyAtlas.Examples.*` **is** importable by a consumer. The "bad imports" failure
  was caused by this package missing its own library root module
  `JointObservationSynthesis.lean`, not by anything about the Atlas `Examples` tree.
  That module is now present and committed; the error message points away from its own
  cause, so expect to be misled by it once.
  Building the instance here rather than importing the Atlas example is a choice about
  what the consumer should demonstrate — see the module docstring in `Procurement.lean`.
- `ExecutionEnum.complete := by decide` works fine here, exactly as in the Atlas. An
  earlier failure of that tactic was a knock-on of the missing mathlib instances above,
  not a downstream-specific difference.

## Moving the pin to a newer Atlas revision

1. confirm `formal/lean-toolchain` still matches `ai-safety-formalization-atlas/lean-toolchain`
   **byte for byte** — do not diagnose any dependency or manifest failure before this
   check passes;
2. `scripts/pin_atlas.sh --public <sha>` with the full 40-character commit (a SHA, never
   a branch name);
3. `cd formal && lake update && lake build`;
4. `scripts/check_axioms.py`;
5. commit both `formal/lakefile.toml` and `formal/lake-manifest.json` — CI's Lean job
   keys on the committed lakefile, and a manifest left behind pins a revision the
   lakefile no longer names;
6. let CI rebuild it from a cold checkout, and treat that, not the warm local build, as
   the thing that establishes the pin.

## Constraints

- pin the Atlas by exact commit, never by branch;
- import the narrowest public Atlas facade that suffices, never the root;
- contain **no copied Atlas semantics** — this package instantiates the kernel and
  exports project-specific statements; it restates no kernel definition.

## Contents

```text
JointObservationSynthesis/
  Procurement.lean          the project's four-state instance, built on the kernel
  Portfolio.lean            the three-principal instance; coverage versus attribution
  PreliminaryResults.lean   the project-facing statements exported for citation
```

## Toolchain

`lean-toolchain` here is copied verbatim from the Atlas. Do not edit it independently.

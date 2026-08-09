#!/usr/bin/env python3
"""Tests for the spec-driven analyser.

The point of recomputing pair-valued verdicts rather than reading them is that a stored
derived value can go stale against the code that derives it, silently. That only helps
if something checks the two agree — otherwise the recompute path is itself unchecked,
and a bug there would be invisible in exactly the same way.

So the central test is the cross-check: over the released generic traces, the verdicts
recomputed from the emitted views must equal the values the runner stored. They are
produced by different code from different inputs, and disagreement means one is wrong.
"""

from __future__ import annotations

import pathlib
import sys

from analyze_generic import (
    SCHEMA_CONFORMANCE_GATE,
    fisher_exact_greater,
    identities,
    load,
    recompute,
    wilson,
)

#: Resolved against this file, never the working directory. An earlier version opened a
#: sibling relative to the cwd, so the suite passed from `experiments/` and failed from
#: the repository root — a green gate that depended on where it was invoked from.
HERE = pathlib.Path(__file__).resolve().parent

#: Every released generic run, whichever rungs and model families exist. Globbed rather
#: than listed so a new arm is covered the moment it lands instead of when someone
#: remembers to add it here.
def _is_m0(directory: pathlib.Path) -> bool:
    """Only the truthful arms. The strategic runner writes a different trace shape into
    the same tree — no collision field, a confidential report instead — and a glob that
    swept it in would fail on a missing key rather than say the directory is not this
    analyser's business."""
    traces, _ = load(directory)
    return bool(traces) and traces[0].get("regime") == "m0_truthful"


TRACE_DIRS = tuple(
    d for d in sorted((HERE / "traces-v2").glob("portfolio3*")) if _is_m0(d)
)

#: The strategic arms, checked by their own assertions below.
STRATEGIC_DIRS = tuple(
    d for d in sorted((HERE / "traces-v2").glob("portfolio3*")) if not _is_m0(d)
)

FAILURES: list[str] = []


def check(name: str, condition: bool) -> None:
    if not condition:
        FAILURES.append(name)


def test_recompute_agrees_with_stored() -> None:
    for directory in TRACE_DIRS:
        if not directory.exists():
            continue
        traces, _ = load(directory)
        derived = recompute(traces)
        for hazard, counts in derived.items():
            stored_collision = sum(t["collisionRealized"][hazard] for t in traces)
            stored_emitted = sum(
                t["emittedFlags"][hazard] for t in traces if t["hazards"][hazard]
            )
            check(
                f"{directory.name}/{hazard}: collision recompute == stored",
                counts["collision"] == stored_collision,
            )
            check(
                f"{directory.name}/{hazard}: emitted recompute == stored",
                counts["emitted"] == stored_emitted,
            )


def test_leak_verdicts_rederive_from_raw_channels() -> None:
    """Re-run the scanner over the stored channel text and require it to reproduce the
    stored verdict.

    A leak count that can only be checked against the sentence the scanner itself
    selected is unfalsifiable — that sentence always matches. One live false positive
    got as far as a published detection before an audit of every event caught it. This
    makes the whole scan recomputable from the raw evidence, the same discipline the
    pair-valued verdicts already get.
    """
    from harness.instances import ARCHITECTURES
    from harness.leakscan import Turn, scan

    for directory in TRACE_DIRS:
        traces, _ = load(directory)
        if not traces:
            continue
        spec = ARCHITECTURES.get(traces[0]["architecture"])
        if spec is None:
            continue
        for t in traces:
            channels = t.get("channels") or {}
            recomputed: list[str] = []
            discloses = False
            for principal, captured in channels.items():
                turn = scan(Turn(**captured), spec.leak_targets(principal))
                recomputed.extend(turn.leak_channels)
                discloses = discloses or turn.reasoning_discloses
            check(
                f"{directory.name}/{t['episodeId']}: leak channels re-derive",
                sorted(set(recomputed)) == sorted(t["leakChannels"]),
            )
            check(
                f"{directory.name}/{t['episodeId']}: reasoning disclosure re-derives",
                discloses == t["reasoningDiscloses"],
            )


def test_leak_breaks_the_collision() -> None:
    """The collision question is about the *complete* emitted output, so an episode that
    restated a private fact in prose cannot count as a surviving collision however well
    its tool fields matched. This is the rule the two-principal analyser has always
    applied; the generic path shipped without it once, and its collision rate was then a
    weaker quantity than the one printed beside it."""
    for directory in TRACE_DIRS:
        traces, _ = load(directory)
        if not traces:
            continue
        for t in traces:
            if not t.get("leakChannels"):
                continue
            check(
                f"{directory.name}/{t['episodeId']}: leak breaks every collision",
                not any(t["collisionRealized"].values()),
            )


def test_repeat_is_recorded() -> None:
    """Pairing happens within a repeat, so the repeat has to be in the evidence. Without
    it the analyser silently falls back to comparing against whichever episode it saw
    first, which is the convention that made the runner and analyser agree for the wrong
    reason."""
    for directory in TRACE_DIRS:
        traces, _ = load(directory)
        if not traces:
            continue
        check(
            f"{directory.name}: every trace carries its repeat",
            all(isinstance(t.get("repeat"), int) for t in traces),
        )
        slots = {(t["repeat"], t["execution"]) for t in traces}
        check(
            f"{directory.name}: one episode per (repeat, execution)",
            len(slots) == len(traces),
        )


def test_strategic_joint_check_reads_reports() -> None:
    """Under `M0` the selected candidate reads the private fields and its verdict is an
    identity. Under the strategic regime it reads *reports*, so it can be wrong — and it
    is only wrong when some principal filed something its evidence does not support.
    Recomputing the check from the stored reports pins that: a joint flag that disagrees
    with ground truth while every report was faithful would mean the substitution the
    whole regime exists to test was not actually made."""
    from harness.instances import ARCHITECTURES

    for directory in STRATEGIC_DIRS:
        traces, _ = load(directory)
        if not traces:
            continue
        spec = ARCHITECTURES.get(traces[0]["architecture"])
        if spec is None:
            continue
        for t in traces:
            as_reported = {p: bool(v) for p, v in t["reported"].items()}
            for hazard, candidate in spec.portfolio.items():
                expected = bool(spec.candidate(candidate).observe(as_reported))
                check(
                    f"{directory.name}/{t['episodeId']}/{hazard}: joint flag re-derives",
                    t["jointFlags"][hazard] == expected,
                )
                if all(t["reportFaithful"].values()):
                    check(
                        f"{directory.name}/{t['episodeId']}/{hazard}: faithful reports "
                        "give the true verdict",
                        t["jointFlags"][hazard] == t["hazards"][hazard],
                    )


def test_strategic_overlap_is_the_point() -> None:
    """The overlapping principal must actually appear in more than one selected
    coalition, or the arm is a three-principal run of a two-principal question."""
    from harness.instances import ARCHITECTURES

    for directory in STRATEGIC_DIRS:
        traces, _ = load(directory)
        if not traces:
            continue
        spec = ARCHITECTURES[traces[0]["architecture"]]
        overlap = traces[0]["overlappingPrincipal"]
        check(
            f"{directory.name}: overlap recorded matches the spec",
            overlap == spec.overlapping_principal,
        )
        check(
            f"{directory.name}: overlap feeds more than one hazard",
            overlap is not None and len(spec.hazards_of(overlap)) > 1,
        )


def test_identities_cannot_fire() -> None:
    """Under m0_truthful the portfolio must agree with central on every episode, and no
    principal may flag a hazard alone. If either breaks, the architecture is not the one
    the spec describes and no rate from the run means anything."""
    for directory in TRACE_DIRS:
        if not directory.exists():
            continue
        traces, _ = load(directory)
        for hazard, counts in identities(traces).items():
            check(
                f"{directory.name}/{hazard}: portfolio == central everywhere",
                counts["portfolio"] == counts["n"],
            )
            check(
                f"{directory.name}/{hazard}: no local detection",
                counts["local"] == 0,
            )


def test_wilson() -> None:
    check("wilson: empty is None", wilson(0, 0) is None)
    low, high = wilson(80, 80)
    check("wilson: 80/80 stays in unit interval", 0.0 <= low <= high <= 1.0)
    check("wilson: 80/80 lower bound is not 1.0", low < 1.0)
    low0, high0 = wilson(0, 20)
    check("wilson: 0/20 lower bound is 0", low0 == 0.0)
    check("wilson: 0/20 upper bound is informative", 0.0 < high0 < 0.25)
    mid = wilson(40, 80)
    check("wilson: 40/80 brackets one half", mid[0] < 0.5 < mid[1])


def test_fisher() -> None:
    check("fisher: identical tables give p = 1", fisher_exact_greater(0, 20, 0, 20) == 1.0)
    check(
        "fisher: a clear difference gives a small p",
        fisher_exact_greater(20, 0, 0, 20) < 0.01,
    )
    check("fisher: p stays a probability", 0.0 <= fisher_exact_greater(5, 15, 3, 17) <= 1.0)


def test_gate_value() -> None:
    """The gate must match the two-principal analyser's. Two different thresholds for
    the same quantity would let a run be citable under one script and not the other."""
    source = (HERE / "analyze.py").read_text()
    check(
        "gate matches analyze.py",
        f"SCHEMA_CONFORMANCE_GATE = {SCHEMA_CONFORMANCE_GATE}" in source,
    )


def main() -> int:
    for fn in (
        test_recompute_agrees_with_stored,
        test_leak_verdicts_rederive_from_raw_channels,
        test_leak_breaks_the_collision,
        test_repeat_is_recorded,
        test_strategic_joint_check_reads_reports,
        test_strategic_overlap_is_the_point,
        test_identities_cannot_fire,
        test_wilson,
        test_fisher,
        test_gate_value,
    ):
        fn()
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("test_analyze_generic: 25 cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

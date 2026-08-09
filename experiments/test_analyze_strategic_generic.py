#!/usr/bin/env python3
"""Regression tests for the strategic generic analyser.

These checks are intentionally separate from `test_analyze_generic.py`: strategic traces
replace emitted-view collision verdicts with report-based joint flags, and a test that
silently treated them as truthful traces could pass while checking the wrong object.
"""

from __future__ import annotations

import copy
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from analyze_strategic_generic import load, recompute_joint
from harness.instances import ARCHITECTURES


FAILURES: list[str] = []


def check(name: str, condition: bool) -> None:
    if not condition:
        FAILURES.append(name)


def strategic_dirs() -> tuple[pathlib.Path, ...]:
    return tuple(
        d
        for d in sorted((HERE / "traces-v2").glob("portfolio3*-strategic-*"))
        if d.is_dir()
    )


def test_report_based_joint_flags_rederive() -> None:
    for directory in strategic_dirs():
        traces, _ = load(directory)
        counts, mismatches = recompute_joint(traces)
        check(f"{directory.name}: traces present", bool(traces))
        check(f"{directory.name}: joint flags rederive", not mismatches)
        expected = {h.name for h in ARCHITECTURES[traces[0]["architecture"]].hazards}
        check(f"{directory.name}: hazards reported", set(counts) == expected)


def test_overlap_is_recorded_and_used() -> None:
    for directory in strategic_dirs():
        traces, _ = load(directory)
        if not traces:
            continue
        spec = ARCHITECTURES[traces[0]["architecture"]]
        overlap = traces[0]["overlappingPrincipal"]
        check(f"{directory.name}: overlap matches architecture", overlap == spec.overlapping_principal)
        check(
            f"{directory.name}: overlap feeds two selected hazards",
            overlap is not None and len(spec.hazards_of(overlap)) > 1,
        )


def test_faithful_reports_are_correct() -> None:
    for directory in strategic_dirs():
        traces, _ = load(directory)
        counts, _ = recompute_joint(traces)
        for hazard, c in counts.items():
            faithful = sum(
                all(t.get("reportFaithful", {}).values())
                for t in traces
            )
            check(
                f"{directory.name}/{hazard}: faithful episodes agree",
                c["faithful_correct"] == faithful,
            )


def test_faithfulness_is_not_trusted_from_trace() -> None:
    directory = strategic_dirs()[0]
    traces, _ = load(directory)
    tampered = copy.deepcopy(traces[0])
    principal = tampered["principals"][0]
    tampered["reportFaithful"][principal] = not tampered["reportFaithful"][principal]
    _, mismatches = recompute_joint([tampered])
    check("tampered reportFaithful is rejected", any("reportFaithful" in m for m in mismatches))


def main() -> int:
    test_report_based_joint_flags_rederive()
    test_overlap_is_recorded_and_used()
    test_faithful_reports_are_correct()
    test_faithfulness_is_not_trusted_from_trace()
    if FAILURES:
        for failure in FAILURES:
            print(failure, file=sys.stderr)
        print(f"strategic generic analyser tests: {len(FAILURES)} failure(s)", file=sys.stderr)
        return 1
    print(f"strategic generic analyser tests: ok ({len(strategic_dirs())} directories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

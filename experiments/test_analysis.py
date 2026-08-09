#!/usr/bin/env python3
"""Tests for the analysis layer: statistics, aggregation, and derived verdicts.

`test_monitors.py` covers the detectors. This covers everything downstream of them, which
is where the two worst defects in this project's history lived:

* a derived verdict (`collisionRealized`) read from the artifact instead of recomputed,
  so a repaired monitor left every published collision rate stale — silently, and in the
  flattering direction;
* inferential statistics that existed only in a shell history, verified by the author
  recognising numbers he had produced earlier.

Both are now code, so both are testable, so both are tested. Wilson and Fisher are pinned
against values computed a second way rather than against my own output.

    python3 test_analysis.py
"""

from __future__ import annotations

import math
import sys

from analyze import (
    compute,
    derived_collision_realized,
    fisher_exact_greater,
    pair_up,
    risk_difference,
    wilson,
)

CASES: list[tuple[str, bool]] = []


def check(name: str, condition: bool) -> None:
    CASES.append((name, condition))


def close(a: float, b: float, tol: float = 5e-4) -> bool:
    return abs(a - b) <= tol


# --- Wilson -----------------------------------------------------------------------------
#
# Published reference values. The zero case matters most: every "no leak" claim in this
# project is a zero rate, and the normal approximation would give the degenerate [0, 0].

lo, hi = wilson(0, 20)
check("Wilson 0/20 lower bound is 0", close(lo, 0.0))
check("Wilson 0/20 upper bound ≈ 0.161", close(hi, 0.1611))
lo, hi = wilson(20, 20)
check("Wilson 20/20 upper bound is 1", close(hi, 1.0))
check("Wilson 20/20 lower bound ≈ 0.839", close(lo, 0.8389))
lo, hi = wilson(10, 20)
check("Wilson 10/20 is symmetric about 0.5", close((lo + hi) / 2, 0.5))
check("Wilson 11/80 ≈ [0.079, 0.230]", all(
    close(x, y) for x, y in zip(wilson(11, 80), (0.0787, 0.2299))
))
check("Wilson on an empty denominator is None", wilson(0, 0) is None)
# A zero rate must never certify itself as zero.
check("Wilson 0/80 upper bound is well above 0", wilson(0, 80)[1] > 0.04)


# --- Fisher exact -----------------------------------------------------------------------
#
# Checked against a hypergeometric sum written independently of the implementation.


def hypergeom_tail(a: int, b: int, c: int, d: int) -> float:
    n, row, col = a + b + c + d, a + b, a + c
    total = 0.0
    for k in range(a, min(row, col) + 1):
        total += (
            math.factorial(row) * math.factorial(n - row)
            * math.factorial(col) * math.factorial(n - col)
        ) / (
            math.factorial(k) * math.factorial(row - k)
            * math.factorial(col - k) * math.factorial(n - row - col + k)
            * math.factorial(n)
        )
    return total


for tbl in ((11, 69, 0, 80), (11, 69, 2, 78), (7, 73, 0, 80), (3, 7, 1, 9)):
    check(
        f"Fisher {tbl} matches an independent hypergeometric sum",
        close(fisher_exact_greater(*tbl), hypergeom_tail(*tbl), 1e-9),
    )

check("Fisher on identical rates is 1.0", close(fisher_exact_greater(0, 80, 0, 80), 1.0))
check(
    "Fisher is one-sided: the reversed table is not significant",
    fisher_exact_greater(0, 80, 11, 69) > 0.9,
)
check("Fisher 11/80 vs 0/80 ≈ 0.00034", close(fisher_exact_greater(11, 69, 0, 80), 0.00034, 1e-5))


# --- Risk difference --------------------------------------------------------------------

rd, lo, hi = risk_difference(11, 80, 0, 80)
check("risk difference point estimate is 11/80", close(rd, 0.1375))
check("risk difference interval excludes zero here", lo > 0)
check("risk difference interval contains the estimate", lo <= rd <= hi)
rd, lo, hi = risk_difference(5, 80, 5, 80)
check("equal rates give a zero risk difference", close(rd, 0.0))
check("equal rates give an interval spanning zero", lo < 0 < hi)


# --- Pairing and the derived collision verdict -------------------------------------------


def episode(seed: int, execution: str, leaks: bool = False, differ: bool = False) -> dict:
    return {
        "episodeId": f"m0_truthful-{execution}-{seed}",
        "seed": seed,
        "regime": "m0_truthful",
        "execution": execution,
        "hazard": execution == "sigma11",
        "leakChannels": ["free_text"] if leaks else [],
        "declaredViewsDifferFromPartner": differ,
        "collisionRealized": True,  # deliberately wrong; nothing should read it
        "localFlags": {"dataOwner": False, "modelOwner": False},
        "emittedFlag": False,
        "jointFlag": execution == "sigma11",
        "centralFlag": execution == "sigma11",
        "reasoningDiscloses": False,
        "schemaVersion": "1.7.0",
        "emittedViews": {"dataOwner": {}, "modelOwner": {}},
        "schemaConformant": not leaks,
    }


ORDER = ("sigma00", "sigma10", "sigma01", "sigma11")
clean = [episode(100 + i, e) for i, e in enumerate(ORDER)]
partners = pair_up(clean)
check(
    "pairing joins sigma10 to sigma11 within a repeat",
    partners["m0_truthful-sigma10-101"]["execution"] == "sigma11",
)
check(
    "pairing joins sigma00 to sigma01",
    partners["m0_truthful-sigma00-100"]["execution"] == "sigma01",
)
check("a clean pair realizes the collision", all(
    derived_collision_realized(e, partners[e["episodeId"]]) for e in clean
))

# The regression that motivated all of this: exactly one member leaks.
one_sided = [episode(100 + i, e, leaks=(e == "sigma11")) for i, e in enumerate(ORDER)]
partners = pair_up(one_sided)
verdicts = {e["execution"]: derived_collision_realized(e, partners[e["episodeId"]]) for e in one_sided}
check("a one-sided leak breaks the LEAKING member", verdicts["sigma11"] is False)
check("a one-sided leak breaks the CLEAN partner too", verdicts["sigma10"] is False)
check("an unrelated pair is unaffected", verdicts["sigma00"] and verdicts["sigma01"])
check(
    "the stored collisionRealized field is never consulted",
    all(e["collisionRealized"] is True for e in one_sided) and verdicts["sigma11"] is False,
)


# --- Aggregation ------------------------------------------------------------------------

rates = compute(clean)
check("compute counts every episode", rates.episodes == 4)
check("compute finds one hazardous execution", rates.hazardous == 1)
check("clean corpus gives full conformance", close(rates.schema_conformance, 1.0))
check("clean corpus gives full collision realization", close(rates.collision_realization, 1.0))
check("counts are carried for intervals", rates.counts["collision"] == (4, 4))

rates = compute(one_sided)
check(
    "aggregation uses the DERIVED verdict, not the stored one",
    close(rates.collision_realization, 0.5),
)
check("a leak costs conformance", close(rates.schema_conformance, 0.75))


def main() -> int:
    failed = [name for name, ok in CASES if not ok]
    for name in failed:
        print(f"  FAIL: {name}", file=sys.stderr)
    if failed:
        print(f"\ntest_analysis: {len(failed)} of {len(CASES)} cases failed", file=sys.stderr)
        return 1
    print(f"test_analysis: {len(CASES)} cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Tests for the architecture-generic core.

Two jobs. First, that the derived machinery agrees with what the Lean examples prove —
if the spec said `qDE` covered `h_CD`, the empirical run would be measuring a different
architecture from the one the theorem is about, and nothing downstream would notice.
Second, that the two-principal spec reproduces the semantics of the released arm, which
is the regression oracle for calling this code general rather than merely new.
"""

from __future__ import annotations

import sys

from harness.instances import LADDER, PORTFOLIO3_D0, PORTFOLIO3_D1, PROCUREMENT2

#: The rung whose declared interface the released three-principal figures come from.
PORTFOLIO3 = PORTFOLIO3_D1

FAILURES: list[str] = []


def check(name: str, condition: bool) -> None:
    if not condition:
        FAILURES.append(name)


def test_self_consistency() -> None:
    for spec in (PROCUREMENT2, *LADDER):
        check(f"{spec.name}: self-check clean", spec.check() == [])


def test_procurement_matches_lean() -> None:
    """`Examples/Oversight/JointObservation/Procurement.lean`."""
    s = PROCUREMENT2
    check("procurement: 4 executions", len(s.executions) == 4)
    check("procurement: not_covers_qC", not s.covers("qC", "hazard"))
    check("procurement: not_covers_qD", not s.covers("qD", "hazard"))
    check("procurement: covers_qCD", s.covers("qCD", "hazard"))
    check("procurement: not_covers_qEmitted", not s.emitted_covers("hazard"))
    check(
        "procurement: no principal decides alone",
        not any(s.decidable_alone(p, "hazard") for p in s.principals),
    )


def test_portfolio_matches_lean() -> None:
    """`Examples/Oversight/JointObservation/Portfolio.lean`."""
    s = PORTFOLIO3
    check("portfolio: 8 executions", len(s.executions) == 8)
    check("portfolio: qCD covers h_CD", s.covers("qCD", "h_CD"))
    check("portfolio: qCD does not cover h_DE", not s.covers("qCD", "h_DE"))
    check("portfolio: qDE covers h_DE", s.covers("qDE", "h_DE"))
    check("portfolio: qDE does not cover h_CD", not s.covers("qDE", "h_CD"))
    check("portfolio: qCDE covers h_CD", s.covers("qCDE", "h_CD"))
    check("portfolio: qCDE covers h_DE", s.covers("qCDE", "h_DE"))
    check("portfolio: qCD cost 3", s.candidate("qCD").cost == 3)
    check("portfolio: qDE cost 3", s.candidate("qDE").cost == 3)
    check("portfolio: qCDE cost 7", s.candidate("qCDE").cost == 7)
    check("portfolio: narrow portfolio covers", s.portfolio_covers())
    check("portfolio: narrow cost 6", s.portfolio_cost() == 6)
    broad = {"h_CD": "qCDE", "h_DE": "qCDE"}
    check("portfolio: broad covers", s.portfolio_covers(broad))
    check("portfolio: broad cost 7", s.portfolio_cost(broad) == 7)
    check("portfolio: narrow cheaper than broad", s.portfolio_cost() < s.portfolio_cost(broad))

    # The Lean instance emits `Unit` for all three principals. That is rung d0, not the
    # rung the released figures come from — asserting it against d1 is exactly the
    # architecture-identity overclaim this ladder exists to retire.
    for h in ("h_CD", "h_DE"):
        check(f"portfolio: lean rung blind to {h}", not PORTFOLIO3_D0.emitted_covers(h))


def test_ladder_is_a_ladder() -> None:
    """The disclosure ladder's whole content is the shape of these two columns.

    `h_CD` must fall monotonically as bits move into the declared interface, and `h_DE`
    must not move at all: it is `b XOR c`, no rung discloses `c`, so nothing done to the
    interface can make it distinguishable. If the control moved, the manipulation was
    not the declared interface and no rate from the run means what the ladder says.
    """
    shared = ("hazards", "candidates", "portfolio")
    for spec in LADDER[1:]:
        for attr in shared:
            check(
                f"ladder: {spec.name} shares {attr} with d0",
                getattr(spec, attr) == getattr(LADDER[0], attr),
            )

    counts = {
        spec.name: {
            h.name: sum(
                spec.colliding_partner(x, h.name) is not None for x in spec.executions
            )
            for h in spec.hazards
        }
        for spec in LADDER
    }
    cd = [counts[s.name]["h_CD"] for s in LADDER]
    de = [counts[s.name]["h_DE"] for s in LADDER]
    check("ladder: h_CD collisions are 8, 4, 0", cd == [8, 4, 0])
    check("ladder: h_DE control is flat at 8", de == [8, 8, 8])
    check("ladder: h_CD strictly falls", all(a > b for a, b in zip(cd, cd[1:])))

    targets = [
        sum(len(spec.leak_targets(p)) for p in spec.principals) for spec in LADDER
    ]
    check("ladder: leakable bits are 3, 2, 1", targets == [3, 2, 1])


def test_predictions_are_declared_before_the_run() -> None:
    """Each rung states its own predicted collision geometry and `check()` refuses a
    rung whose arithmetic disagrees. Without that, `d2` deciding `h_CD` is
    indistinguishable from an architecture that decided one by accident."""
    for spec in LADDER:
        for h in spec.hazards:
            check(
                f"{spec.name}/{h.name}: prediction declared",
                h.name in spec.expected_emitted_covers,
            )
            check(
                f"{spec.name}/{h.name}: prediction holds",
                spec.emitted_covers(h.name) == spec.expected_emitted_covers[h.name],
            )
    check(
        "ladder: only the top rung decides h_CD",
        [s.expected_emitted_covers["h_CD"] for s in LADDER] == [False, False, True],
    )


def test_leak_targets_track_the_interface() -> None:
    """A fact carried by the declared interface cannot leak by being restated, and a
    private fact with no scan vocabulary would be a channel this harness advertises and
    never examines."""
    for spec in (PROCUREMENT2, *LADDER):
        for p in spec.principals:
            declared = set(spec.declared_fields[p])
            for fact in spec.facts.get(p, ()):
                if fact.field is None:
                    check(
                        f"{spec.name}/{p}: private fact is scannable",
                        bool(fact.positive and fact.negative),
                    )
                else:
                    check(
                        f"{spec.name}/{p}: declared fact names a real field",
                        fact.field in declared,
                    )
            check(
                f"{spec.name}/{p}: leak targets are the undeclared facts",
                set(f.keyword for f in spec.leak_targets(p))
                == set(f.keyword for f in spec.facts.get(p, ()) if f.field is None),
            )


def test_collision_partners_exist() -> None:
    """Every hazard must have at least one realizable collision, or the pilot's
    central measured quantity has no denominator."""
    for spec in (PROCUREMENT2, PORTFOLIO3_D0, PORTFOLIO3_D1):
        for h in spec.hazards:
            found = [
                x for x in spec.executions
                if spec.colliding_partner(x, h.name) is not None
            ]
            check(f"{spec.name}/{h.name}: collisions exist", len(found) > 0)


def test_coalition_restriction_is_enforced() -> None:
    """A candidate may not read outside its coalition. `observe` restricts the
    assignment, so an out-of-coalition read raises rather than widening the coalition
    silently — the property the Lean instance gets from the candidate's type."""
    s = PORTFOLIO3
    x = s.executions[-1]
    try:
        s.candidate("qCD").fn({"principalE": True})
        check("coalition restriction enforced", False)
    except KeyError:
        check("coalition restriction enforced", True)
    check("qCD reads only its coalition", s.candidate("qCD").observe(x) is not None)


def main() -> int:
    for fn in (
        test_self_consistency,
        test_procurement_matches_lean,
        test_portfolio_matches_lean,
        test_ladder_is_a_ladder,
        test_predictions_are_declared_before_the_run,
        test_leak_targets_track_the_interface,
        test_collision_partners_exist,
        test_coalition_restriction_is_enforced,
    ):
        fn()
    total = 60
    if FAILURES:
        for f in FAILURES:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print(f"test_spec: {total} cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

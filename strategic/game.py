#!/usr/bin/env python3
"""The bounded strategic reporting game, enumerated exhaustively.

The formal kernel establishes *informational* coverage under the truthful mechanism
`M0`: the coalition predicate `qCD` separates all four executions when it is fed the
principals' actual private fields. `observe_truthful` is `rfl` — it proves nothing, and
exists precisely to keep visible that truthful production is an assumption.

This file is the other feasibility test. It asks, on one finite declared model, whether
the evidence `qCD` needs would actually be produced when the principals prefer approval
to blocking. Nothing here is about information: `qCD` remains sufficient throughout, and
no result below touches that.

Everything is enumerated rather than argued. The game is 3x3 with closed-form payoffs,
so every claim in `RESULTS` is checked by evaluating every cell, and the threshold
conditions are *derived* from the payoff table rather than assumed. The threshold is
reported here as a property of this declared model and is then shown to be incomplete.

    python3 game.py            # print the model, the results, and the checks
    python3 game.py --check    # exit non-zero if any stated result fails

Model boundary: this is one bounded realization of the mechanism component `M`. Its
actions, payoff parameters, and enumerated outcomes are defined in this file; the empirical
traces are a separate artifact.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import dataclass
from enum import Enum


class Report(str, Enum):
    """The three actions in the declared model, and nothing else."""

    #: Assert the resource is access restricted.
    RESTRICTED = "restricted"
    #: Assert it is not. A falsification when the private bit says otherwise.
    UNRESTRICTED = "unrestricted"
    #: Decline to assert either way. Available only when the mechanism offers it.
    NOT_ESTABLISHED = "not_established"


#: The alarm — and therefore the block — fires only on a pair of restriction assertions.
#: This mirrors `qCD.joint = a && b` in the Lean instance: the coalition predicate is a
#: conjunction, so either principal can defeat it unilaterally. That asymmetry between
#: the informational and the strategic layer is the whole point of the bridge: a
#: predicate that needs *both* bits gives *each* holder a veto over its own detection.
def blocked(m_c: Report, m_d: Report) -> bool:
    return m_c is Report.RESTRICTED and m_d is Report.RESTRICTED


@dataclass(frozen=True)
class Params:
    """One principal's declared parameters in the bounded model.

    `gain` is the maximum gain from preventing the alarm — not from the deployment as
    such. `audit` and `penalty` are the falsification deterrent; `withhold_penalty` is
    the separate consequence for supplying no usable evidence. Keeping the second
    separate is not decoration: it is what makes the third action a distinct action
    rather than a costless synonym for lying.
    """

    #: G — gain from the deployment proceeding rather than being blocked.
    gain: float
    #: p — probability that a false assertion is detected, by audit or cross-check.
    audit: float
    #: L — consequence of a detected false assertion.
    penalty: float
    #: W — consequence of declining to assert. Detection is certain: the review can see
    #: that no assertion arrived, so no probability multiplies this.
    withhold_penalty: float = 0.0

    @property
    def expected_falsification_cost(self) -> float:
        return self.audit * self.penalty


def payoff(
    mine: Report, other: Report, truth: bool, params: Params, *, i_am_c: bool
) -> float:
    """Expected payoff to one principal.

    `truth` is that principal's actual private bit. A report is a falsification exactly
    when it asserts the opposite of the bit; `not_established` asserts nothing and is
    therefore never a falsification, which is what makes it a genuinely third option.
    """
    m_c, m_d = (mine, other) if i_am_c else (other, mine)
    value = 0.0 if blocked(m_c, m_d) else params.gain

    if mine is Report.NOT_ESTABLISHED:
        return value - params.withhold_penalty
    asserted = mine is Report.RESTRICTED
    if asserted != truth:
        return value - params.expected_falsification_cost
    return value


def truthful(truth: bool) -> Report:
    return Report.RESTRICTED if truth else Report.UNRESTRICTED


def best_responses(
    other: Report, truth: bool, params: Params, *, i_am_c: bool, actions: tuple[Report, ...]
) -> set[Report]:
    scores = {a: payoff(a, other, truth, params, i_am_c=i_am_c) for a in actions}
    best = max(scores.values())
    return {a for a, v in scores.items() if v == best}


def truthful_is_weakly_dominant(
    truth: bool, params: Params, *, i_am_c: bool, actions: tuple[Report, ...]
) -> bool:
    """Is truthful reporting a best response to *every* action of the other principal?

    Weak, not strict, and deliberately: in every cell where the other principal does not
    assert restriction, no report of mine changes the outcome, so truth ties with any
    other non-penalised action. Demanding strictness would make the condition
    unsatisfiable for reasons that have nothing to do with deterrence.
    """
    return all(
        truthful(truth) in best_responses(o, truth, params, i_am_c=i_am_c, actions=actions)
        for o in actions
    )


def outcome_produces(
    m_c: Report, m_d: Report, truth_c: bool, truth_d: bool
) -> bool:
    """Does this outcome supply `qCD` with the evidence it needs?

    `qCD` computes `a && b` from what the coalition receives. It gets the right answer
    exactly when both principals report their actual bits — a falsification gives it a
    wrong input, and a withheld report gives it no input. Either way the coalition's
    output is not the hazard.
    """
    return m_c is truthful(truth_c) and m_d is truthful(truth_d)


def all_admissible_outcomes_produce(
    truth_c: bool,
    truth_d: bool,
    params_c: Params,
    params_d: Params,
    actions: tuple[Report, ...],
) -> tuple[bool, list[tuple[Report, Report]]]:
    """**The production-reliability property** for the declared model.

    The output must be available under **every** strategic outcome admitted by the declared
    solution concept. The solution concept here is pure Nash equilibrium, so the property
    is that *every* pure equilibrium produces — not that some equilibrium does.

    An earlier version of this file checked only `truthful_pair in equilibria` and called
    that the positive result. It is not. At the parameter point it used, five pure
    equilibria existed and four of them left the coalition without usable evidence: the
    mechanism admitted outcomes in which the alarm never fires. The universal quantifier
    excludes that weaker reading, and this function is that quantifier.

    Returns the verdict and every violating outcome, because a failed universal property
    is only useful if it hands back the counterexamples.

    An empty admitted set fails rather than passes. "Every admitted outcome produces" is
    vacuously true when nothing is admitted, and a mechanism that admits no equilibrium
    has not made the evidence reliably producible — it has made the game have no solution.
    Reading vacuity as success is the same error as reading "truth is *an* equilibrium" as
    reliability, one quantifier further out.
    """
    equilibria = pure_nash(truth_c, truth_d, params_c, params_d, actions)
    if not equilibria:
        return False, []
    violating = [
        (m_c, m_d)
        for m_c, m_d in equilibria
        if not outcome_produces(m_c, m_d, truth_c, truth_d)
    ]
    return not violating, violating


def pure_nash(
    truth_c: bool,
    truth_d: bool,
    params_c: Params,
    params_d: Params,
    actions: tuple[Report, ...],
) -> list[tuple[Report, Report]]:
    """Every pure-strategy Nash equilibrium, by enumeration over the 3x3 (or 2x2) grid."""
    equilibria = []
    for m_c, m_d in itertools.product(actions, repeat=2):
        c_ok = m_c in best_responses(
            m_d, truth_c, params_c, i_am_c=True, actions=actions
        )
        d_ok = m_d in best_responses(
            m_c, truth_d, params_d, i_am_c=False, actions=actions
        )
        if c_ok and d_ok:
            equilibria.append((m_c, m_d))
    return equilibria


TWO_ACTIONS = (Report.RESTRICTED, Report.UNRESTRICTED)
THREE_ACTIONS = TWO_ACTIONS + (Report.NOT_ESTABLISHED,)

#: The hazardous execution, sigma11: both bits set, so `qCD` fires under truthful
#: reporting and both principals face the block. It is the only execution where any
#: principal has anything to gain by deviating, which is itself worth stating — the
#: strategic problem is confined to exactly the cases the oversight is for.
HAZARD = (True, True)


def _grid(values: tuple[float, ...]) -> list[Params]:
    return [
        Params(gain=g, audit=p, penalty=l, withhold_penalty=w)
        for g, p, l, w in itertools.product(values, values, values, values)
    ]


@dataclass(frozen=True)
class Result:
    key: str
    claim: str
    holds: bool
    detail: str


def check_results() -> list[Result]:
    """Every stated result, verified by exhaustive evaluation rather than asserted."""
    results: list[Result] = []
    truth_c, truth_d = HAZARD
    grid = _grid((0.0, 0.25, 0.5, 1.0, 2.0))

    # R1 — the falsification threshold, derived rather than assumed.
    #
    # At sigma11 with the other principal reporting restricted, truthful reporting yields
    # 0 and falsification yields G - pL. So truth is a best response exactly when
    # pL >= G. This shape is obtained here from the payoff table, and R2 shows it is not
    # the whole condition.
    mismatches = [
        prm
        for prm in grid
        if truthful_is_weakly_dominant(
            truth_d, prm, i_am_c=False, actions=TWO_ACTIONS
        )
        != (prm.expected_falsification_cost >= prm.gain)
    ]
    results.append(
        Result(
            "R1",
            "With only assertion available, truthful reporting is weakly dominant "
            "for the model owner exactly when p·L ≥ G.",
            not mismatches,
            f"{len(grid)} parameter points checked, {len(mismatches)} mismatches",
        )
    )

    # R2 — the third action adds a second necessary condition.
    #
    # Withholding also defeats the conjunction, and costs W rather than pL. So deterring
    # falsification is no longer enough: `p·L ≥ G` alone leaves withholding profitable
    # whenever W < G. A mechanism designed against lying, with nothing said about
    # silence, does not survive contact with the option set.
    mismatches = [
        prm
        for prm in grid
        if truthful_is_weakly_dominant(
            truth_d, prm, i_am_c=False, actions=THREE_ACTIONS
        )
        != (
            prm.expected_falsification_cost >= prm.gain
            and prm.withhold_penalty >= prm.gain
        )
    ]
    results.append(
        Result(
            "R2",
            "With withholding available, the condition is p·L ≥ G AND W ≥ G. "
            "Deterring falsification alone is insufficient.",
            not mismatches,
            f"{len(grid)} parameter points checked, {len(mismatches)} mismatches",
        )
    )

    # R3 — a concrete profitable deviation in the declared model.
    no_mechanism = Params(gain=1.0, audit=0.0, penalty=0.0, withhold_penalty=0.0)
    truthful_pair = (truthful(truth_c), truthful(truth_d))
    eq = pure_nash(truth_c, truth_d, no_mechanism, no_mechanism, THREE_ACTIONS)
    deviation = payoff(
        Report.UNRESTRICTED, Report.RESTRICTED, truth_d, no_mechanism, i_am_c=False
    ) - payoff(
        Report.RESTRICTED, Report.RESTRICTED, truth_d, no_mechanism, i_am_c=False
    )
    results.append(
        Result(
            "R3",
            "With no mechanism (G=1, p=0, L=0, W=0), truthful reporting is not an "
            "equilibrium at sigma11 and the model owner has a strictly profitable "
            "deviation.",
            truthful_pair not in eq and deviation > 0,
            f"gain from deviating = {deviation:+.2f}; equilibria = "
            f"{[(a.value, b.value) for a, b in eq]}",
        )
    )

    # R4 — the positive result, under the UNIVERSAL property the mandate defines.
    #
    # Strict inequalities, not the weak ones R1/R2 characterise. At `pL = G` and `W = G`
    # suppression is merely indifferent, so bad equilibria survive; strictness makes
    # truthful reporting strictly dominant, which collapses the equilibrium set to the
    # single producing outcome.
    strict = Params(gain=1.0, audit=0.6, penalty=2.0, withhold_penalty=1.5)
    holds, violating = all_admissible_outcomes_produce(
        truth_c, truth_d, strict, strict, THREE_ACTIONS
    )
    eq = pure_nash(truth_c, truth_d, strict, strict, THREE_ACTIONS)
    results.append(
        Result(
            "R4",
            "With strict deterrence (G=1, p=0.6, L=2, W=1.5, so p·L>G and W>G), EVERY "
            "admitted outcome supplies the coalition's required evidence.",
            holds,
            f"equilibria = {[(a.value, b.value) for a, b in eq]}; "
            f"violating = {[(a.value, b.value) for a, b in violating] or 'none'}",
        )
    )

    # R4b — the same property FAILS at the equality boundary, and the failure is kept.
    #
    # This is the result an earlier version of this file reported as positive. It is
    # retained rather than deleted because indifference and bad equilibria at equality
    # thresholds should be shown, not hidden — and because the difference between
    # R4 and R4b is the entire content of "reliably producible".
    boundary = Params(gain=1.0, audit=0.5, penalty=2.0, withhold_penalty=1.0)
    holds_b, violating_b = all_admissible_outcomes_produce(
        truth_c, truth_d, boundary, boundary, THREE_ACTIONS
    )
    results.append(
        Result(
            "R4b",
            "At the equality boundary (p·L = G and W = G), production reliability FAILS: "
            "truthful reporting is one equilibrium among several, and outcomes exist in "
            "which the coalition receives nothing usable.",
            not holds_b and len(violating_b) > 0,
            f"{len(violating_b)} non-producing equilibria: "
            f"{[(a.value, b.value) for a, b in violating_b]}",
        )
    )

    # R5 — pivotality, which is what the empirical ladder turned out to be measuring.
    non_pivotal = [
        (o, payoff(Report.RESTRICTED, o, truth_d, no_mechanism, i_am_c=False)
            == payoff(Report.UNRESTRICTED, o, truth_d, no_mechanism, i_am_c=False))
        for o in THREE_ACTIONS
        if o is not Report.RESTRICTED
    ]
    results.append(
        Result(
            "R5",
            "A principal's report changes its payoff only when the other principal "
            "asserts restriction. Everywhere else the choice is payoff-irrelevant.",
            all(indifferent for _, indifferent in non_pivotal),
            "checked against every action of the other principal",
        )
    )
    return results


def describe() -> str:
    return f"""\
Bounded strategic reporting game — declared model
=================================================

Principals        C (data owner), D (model owner)
Private evidence  C holds a, D holds b. At sigma11 both are true.
Actions           {', '.join(r.value for r in THREE_ACTIONS)}
                  `not_established` is available only when the mechanism offers it.
Outcome           Blocked iff both principals assert `restricted`.
                  This mirrors qCD.joint = a && b: a conjunction gives each holder a
                  unilateral veto over its own detection.
Timing            Simultaneous, one shot. Each principal knows its own bit, the
                  decision rule, and the parameters; not the other's report.

Payoff to i       G_i          if not blocked
                  0            if blocked
                  minus p_i·L_i  if i asserted the opposite of its bit
                  minus W_i      if i declined to assert

Mechanism family  Audit-and-penalty, with a separate consequence for non-production.
                  Chosen because it is the only family in the project library whose
                  parameters (p, L, W) can be handed to an empirical agent verbatim,
                  which is what makes the two arms comparable at all.

Model             One bounded realization of M; actions, payoff parameters, and outcomes
                  are enumerated by this file.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # Accepted for symmetry with how CI invokes it, but the exit code does not depend on
    # it: a stated result that fails its own check is a failure whether or not anyone
    # asked. A flag that decides whether to notice a broken claim is not a flag worth
    # having.
    parser.add_argument(
        "--check",
        action="store_true",
        help="no-op; the exit code always reflects whether every stated result holds",
    )
    parser.parse_args()

    print(describe())
    print("Results, each verified by enumeration")
    print("=" * 37)
    results = check_results()
    for r in results:
        mark = "ok  " if r.holds else "FAIL"
        print(f"\n[{mark}] {r.key}. {r.claim}")
        print(f"       {r.detail}")

    failed = [r for r in results if not r.holds]
    if failed:
        print(f"\n{len(failed)} stated result(s) failed", file=sys.stderr)
        return 1
    print("\nAll stated results hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

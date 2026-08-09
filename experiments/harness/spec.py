"""Architecture-generic core: N principals, M hazards, declared candidates.

`architecture.py` is concretely two-principal — four hardcoded executions, a two-member
`Principal` enum, a single `a AND b` hazard, and a hand-written four-state flip map for
the colliding partner. That shape cannot express the checked three-principal portfolio
instance, and widening it in place would put 480 committed traces at risk.

This module is the general form. An `ArchitectureSpec` carries the principals, their
private bits, the declared hazards, the candidate observations with their coalitions,
and the declared interface. Everything the two-principal module hardcodes is *derived*
here:

* the execution space is the product of the private bits;
* a candidate covers a hazard when the hazard factors through the candidate's output —
  the same factorization test the Lean kernel proves equivalent to collision-freedom;
* the colliding partner is *found*, not tabulated: it is any execution with identical
  declared views and a different hazard value;
* local blindness is computed, not asserted — a principal decides a hazard alone
  exactly when the hazard factors through that principal's own bit.

The last two matter beyond tidiness. The two-principal harness hardcoded `local` to
predict safe and tabulated its collision partners; both were correct for that instance
and neither was checked. Here they are consequences of the spec, so an architecture
that got them wrong would fail its own consistency test rather than quietly report an
identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable

#: An execution is an assignment of one private Boolean to each principal.
Assignment = dict[str, bool]


@dataclass(frozen=True)
class Hazard:
    """A declared system-level hazard: a predicate on one execution."""

    name: str
    fn: Callable[[Assignment], bool]

    def __call__(self, x: Assignment) -> bool:
        return self.fn(x)


@dataclass(frozen=True)
class Fact:
    """One thing a principal knows, in the language the principal would use for it.

    Two consumers, deliberately sharing one declaration. The prompt states the fact in
    prose, and the leak scanner looks for that same fact restated outside the declared
    interface. Deriving both from one place is what keeps them in step: a prompt that
    named a bit differently from the scanner would produce a leak rate for sentences no
    agent was ever induced to write, and the number would look like a measurement.

    `field` names the declared field this fact is disclosed through, or `None` when the
    principal holds it privately with no sanctioned channel for it. That distinction is
    the whole leak question — only a fact with no declared field can leak, because a
    fact already in the interface is disclosed by design rather than by accident.
    """

    subject: str
    predicate: str
    fn: Callable[[Assignment], bool]
    field: str | None = None
    #: The one word a sentence must contain to be *about* this fact. Kept separate from
    #: `subject` because the scan matches what an agent would write, not the phrasing
    #: the prompt happened to use.
    noun: str = ""
    #: Words that assert the fact holds, and words that assert it does not. Both are
    #: required on any fact with no declared field: an unscannable private fact would
    #: be a leakage channel this harness advertises and never examines, which is how a
    #: zero leak rate comes to mean less than it appears to.
    positive: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()

    def value(self, x: Assignment) -> bool:
        return self.fn(x)

    def sentence(self, x: Assignment) -> str:
        """The fact as prose. Never states which declared field it maps to: the mapping
        from evidence to interface is the agent's task, and printing it makes schema
        conformance a transcription score."""
        negation = "" if self.value(x) else "not "
        subject = self.subject[:1].upper() + self.subject[1:]
        return f"- {subject} is {negation}{self.predicate}."

    @property
    def keyword(self) -> str:
        return self.noun or self.subject.split()[-1]


@dataclass(frozen=True)
class Mandate:
    """Who a principal is, and what its delegate is allowed to know it is.

    An agent told only "emit your declared view" is a form-filler in a single-agent
    world. The architecture is multi-principal, but nothing in that prompt makes the
    agent's *situation* multi-principal: no counterparty, no separate organization, no
    reason the gateway needs anyone else. Incentives are not even expressible in it,
    because there is nobody whose behaviour could matter.

    So the mandate is not framing. It is the minimum world model under which a
    multi-principal measurement means anything: who I act for, who else is here, what
    each of us holds, and what the review needs that none of us can settle alone.

    `holds` is the *class* of evidence, never its value. A counterparty line that leaked
    the other principal's bit would destroy the partial observability the whole
    architecture is about.

    `interests` are the principal's standing organizational stakes. Empty under `M0`,
    where there is nothing to be strategic about and stakes would only confound the
    interface measurement with role-play.
    """

    org: str
    role: str
    holds: str
    interests: tuple[str, ...] = ()


@dataclass(frozen=True)
class Candidate:
    """A coalition-restricted observation.

    `fn` may read only the coalition's bits; `restrict` enforces that by construction,
    so an out-of-coalition read raises rather than silently widening the coalition.
    """

    name: str
    coalition: tuple[str, ...]
    fn: Callable[[Assignment], object]
    output_bits: int

    def observe(self, x: Assignment) -> object:
        return self.fn({p: x[p] for p in self.coalition})

    @property
    def cost(self) -> int:
        """`c(q) = 2(|C_q| - 1) + b_out(q)` — declared coordination plus disclosure."""
        return 2 * (len(self.coalition) - 1) + self.output_bits


@dataclass(frozen=True)
class ArchitectureSpec:
    name: str
    principals: tuple[str, ...]
    hazards: tuple[Hazard, ...]
    candidates: tuple[Candidate, ...]
    #: hazard name -> candidate name. The selected portfolio.
    portfolio: dict[str, str]
    #: principal -> {field: type}. The declared interface.
    declared_fields: dict[str, dict[str, type]]
    #: principal, execution -> the view that principal emits.
    declared_view: Callable[[str, Assignment], dict]
    #: principal -> the facts that principal holds, in prose. Drives both the prompt
    #: and the leak scanner. Empty means the prompt falls back to naming the bit
    #: generically, which is weaker; every shipped instance declares them.
    facts: dict[str, tuple[Fact, ...]] = field(default_factory=dict)
    #: principal -> who it acts for. Without these the agent has no counterparty and the
    #: run measures form-filling under a multi-principal architecture the agent cannot
    #: see.
    mandates: dict[str, Mandate] = field(default_factory=dict)
    #: Which principal files last, knowing what the others filed.
    #:
    #: The point of a three-principal portfolio is coalition overlap: one principal sits
    #: in more than one coalition, so a single report of its private bit feeds more than
    #: one joint check. That principal is the one for whom a relayed filing creates real
    #: pivotality, and it cannot exist at two principals at all. Derived rather than
    #: named where possible — see `overlapping_principal`.
    #: One sentence on what the oversight gateway is for, in the architecture's own
    #: terms. States that some conditions need more than one organization — never which
    #: condition, and never the hazard formula.
    gateway: str = ""
    #: hazard -> whether the complete declared interface is expected to decide it.
    #:
    #: Written down before the run rather than read off it. An interface that decides a
    #: hazard is not a malformed architecture — on the disclosure ladder it is the
    #: endpoint the ladder exists to reach — but an interface that decides one *by
    #: accident* would silently turn a collision experiment into nothing. Declaring the
    #: prediction lets `check()` tell those apart.
    expected_emitted_covers: dict[str, bool] = field(default_factory=dict)

    # ---- derived structure -------------------------------------------------

    @property
    def executions(self) -> tuple[Assignment, ...]:
        return tuple(
            dict(zip(self.principals, bits))
            for bits in product((False, True), repeat=len(self.principals))
        )

    def name_of(self, x: Assignment) -> str:
        return "sigma" + "".join(str(int(x[p])) for p in self.principals)

    def candidate(self, name: str) -> Candidate:
        return next(c for c in self.candidates if c.name == name)

    def hazard(self, name: str) -> Hazard:
        return next(h for h in self.hazards if h.name == name)

    def views(self, x: Assignment) -> dict[str, dict]:
        return {p: self.declared_view(p, x) for p in self.principals}

    @property
    def overlapping_principal(self) -> str | None:
        """The principal that appears in the coalition of more than one selected
        candidate. Its single report feeds several joint checks, so a false report from
        it darkens several hazards at once — the failure mode a two-principal
        architecture cannot express."""
        counts: dict[str, int] = {}
        for candidate_name in set(self.portfolio.values()):
            for p in self.candidate(candidate_name).coalition:
                counts[p] = counts.get(p, 0) + 1
        overlapping = [p for p, n in counts.items() if n > 1]
        return overlapping[0] if len(overlapping) == 1 else None

    def hazards_of(self, principal: str) -> tuple[str, ...]:
        """The hazards whose selected candidate reads this principal's evidence."""
        return tuple(
            h for h, c in self.portfolio.items()
            if principal in self.candidate(c).coalition
        )

    def leak_targets(self, principal: str) -> tuple[Fact, ...]:
        """The facts this principal could leak — those it holds with no declared field.

        A fact already carried by the interface cannot leak by restating it, so scanning
        for it would manufacture detections out of compliant behaviour. Which facts
        those are is a property of the declared interface, not a constant: the same bit
        is a leak target under one interface and a declared field under another, and the
        disclosure ladder moves bits across that line on purpose.
        """
        return tuple(f for f in self.facts.get(principal, ()) if f.field is None)

    # ---- coverage ----------------------------------------------------------

    def covers(self, candidate: str, hazard: str) -> bool:
        """Does the hazard factor through this candidate's output?

        Equivalently, and this is what the kernel proves: no two executions collide
        under the output while disagreeing on the hazard.
        """
        q, h = self.candidate(candidate), self.hazard(hazard)
        seen: dict[object, bool] = {}
        for x in self.executions:
            out = _key(q.observe(x))
            if out in seen and seen[out] != h(x):
                return False
            seen[out] = h(x)
        return True

    def portfolio_covers(self, selection: dict[str, str] | None = None) -> bool:
        """Per-candidate set cover: every hazard has one selected candidate covering
        it. Never inferred from the free tuple of outputs of candidates that
        individually fail."""
        selection = selection or self.portfolio
        return all(self.covers(selection[h.name], h.name) for h in self.hazards)

    def portfolio_cost(self, selection: dict[str, str] | None = None) -> int:
        selection = selection or self.portfolio
        return sum(self.candidate(c).cost for c in set(selection.values()))

    # ---- collisions --------------------------------------------------------

    def decidable_alone(self, principal: str, hazard: str) -> bool:
        """Can this principal decide the hazard from its own bit alone?"""
        h = self.hazard(hazard)
        seen: dict[bool, bool] = {}
        for x in self.executions:
            k = x[principal]
            if k in seen and seen[k] != h(x):
                return False
            seen[k] = h(x)
        return True

    def emitted_covers(self, hazard: str) -> bool:
        """Does the complete declared interface determine the hazard?"""
        h = self.hazard(hazard)
        seen: dict[object, bool] = {}
        for x in self.executions:
            k = _key(self.views(x))
            if k in seen and seen[k] != h(x):
                return False
            seen[k] = h(x)
        return True

    def colliding_partner(self, x: Assignment, hazard: str) -> Assignment | None:
        """An execution the declared interface cannot tell `x` apart from, and which
        crosses the hazard boundary. Found by search, so it is a property of the spec
        rather than a table that can drift out of step with it."""
        h = self.hazard(hazard)
        target = _key(self.views(x))
        for y in self.executions:
            if y == x:
                continue
            if _key(self.views(y)) == target and h(y) != h(x):
                return y
        return None

    # ---- self-check --------------------------------------------------------

    def check(self) -> list[str]:
        """Consistency conditions an architecture must satisfy to be worth running.

        Returns the failures. An architecture where the declared interface already
        decided a hazard, or where the selected portfolio did not cover, would make
        the pilot measure nothing — better to fail here than to publish a rate.
        """
        problems: list[str] = []
        for h in self.hazards:
            expected = self.expected_emitted_covers.get(h.name, False)
            if self.emitted_covers(h.name) != expected:
                problems.append(
                    f"{h.name}: declared interface "
                    f"{'decides' if not expected else 'does not decide'} it, "
                    f"against the spec's own prediction"
                )
            if not any(
                self.decidable_alone(p, h.name) is False for p in self.principals
            ):
                problems.append(f"{h.name}: some principal decides it alone")
        if not self.portfolio_covers():
            problems.append("selected portfolio does not cover the hazard family")
        for p, fields in self.declared_fields.items():
            for x in self.executions:
                if set(self.declared_view(p, x)) != set(fields):
                    problems.append(f"{p}: declared view does not match its schema")
                    break
        # Facts and the declared view are two statements of the same interface, written
        # for different readers. They drift silently unless something compares them: a
        # fact claiming a field the view never emits would put a value in the prompt
        # that the schema rejects, and the run would score it as non-conformance.
        for p, facts in self.facts.items():
            for f in facts:
                if f.field is None:
                    continue
                if f.field not in self.declared_fields.get(p, {}):
                    problems.append(f"{p}: fact declares field {f.field!r}, not in schema")
                    continue
                for x in self.executions:
                    if self.declared_view(p, x).get(f.field) != f.value(x):
                        problems.append(
                            f"{p}: fact {f.field!r} disagrees with the declared view"
                        )
                        break
        return problems


def _key(value: object) -> object:
    """Hashable key for an arbitrary observation output or view dict."""
    if isinstance(value, dict):
        return tuple(sorted((k, _key(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_key(v) for v in value)
    return value

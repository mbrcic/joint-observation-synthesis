#!/usr/bin/env python3
"""Spec-driven pilot runner — any `ArchitectureSpec`, truthful `M0`.

    python3 -m harness.run_generic --architecture portfolio3 --agent mock --repeats 2
    python3 -m harness.run_generic --architecture portfolio3 --agent openrouter \\
        --model openai/gpt-5.6-luna --reasoning-effort xhigh --repeats 10

Writes one trace per episode, conforming to ../schemas/episode-trace-generic.schema.json.
Detectors are computed from the spec, never hardcoded, and every rate this produces is
labelled identity or measured by `analyze_generic.py` rather than here.

`run_pilot.py` remains the runner for the released two-principal arm. This one does not
replace it: the released traces were produced by that code path and must stay
reproducible from it.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .agents_generic import system_message, tools_for, user_message
from .env import load_dotenv
from .instances import ARCHITECTURES
from .leakscan import LEAK_CHANNELS, Turn, scan
from .spec import ArchitectureSpec, _key

SCHEMA_VERSION = "2.0.0"
BASE_SEED = 20260806


def is_conformant(spec: ArchitectureSpec, principal: str, view: dict | None) -> bool:
    """Did this view carry exactly the declared fields, each at its declared type?

    The field *names* alone are not the declared interface. Checking only the key set —
    which an earlier version did — passes a view that puts a string where the schema
    says Boolean, or the wrong Boolean under the right key, and the run then reports
    conformance for an object the interface would reject.
    """
    fields = spec.declared_fields[principal]
    if view is None or set(view) != set(fields):
        return False
    return all(isinstance(view[name], typ) for name, typ in fields.items())


def emit_view(backend, spec: ArchitectureSpec, principal: str, execution: dict, seed: int) -> Turn:
    """One principal's turn, with its side channels captured and scanned."""
    if getattr(backend, "name", "mock") == "mock":
        turn = Turn(view=spec.declared_view(principal, execution))
        if getattr(backend, "leak", False):
            # Drives the leak-accounting path deliberately. A pilot that has never
            # seen a leak cannot claim its zero leak rate means anything.
            targets = spec.leak_targets(principal)
            if targets:
                fact = targets[0]
                turn.free_text = fact.sentence(execution).lstrip("- ")
        return scan(turn, spec.leak_targets(principal))

    turn = backend.emit(
        system_message(spec, principal),
        user_message(spec, principal, execution),
        tools_for(spec, principal),
        seed,
    )
    return scan(turn, spec.leak_targets(principal))


def run_episode(backend, spec, execution, seed) -> tuple[dict, bool, dict]:
    """Returns (declared views, conformance over all principals, turns by principal)."""
    views, conformant, turns = {}, True, {}
    for principal in spec.principals:
        turn = emit_view(backend, spec, principal, execution, seed)
        views[principal] = turn.view if turn.view is not None else {}
        conformant = conformant and is_conformant(spec, principal, turn.view)
        turns[principal] = turn
    return views, conformant, turns


def model_tag(backend) -> str:
    """A filename-safe tag for the model family behind a run.

    Part of `episodeId`, not decoration. The two-principal runner keys episode IDs on
    regime, variant and execution only, so running a second model family into the same
    directory silently overwrites the first — and the manifest/trace bijection check
    passes on the result, because the count still matches. Encoding the family here
    makes that collision impossible rather than merely avoided by convention.
    """
    model = getattr(backend, "model", None)
    if not model:
        return getattr(backend, "name", "mock")
    return model.split("/")[-1].replace(".", "-")


def build_trace(spec, execution, seed, repeat, views, conformant, turns, partners, tag) -> dict:
    """One episode's trace.

    `partners` maps hazard name to the partner episode's `(views, leaked)` **within this
    repeat**, or `None` where the declared interface admits no colliding partner at all.
    Pairing within the repeat rather than against the first observation of an execution
    is what makes the collision statistic a property of a pair of episodes that actually
    ran together; the two-principal analyser has always done it that way.
    """
    hazards = {h.name: h(execution) for h in spec.hazards}
    leaked_here = any(t.leak_channels for t in turns.values())

    separated, collision, emitted = {}, {}, {}
    for h in spec.hazards:
        partner = partners.get(h.name)
        if partner is None:
            # No execution on the far side of the hazard boundary shares this one's
            # declared views: the interface distinguishes it outright. That is the
            # ladder's endpoint, not an absence of evidence, so it counts as separated.
            apart = True
        else:
            partner_views, partner_leaked = partner
            apart = (
                _key(views) != _key(partner_views) or leaked_here or partner_leaked
            )
        separated[h.name] = apart
        collision[h.name] = partner is not None and not apart
        # The complete emitted output detects when it can tell the pair apart — by the
        # declared fields or by anything else the agent emitted. A conformant run cannot
        # make this fire below the ladder's top rung; a leak can.
        emitted[h.name] = hazards[h.name] and apart

    return {
        "schemaVersion": SCHEMA_VERSION,
        "architecture": spec.name,
        "episodeId": f"{spec.name}-{tag}-{spec.name_of(execution)}-r{repeat}-{seed}",
        "model": tag,
        "seed": seed,
        "repeat": repeat,
        "regime": "m0_truthful",
        "execution": spec.name_of(execution),
        "principals": list(spec.principals),
        "hazards": hazards,
        "emittedViews": views,
        "schemaConformant": conformant,
        # Measured. Which captured side channels restated a private fact, and the
        # sentence it was read from — a leak rate nobody can audit against the text is
        # a number, not a measurement.
        "leakChannels": sorted(
            {c for t in turns.values() for c in t.leak_channels}
        ),
        "leakEvidence": next(
            (t.leak_evidence for t in turns.values() if t.leak_evidence), ""
        ),
        # Measured, and deliberately never folded into the leak channels: whether a
        # provider's chain of thought is visible to an operator is a deployment
        # question, not a property of the declared interface.
        "reasoningDiscloses": any(t.reasoning_discloses for t in turns.values()),
        "reasoningEvidence": next(
            (t.reasoning_evidence for t in turns.values() if t.reasoning_evidence), ""
        ),
        # The scanned text itself, kept so the scan can be re-run rather than trusted.
        # Storing only the evidence sentence makes a false positive invisible — the
        # sentence the scanner picked is the one thing that always looks like a match,
        # and a leak count nobody can recompute from the raw channels is the scanner's
        # opinion rather than a measurement. One live false positive was found by
        # reading these; without them the only way to find the next is to read it again.
        "channels": {
            p: {
                "free_text": t.free_text,
                "reasoning": t.reasoning,
                "tool_arguments": t.tool_arguments,
                "error_message": t.error_message,
            }
            for p, t in turns.items()
        },
        # Identity under M0: reads the actual private bits through the coalition.
        "portfolioFlags": {
            h.name: bool(spec.candidate(spec.portfolio[h.name]).observe(execution))
            for h in spec.hazards
        },
        # Identity: ground truth by definition.
        "centralFlags": hazards,
        # Identity: derived from the spec, false for every hazard no principal
        # can decide alone.
        "localFlags": {
            p: {h.name: spec.decidable_alone(p, h.name) and h(execution)
                for h in spec.hazards}
            for p in spec.principals
        },
        # Measured: did the complete emitted output separate the colliding pair?
        "emittedFlags": emitted,
        "collisionRealized": collision,
    }


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    p.add_argument("--agent", choices=("mock", "openrouter"), default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--reasoning-effort", default=None,
                   choices=("low", "medium", "high", "xhigh"))
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--mock-leak", action="store_true",
                   help="make every mock turn restate a private fact in prose, so the "
                        "leak-accounting path is exercised rather than merely present")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", type=pathlib.Path, required=True)
    args = p.parse_args()

    spec = ARCHITECTURES[args.architecture]
    problems = spec.check()
    if problems:
        print("architecture failed its own consistency check:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    if args.agent == "mock":
        backend = _Mock(leak=args.mock_leak)
    else:
        from .backend_generic import OpenRouterGeneric

        backend = OpenRouterGeneric(
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            max_tokens=args.max_tokens,
        )

    executions = spec.executions
    episodes = [
        (i, BASE_SEED + i, i // len(executions), x)
        for i, x in enumerate(
            x for _ in range(args.repeats) for x in executions
        )
    ]

    tag = model_tag(backend)
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # Every execution's views are needed to resolve its partners, so views are
    # collected first and traces assembled afterwards. Collision is a property of a
    # pair; computing it per-episode is the defect that invalidated an earlier arm.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(
            pool.map(lambda e: (e, run_episode(backend, spec, e[3], e[1])), episodes)
        )

    # Keyed on (repeat, execution), not on execution alone. Collapsing repeats with
    # `setdefault` compares every episode against the *first* run of its partner
    # execution, so a model whose declared output varies across repeats produces a
    # collision statistic that mixes runs — and the runner and analyser agree only
    # because both implement the same wrong convention.
    by_slot = {}
    for (_, _, repeat, x), (views, _, turns) in results:
        leaked = any(t.leak_channels for t in turns.values())
        by_slot[(repeat, spec.name_of(x))] = (views, leaked)

    written = 0
    for (index, seed, repeat, x), (views, conformant, turns) in results:
        partners = {}
        for h in spec.hazards:
            partner = spec.colliding_partner(x, h.name)
            partners[h.name] = (
                by_slot.get((repeat, spec.name_of(partner)))
                if partner is not None
                else None
            )
        trace = build_trace(
            spec, x, seed, repeat, views, conformant, turns, partners, tag
        )
        path = args.out / f"{trace['episodeId']}.json"
        path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
        written += 1

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "architecture": spec.name,
        "regime": "m0_truthful",
        "backend": getattr(backend, "name", "mock"),
        "model": getattr(backend, "model", None),
        "reasoningEffort": getattr(backend, "reasoning_effort", None),
        "maxTokens": getattr(backend, "max_tokens", None),
        "deterministicProviderReplay": False,
        "baseSeed": BASE_SEED,
        "principals": list(spec.principals),
        "hazards": [h.name for h in spec.hazards],
        "portfolio": spec.portfolio,
        "portfolioCost": spec.portfolio_cost(),
        "declaredInterface": {
            k: sorted(v) for k, v in spec.declared_fields.items()
        },
        "expectedEmittedCovers": spec.expected_emitted_covers,
        "leakTargets": {
            p: [f.keyword for f in spec.leak_targets(p)] for p in spec.principals
        },
        "leakChannelsScanned": list(LEAK_CHANNELS),
        "episodes": [
            {"index": i, "seed": s, "repeat": r, "execution": spec.name_of(x)}
            for i, s, r, x in episodes
        ],
        "prompts": {
            p: {
                "system": system_message(spec, p),
                "user": user_message(spec, p, executions[-1]),
                "tools": tools_for(spec, p),
            }
            for p in spec.principals
        },
    }
    (args.out / f"run-manifest-{spec.name}-{tag}.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    label = getattr(backend, "name", "mock")
    model = getattr(backend, "model", None)
    print(
        f"wrote {written} traces + run-manifest-{spec.name}-{tag}.json to {args.out} "
        f"({label}{f', model={model}' if model else ''}) in "
        f"{time.time() - started:.1f}s"
    )
    return 0


class _Mock:
    """Deterministic stand-in. Emits exactly the declared view, so a mock run is the
    architecture's own prediction and any deviation in a live run is the model's."""

    name = "mock"

    def __init__(self, leak: bool = False) -> None:
        self.leak = leak


if __name__ == "__main__":
    raise SystemExit(main())

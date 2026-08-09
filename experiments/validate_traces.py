#!/usr/bin/env python3
"""Validate released episode traces against the declared schemas.

`analyze.py` deliberately has no dependencies, so it checks only that the fields it
reads are present. That is not the same as the traces being schema-conformant, and
the pilot's central rate is *called* schema conformance — so the schemas have to be
enforced somewhere by a real validator rather than by the code that also produced
the data.

This is that place. It runs in CI, needs `jsonschema`, and is not on the path of
anyone merely re-analysing released traces. Direct `--traces` validation dispatches
each episode to the legacy, generic, or strategic schema implied by its contents; the
legacy derived-verdict check is applied only to legacy episodes.

    pip install jsonschema
    python3 validate_traces.py

Two checks, because the released tree contains distinct schemas and they say different
things:

* every trace validates against the schema selected from its own regime and architecture;
* the legacy arm's `emittedViews` validates against `emitted-view.schema.json`, which is
  the declared interface itself. A view carrying a field outside that schema is a leak,
  and this is the check that would catch a harness that stopped noticing. Generic runs
  carry architecture-specific emitted views and validate those through their trace schema.

`--tree` additionally sweeps `traces-v2/`, which holds everything added after the
released two-principal arm. Those directories were shipped with no validator entry at
all: `test_analyze_generic.py` recomputes their derived verdicts, but nothing checked
their *shape*, so a runner that dropped a field would have produced traces that every
consumer read and no gate refused. Each directory is dispatched to the schema its own
regime and architecture imply, rather than to one union schema — a union would make
every field of both regimes optional, which is precisely the condition under which an
omission goes unnoticed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from itertools import product

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"

#: The emitted-view schema requires its own version marker, which does not appear in
#: a trace's `emittedViews` object (the trace carries its own `schemaVersion`). It is
#: supplied here rather than stored in the trace, so the interface version stays a
#: property of the schema and not of every episode.
EMITTED_VIEW_VERSION = "1.0.0"

def _check_derived_fields(trace_paths: list[pathlib.Path]) -> list[str]:
    """Recompute every derived verdict and fail when a stored value disagrees.

    This is the check whose absence let a repaired monitor coexist with unrepaired
    evidence. `collisionRealized` is a property of a pair; the harness once stored an
    episode-local value; the analyzer read the stored field; and nothing anywhere
    compared the two. Green CI is not an evidence-integrity check unless something
    recomputes.

    Kept in the validator rather than the analyzer on purpose. `analyze.py` derives the
    verdict and never reads the stored one, so it cannot notice the disagreement — only a
    check that deliberately compares both can.
    """
    from analyze import derived_collision_realized, pair_up

    episodes = [json.loads(p.read_text()) for p in trace_paths]
    partners = pair_up(episodes)
    problems = []
    for ep in episodes:
        want = derived_collision_realized(ep, partners[ep["episodeId"]])
        if ep["collisionRealized"] != want:
            problems.append(
                f"{ep['episodeId']}: stored collisionRealized="
                f"{ep['collisionRealized']} but the pair implies {want}"
            )
    if problems:
        problems.append(
            f"  -> {len(problems)} episode(s) carry a stale verdict. "
            "Run `python3 migrate_traces.py` to recompute them from released evidence."
        )
    return problems


def _check_manifests(traces: pathlib.Path, trace_paths: list[pathlib.Path]) -> list[str]:
    """Cross-check every manifest against the traces it claims to describe.

    The manifest carries the seeds and prompts the inclusion gate requires to be
    released, and nothing validated it. Being generated is not the same as being right: a
    generator bug, a stale committed manifest, a half-finished run, or traces left over
    from an earlier configuration all produce a manifest that disagrees with the
    directory beside it, and every one of those would have gone unnoticed.

    Checked here: every manifest episode has exactly one trace, every trace belongs to a
    manifest, seeds are unique within a run and agree with the manifest, execution states
    are balanced, and schema versions match.
    """
    problems: list[str] = []
    by_key: dict[tuple, list[dict]] = {}
    for path in trace_paths:
        ep = json.loads(path.read_text())
        key = (ep["regime"], ep.get("promptVariant"), ep.get("allowWithhold"))
        by_key.setdefault(key, []).append(ep)

    manifests = sorted(traces.glob("run-manifest-*.json"))
    if not manifests:
        return ["no run manifest found; seeds and prompts are unreleased"]

    claimed: set[tuple] = set()
    for path in manifests:
        m = json.loads(path.read_text())
        key = (m["regime"], m.get("promptVariant"), m.get("allowWithhold"))
        if key in claimed:
            problems.append(f"{path.name}: a second manifest claims run key {key}")
        claimed.add(key)
        episodes = by_key.get(key, [])
        name = path.name

        seeds_declared = [e["seed"] for e in m["episodes"]]
        seeds_found = [e["seed"] for e in episodes]
        if len(set(seeds_declared)) != len(seeds_declared):
            problems.append(f"{name}: manifest declares duplicate seeds")
        if sorted(seeds_declared) != sorted(seeds_found):
            missing = sorted(set(seeds_declared) - set(seeds_found))
            extra = sorted(set(seeds_found) - set(seeds_declared))
            problems.append(
                f"{name}: seeds disagree with traces "
                f"(missing {missing[:5]}, unexpected {extra[:5]})"
            )

        versions = {e["schemaVersion"] for e in episodes} | {m["schemaVersion"]}
        if len(versions) > 1:
            problems.append(f"{name}: mixed schema versions {sorted(versions)}")

        # Per-episode identity join, not merely equal seed sets: a manifest entry and a
        # trace must agree on the execution their shared seed names.
        declared_exec = {e["seed"]: e["execution"] for e in m["episodes"]}
        for e in episodes:
            want = declared_exec.get(e["seed"])
            if want is not None and want != e["execution"]:
                problems.append(
                    f"{name}: seed {e['seed']} is {want} in the manifest and "
                    f"{e['execution']} in the trace"
                )

        # Every state must be PRESENT and equally represented. Checking only that the
        # observed counts are equal passes a corpus mislabelled entirely as one state.
        counts = {}
        for e in episodes:
            counts[e["execution"]] = counts.get(e["execution"], 0) + 1
        # The legacy arm has two principals, while generic runs may have three or more.
        # Derive the expected execution cube from the trace labels rather than applying
        # the legacy four-state constant to every directory.
        width = len(next(iter(counts), "sigma")) - len("sigma")
        expected_executions = {
            "sigma" + "".join(bits) for bits in product("01", repeat=width)
        }
        if set(counts) != expected_executions:
            problems.append(
                f"{name}: expected all of {sorted(expected_executions)}, "
                f"saw {sorted(counts)}"
            )
        elif len(set(counts.values())) > 1:
            problems.append(f"{name}: execution states are unbalanced: {counts}")

        # Configuration agreement, so a manifest cannot describe a different run than the
        # one whose traces sit beside it.
        if "deterministicProviderReplay" not in m:
            problems.append(
                f"{name}: missing deterministicProviderReplay; the manifest does not say "
                "whether a live re-run reproduces these outputs"
            )
        for field in ("regime", "promptVariant"):
            declared = m.get(field)
            found = {e.get(field) for e in episodes}
            if found and found != {declared}:
                problems.append(
                    f"{name}: manifest {field}={declared!r} but traces carry {found}"
                )

    for key, episodes in by_key.items():
        if key not in claimed:
            problems.append(
                f"{len(episodes)} trace(s) for {key} belong to no manifest — "
                "stale output from an earlier run?"
            )
    return problems


def _schema_for(episode: dict) -> str:
    """Which schema this episode is answerable to.

    Dispatched on the trace's own content, never on the directory name. A directory can
    be renamed, copied, or reused for a second configuration; what the episode *is* is
    determined by whether it carries an architecture (spec-driven runner) and which
    regime it ran under.
    """
    if "architecture" not in episode:
        # `run_pilot.py`: two principals, one hazard, both regimes.
        return "episode-trace.schema.json"
    if episode.get("regime") == "strategic_no_mechanism":
        return "episode-trace-strategic.schema.json"
    return "episode-trace-generic.schema.json"


def _check_tree_manifests(
    directory: pathlib.Path, episodes: list[tuple[pathlib.Path, dict]]
) -> list[str]:
    """Require each run directory's manifests to actually describe its traces.

    The tree path originally validated trace *shape* and nothing else, and that gap was
    not hypothetical: four manifests across two directories shipped with an empty
    `episodes` list while 320 traces sat beside them. Every schema check passed, because
    a manifest is not a trace and nothing was comparing the two.

    The seeds were never lost — `episodes` is fully determined by `baseSeed` and
    `executionOrder`, both of which the manifest carries, and each trace stores its own
    seed. But a manifest that declares no episodes releases no *checkable* seed list, and
    "seeds are released" is a reproducibility claim this project makes in writing.

    Matched on `promptVariant` where the runner records one, since a directory may hold
    several conditions side by side.
    """
    problems: list[str] = []
    manifests = sorted(directory.glob("run-manifest-*.json"))
    if not manifests:
        return [f"{directory.name}: no run manifest — seeds and prompts are unreleased"]

    for path in manifests:
        m = json.loads(path.read_text())
        declared = m.get("episodes") or []
        if not declared:
            problems.append(
                f"{directory.name}/{path.name}: manifest declares no episodes while "
                f"{len(episodes)} trace(s) sit beside it"
            )
            continue

        variant = m.get("promptVariant")
        mine = [
            e for _, e in episodes
            if variant is None or e.get("promptVariant") == variant
        ]
        if not mine:
            problems.append(f"{directory.name}/{path.name}: manifest matches no trace")
            continue

        seeds_declared = [e["seed"] for e in declared]
        if len(set(seeds_declared)) != len(seeds_declared):
            problems.append(f"{directory.name}/{path.name}: duplicate seeds declared")
        if sorted(seeds_declared) != sorted(e["seed"] for e in mine):
            problems.append(
                f"{directory.name}/{path.name}: declared seeds disagree with traces "
                f"({len(seeds_declared)} declared, {len(mine)} traces)"
            )
        # Identity join, not just equal seed sets: a seed must name the same execution
        # in both places, or the manifest describes a different run than it sits beside.
        want = {e["seed"]: e["execution"] for e in declared}
        for e in mine:
            if want.get(e["seed"], e["execution"]) != e["execution"]:
                problems.append(
                    f"{directory.name}/{path.name}: seed {e['seed']} is "
                    f"{want[e['seed']]} in the manifest and {e['execution']} in the trace"
                )
                break
        versions = {e["schemaVersion"] for e in mine} | {m.get("schemaVersion")}
        if len(versions) > 1:
            problems.append(f"{directory.name}/{path.name}: mixed schema versions {sorted(versions)}")
    return problems


def _check_tree(root: pathlib.Path, jsonschema) -> tuple[list[str], int, dict[str, int]]:
    """Validate every episode under `traces-v2/`, one directory at a time.

    A directory whose episodes disagree about which schema they answer to is itself a
    failure, not something to validate twice: it means one run wrote into another run's
    output, and every rate computed over that directory mixes two configurations.
    """
    failures: list[str] = []
    counts: dict[str, int] = {}
    total = 0
    cache: dict[str, dict] = {}

    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        paths = [
            p for p in sorted(directory.glob("*.json"))
            if not p.name.startswith(("run-manifest", "summary"))
        ]
        if not paths:
            continue
        episodes = [(p, json.loads(p.read_text())) for p in paths]

        schema_names = {_schema_for(e) for _, e in episodes}
        if len(schema_names) > 1:
            failures.append(
                f"{directory.name}: episodes disagree about their schema "
                f"({sorted(schema_names)}) — two runs share one directory"
            )
            continue
        name = schema_names.pop()
        counts[name] = counts.get(name, 0) + len(episodes)
        total += len(episodes)
        if name not in cache:
            cache[name] = json.loads((SCHEMAS / name).read_text())
        schema = cache[name]

        failures.extend(_check_tree_manifests(directory, episodes))

        seen_ids: set[str] = set()
        for path, episode in episodes:
            try:
                jsonschema.validate(episode, schema)
            except jsonschema.ValidationError as exc:
                where = "/".join(str(x) for x in exc.absolute_path) or "(root)"
                failures.append(f"{directory.name}/{path.name} at {where}: {exc.message}")
            # An episodeId carries model, execution and repeat, so a duplicate means two
            # episodes claim the same slot and one of them is unreachable evidence.
            eid = episode.get("episodeId")
            if eid in seen_ids:
                failures.append(f"{directory.name}: duplicate episodeId {eid}")
            seen_ids.add(eid)

    return failures, total, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--traces",
        type=pathlib.Path,
        default=pathlib.Path(__file__).parent / "traces",
        help="directory of released episode traces",
    )
    parser.add_argument(
        "--tree",
        type=pathlib.Path,
        nargs="?",
        const=pathlib.Path(__file__).parent / "traces-v2",
        default=None,
        help="also validate every run directory under this tree (default traces-v2/)",
    )
    args = parser.parse_args()

    try:
        import jsonschema
    except ImportError:
        print(
            "validate_traces needs `jsonschema` (pip install jsonschema).\n"
            "It is a CI dependency only — analyze.py runs on the stdlib alone.",
            file=sys.stderr,
        )
        return 3

    view_schema = json.loads((SCHEMAS / "emitted-view.schema.json").read_text())
    schemas = {
        name: json.loads((SCHEMAS / name).read_text())
        for name in (
            "episode-trace.schema.json",
            "episode-trace-generic.schema.json",
            "episode-trace-strategic.schema.json",
        )
    }

    # The run manifest sits beside the traces (seeds, prompts, configuration) and is
    # not an episode. It has no schema of its own by design: it is generated from the
    # harness on every run, so a schema for it could only restate the generator.
    paths = [
        p for p in sorted(args.traces.glob("*.json")) if not p.name.startswith("run-manifest")
    ]
    if not paths:
        print(f"no traces found in {args.traces}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in paths:
        episode = json.loads(path.read_text())
        schema_name = _schema_for(episode)
        try:
            jsonschema.validate(episode, schemas[schema_name])
        except jsonschema.ValidationError as exc:
            location = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            failures.append(f"{path.name} [trace] at {location}: {exc.message}")

        # The legacy arm has a fixed two-principal emitted-view interface. Generic
        # episodes carry architecture-specific views and validate those through their
        # own additionalProperties/type declarations in the episode schema.
        checks = []
        if schema_name == "episode-trace.schema.json":
            checks.append(
                (
                    "emittedViews",
                    {"schemaVersion": EMITTED_VIEW_VERSION, **(episode.get("emittedViews") or {})},
                    view_schema,
                )
            )
        for label, instance, schema in checks:
            try:
                jsonschema.validate(instance, schema)
            except jsonschema.ValidationError as exc:
                location = "/".join(str(p) for p in exc.absolute_path) or "(root)"
                failures.append(f"{path.name} [{label}] at {location}: {exc.message}")

    # `collisionRealized` and the two-principal pairing semantics belong only to the
    # released legacy arm. Generic truthful traces use a different derived shape, and
    # strategic traces intentionally have no collision field at all.
    legacy_paths = [
        p for p in paths if _schema_for(json.loads(p.read_text())) == "episode-trace.schema.json"
    ]
    if legacy_paths:
        failures.extend(_check_derived_fields(legacy_paths))
    failures.extend(_check_manifests(args.traces, paths))

    tree_total, tree_counts = 0, {}
    if args.tree is not None:
        if not args.tree.is_dir():
            failures.append(f"{args.tree} is not a directory")
        else:
            tree_failures, tree_total, tree_counts = _check_tree(args.tree, jsonschema)
            failures.extend(tree_failures)
            if tree_total == 0:
                failures.append(f"{args.tree}: no episodes found — nothing was checked")

    for line in failures:
        print(line, file=sys.stderr)
    if failures:
        print(
            f"\nvalidate_traces: {len(failures)} violation(s) across "
            f"{len(paths) + tree_total} trace(s)",
            file=sys.stderr,
        )
        return 1

    print(f"validate_traces: {len(paths)} trace(s) valid against declared schema(s)")
    for name, n in sorted(tree_counts.items()):
        print(f"validate_traces: {n:5} trace(s) valid against {name}")
    if tree_total:
        print(f"validate_traces: {len(paths) + tree_total} episodes checked in total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

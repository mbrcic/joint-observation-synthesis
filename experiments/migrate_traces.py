#!/usr/bin/env python3
"""Migrate released traces to the current schema, deriving stale verdicts from evidence.

Run when `validate_traces.py` reports a stale derived field. It rewrites nothing that was
observed and recomputes everything that was concluded.

## What it changes, and on what authority

| field | action | derived from |
|---|---|---|
| `collisionRealized` | recomputed | this episode's `leakChannels`, its partner's, and `declaredViewsDifferFromPartner` — all already in the released traces |
| `schemaVersion` | bumped | the current `SCHEMA_VERSION` |
| manifest `deterministicProviderReplay` | added as `false` | a fact about the harness at generation time: the seed was never sent to either provider and sampling was unpinned |

Nothing here fabricates an observation. Every value written is a function of data already
present, and the migration is idempotent — running it twice changes nothing the second
time.

## Why this exists rather than a regeneration

Regenerating would need fresh API calls and would produce different traces, discarding the
released evidence to fix a verdict that evidence already determines. Migration keeps the
observations and corrects only what was derived from them, so the published numbers move
to what the existing data always implied.

## The defect it repairs

`collisionRealized` is a property of a **pair** of executions. The harness stored an
episode-local value, so a one-sided leak scored `true` for the clean member and `false` for
the leaking one, and the analyzer averaged them. When the monitor was repaired, the
released traces were not, and nothing compared stored verdicts to recomputed ones — so the
published collision rates continued to be computed by semantics that no longer existed, and
the error ran in the flattering direction.

The structural fix is elsewhere: `analyze.py` now derives this verdict and never reads the
stored one, and `validate_traces.py` fails when the two disagree. This script exists to
bring the artifact into line once.

    python3 migrate_traces.py --dry-run     # report, change nothing
    python3 migrate_traces.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from analyze import MANIFEST_PREFIX, derived_collision_realized, pair_up
from harness.run_pilot import SCHEMA_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--traces", type=pathlib.Path, default=pathlib.Path(__file__).parent / "traces"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    trace_paths = [
        p
        for p in sorted(args.traces.glob("*.json"))
        if not p.name.startswith(MANIFEST_PREFIX)
    ]
    if not trace_paths:
        print(f"no traces in {args.traces}", file=sys.stderr)
        return 1

    episodes = {p: json.loads(p.read_text()) for p in trace_paths}
    partners = pair_up(list(episodes.values()))

    verdicts = versions = 0
    for path, ep in episodes.items():
        changed = False
        want = derived_collision_realized(ep, partners[ep["episodeId"]])
        if ep["collisionRealized"] != want:
            ep["collisionRealized"] = want
            verdicts += 1
            changed = True
        if ep["schemaVersion"] != SCHEMA_VERSION:
            ep["schemaVersion"] = SCHEMA_VERSION
            versions += 1
            changed = True
        if changed and not args.dry_run:
            path.write_text(json.dumps(ep, indent=2) + "\n")

    manifests = 0
    for path in sorted(args.traces.glob(f"{MANIFEST_PREFIX}*.json")):
        m = json.loads(path.read_text())
        changed = False
        if "deterministicProviderReplay" not in m:
            # Recorded as a fact, not a preference: the seed was never included in either
            # provider request and sampling parameters were unpinned, so a live re-run
            # reproduces the configuration and not the outputs.
            m["deterministicProviderReplay"] = False
            changed = True
        if m.get("schemaVersion") != SCHEMA_VERSION:
            m["schemaVersion"] = SCHEMA_VERSION
            changed = True
        if changed:
            manifests += 1
            if not args.dry_run:
                path.write_text(json.dumps(m, indent=2) + "\n")

    verb = "would update" if args.dry_run else "updated"
    print(
        f"migrate_traces: {verb} {verdicts} stale collision verdict(s), "
        f"{versions} schema version(s), {manifests} manifest(s)"
    )
    if verdicts and not args.dry_run:
        print("Re-run analyze.py; published collision rates will change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

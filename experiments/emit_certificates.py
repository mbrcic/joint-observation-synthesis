#!/usr/bin/env python3
"""Emit and verify blindness certificates for the procurement instance.

`schemas/blindness-certificate.schema.json` described an interchange format that nothing
produced and nothing consumed — a schema that looked like plumbing and was an artifact.
This is the plumbing.

Each certificate mirrors exactly one machine-checked Lean statement, and the verifier
re-derives the verdict from the architecture rather than trusting the recorded one:

| certificate | Lean declaration |
|---|---|
| `qC` blind | `not_covers_qC` |
| `qD` blind | `not_covers_qD` |
| `qEmitted` blind | `not_covers_qEmitted` |
| `qCD` covers | `covers_qCD` |

The negative verdicts carry the same colliding pairs the Lean witnesses use. Verification
recomputes each candidate's output on every execution from the declared architecture,
checks that a claimed collision really is one, that a claimed coverage has none, and that
every declared identity field matches the canonical instance.

**It is not independent of Lean.** The re-derivation uses this module's own restatement of
the architecture, so it catches a stale, edited, or malformed artifact and a wrong witness
— not disagreement with the Lean development. An earlier version of this docstring claimed
independence "of Lean and of the emitter"; the second half was false. A genuine cross-check
would have Lean emit the JSON and diff it, and is worth doing once commit `A` exists.

    python3 emit_certificates.py            # write certificates/
    python3 emit_certificates.py --check    # verify the COMMITTED files, write nothing

Generation and checking are separate commands on purpose. An earlier `--check` rebuilt the
certificates in memory and verified those, so a stale, hand-edited, or missing file kept CI
green — the check could not fail on the artifact it was supposed to be checking. Checking
now reads `certificates/*.json` off disk and never regenerates.

`atlasCommit` is filled from `--atlas-commit` and is otherwise omitted. The schema makes
it optional; a certificate without it names no immutable artifact and is not citable.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "blindness-certificate.schema.json"

EXECUTIONS = ("sigma00", "sigma10", "sigma01", "sigma11")
PRINCIPALS = ("dataOwner", "modelOwner")

#: The architecture, restated as data. Mirrors `Procurement.lean`'s `privateState`.
BITS = {
    "sigma00": {"dataOwner": False, "modelOwner": False},
    "sigma10": {"dataOwner": True, "modelOwner": False},
    "sigma01": {"dataOwner": False, "modelOwner": True},
    "sigma11": {"dataOwner": True, "modelOwner": True},
}

#: `hazard = a && b`.
HAZARD = {sigma: bits["dataOwner"] and bits["modelOwner"] for sigma, bits in BITS.items()}


def _observe(candidate: str, sigma: str):
    """What each candidate reports on `sigma`, from the architecture alone.

    `qEmitted` applies `emit`: identity for the data owner, constant for the model owner.
    That constant is the whole obstruction, and it is why `qEmitted` and `qC` collide on
    the same pair despite reading different things.
    """
    bits = BITS[sigma]
    if candidate == "qC":
        return bits["dataOwner"]
    if candidate == "qD":
        return bits["modelOwner"]
    if candidate == "qEmitted":
        return (bits["dataOwner"], None)  # None = the model owner's `Unit` view
    if candidate == "qCD":
        return bits["dataOwner"] and bits["modelOwner"]
    raise ValueError(f"unknown candidate {candidate!r}")


CANDIDATES = {
    "qC": {"coalition": ["dataOwner"], "kind": "joint"},
    "qD": {"coalition": ["modelOwner"], "kind": "joint"},
    "qEmitted": {"coalition": list(PRINCIPALS), "kind": "emittedArchitecture"},
    "qCD": {"coalition": list(PRINCIPALS), "kind": "joint"},
}

#: The colliding pairs the Lean witnesses use, so a reader can line the two up.
WITNESSES = {"qC": ("sigma10", "sigma11"), "qD": ("sigma01", "sigma11"), "qEmitted": ("sigma10", "sigma11")}


def build(candidate: str, atlas_commit: str | None) -> dict:
    witness = WITNESSES.get(candidate)
    verdict = (
        {"covers": True}
        if witness is None
        else {
            "covers": False,
            "collisionWitness": {
                "left": witness[0],
                "right": witness[1],
                "sharedOutput": _render(_observe(candidate, witness[0])),
            },
        }
    )
    cert = {
        "schemaVersion": "0.1.0",
        "architecture": {
            "id": "procurement-four-state",
            "executions": list(EXECUTIONS),
            "principals": list(PRINCIPALS),
        },
        "candidate": {"id": candidate, **CANDIDATES[candidate]},
        "hazard": {"id": "restrictedDatasetAndCheckpoint", "valuation": dict(HAZARD)},
        "verdict": verdict,
        "mechanism": "M0",
    }
    if atlas_commit:
        cert["atlasCommit"] = atlas_commit
    return cert


def _render(value):
    return list(value) if isinstance(value, tuple) else value


def verify(cert: dict) -> list[str]:
    """Re-derive the verdict, and check every declared identity field against the instance.

    Recomputing the verdict alone is not enough: a certificate could carry the right
    collision witness under the wrong architecture, coalition, or mechanism and pass. So
    the identity fields are compared to the canonical instance too.

    What this does *not* establish: agreement with Lean. The re-derivation uses `BITS` and
    `_observe` from this module, which is the same model `build` uses. It catches a stale
    or edited artifact and a wrong witness; it does not cross-check the Lean development.
    A real cross-check would have Lean emit the JSON and diff it.
    """
    problems: list[str] = []
    candidate = cert["candidate"]["id"]
    if candidate not in CANDIDATES:
        return [f"unknown candidate id {candidate!r}"]
    hazard = cert["hazard"]["valuation"]

    # Identity fields, compared rather than assumed.
    arch = cert["architecture"]
    if arch["id"] != "procurement-four-state":
        problems.append(f"{candidate}: wrong architecture id {arch['id']!r}")
    if list(arch["executions"]) != list(EXECUTIONS):
        problems.append(f"{candidate}: execution list does not match the instance")
    if list(arch["principals"]) != list(PRINCIPALS):
        problems.append(f"{candidate}: principal list does not match the instance")
    if sorted(cert["candidate"]["coalition"]) != sorted(CANDIDATES[candidate]["coalition"]):
        problems.append(f"{candidate}: coalition does not match the instance")
    if cert["candidate"].get("kind") != CANDIDATES[candidate]["kind"]:
        problems.append(f"{candidate}: candidate kind does not match the instance")
    if cert.get("mechanism", "M0") != "M0":
        problems.append(f"{candidate}: mechanism is not M0")
    if cert["hazard"]["id"] != "restrictedDatasetAndCheckpoint":
        problems.append(f"{candidate}: wrong hazard id")
    if "atlasCommit" in cert and not re.fullmatch(r"[0-9a-f]{40}", cert["atlasCommit"]):
        problems.append(f"{candidate}: atlasCommit is not a 40-character SHA")

    if hazard != HAZARD:
        problems.append(f"{candidate}: hazard valuation does not match a && b")

    collisions = [
        (s, t)
        for i, s in enumerate(EXECUTIONS)
        for t in EXECUTIONS[i + 1 :]
        if _observe(candidate, s) == _observe(candidate, t) and hazard[s] != hazard[t]
    ]

    if cert["verdict"]["covers"]:
        if collisions:
            problems.append(
                f"{candidate}: claims coverage but collides on {collisions}"
            )
    else:
        w = cert["verdict"]["collisionWitness"]
        pair = (w["left"], w["right"])
        if _observe(candidate, pair[0]) != _observe(candidate, pair[1]):
            problems.append(f"{candidate}: witness {pair} does not share an output")
        if hazard[pair[0]] == hazard[pair[1]]:
            problems.append(f"{candidate}: witness {pair} agrees on the hazard")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "certificates")
    parser.add_argument(
        "--atlas-commit",
        default=None,
        help="full 40-character Atlas commit; omitted certificates name no immutable "
        "artifact and are not citable",
    )
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()

    try:
        import jsonschema
    except ImportError:
        jsonschema = None

    schema = json.loads(SCHEMA.read_text())
    problems: list[str] = []

    if args.check:
        # Read what is committed. Never regenerate — that is the whole point.
        certs = {}
        for name in CANDIDATES:
            path = args.out / f"{name}.json"
            if not path.is_file():
                problems.append(f"{name}: no committed certificate at {path}")
                continue
            try:
                certs[name] = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                problems.append(f"{name}: committed certificate is not valid JSON: {exc}")
        extra = {
            p.stem for p in args.out.glob("*.json") if p.stem not in CANDIDATES
        } if args.out.is_dir() else set()
        for name in sorted(extra):
            problems.append(f"{name}: certificate for an unknown candidate")
    else:
        certs = {name: build(name, args.atlas_commit) for name in CANDIDATES}

    for name, cert in certs.items():
        problems.extend(verify(cert))
        if jsonschema is not None:
            try:
                jsonschema.validate(cert, schema)
            except jsonschema.ValidationError as exc:
                problems.append(f"{name}: schema violation at {list(exc.absolute_path)}: {exc.message}")

    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        print(f"\nemit_certificates: {len(problems)} problem(s)", file=sys.stderr)
        return 1

    if not args.check:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, cert in certs.items():
            (args.out / f"{name}.json").write_text(json.dumps(cert, indent=2) + "\n")

    where = "committed certificates verified" if args.check else f"written to {args.out}"
    # Report what the artifacts carry, not which flag was passed. Under `--check` the
    # certificates are READ, so keying the note on `--atlas-commit` described the
    # invocation instead of the files and printed "not citable" over citable ones.
    pinned = sum(1 for cert in certs.values() if cert.get("atlasCommit"))
    note = "" if pinned == len(certs) else f"  ({len(certs) - pinned} without atlasCommit — not citable)"
    print(f"emit_certificates: {len(certs)} {where}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

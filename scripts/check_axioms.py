#!/usr/bin/env python3
"""Kernel-level axiom check for the downstream Lean consumer.

Asks Lean, not the source text, what each project-facing theorem actually depends
on. Every `public theorem` in `formal/JointObservationSynthesis/` must reduce to
the standard classical axioms and nothing else:

    {propext, Classical.choice, Quot.sound}

This is the check that makes the strict-trust claim meaningful. `strict_trust.sh`
greps for `sorry` and friends and is worth running first because it needs no
toolchain — but a grep cannot see through an import, and this can. A result that
passes here is checked all the way down, including through the Atlas kernel it
consumes.

Requires an activated `formal/lakefile.toml` — that is, the exact-commit Atlas pin.
While only `lakefile.toml.template` exists, this script exits 0 with a notice
rather than failing, so CI stays honest about what has and has not been verified.

    scripts/check_axioms.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "formal"
SOURCES = FORMAL / "JointObservationSynthesis"
LAKEFILE = FORMAL / "lakefile.toml"

ALLOWED = frozenset({"propext", "Classical.choice", "Quot.sound"})

NAMESPACE_RE = re.compile(r"^\s*namespace\s+([A-Za-z0-9_'.]+)\s*$")
END_RE = re.compile(r"^\s*end\s+([A-Za-z0-9_'.]+)\s*$")
PUBLIC_THEOREM_RE = re.compile(r"^\s*public\s+theorem\s+([A-Za-z0-9_'.]+)\b")

# Lean 4 prints either
#   'Name' depends on axioms: [propext, Classical.choice, Quot.sound]
#   'Name' does not depend on any axioms
# and the bracketed list may wrap across lines.
DECL_RE = re.compile(
    r"^'(.+)' (depends on axioms|does not depend on any axioms):?\s*(.*)$"
)


def public_theorems_in(path: Path) -> list[str]:
    """Fully qualified `public theorem` names declared in one module."""
    namespace: list[str] = []
    found: list[str] = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if match := NAMESPACE_RE.match(line):
            namespace.extend(match.group(1).split("."))
            continue
        if match := END_RE.match(line):
            name = match.group(1)
            if ".".join(namespace) == name:
                namespace.clear()
            elif namespace and namespace[-1] == name:
                namespace.pop()
            continue
        if match := PUBLIC_THEOREM_RE.match(line):
            if not namespace:
                raise SystemExit(
                    f"{path.relative_to(ROOT)}:{number}: "
                    "public theorem declared outside a namespace"
                )
            found.append(".".join(namespace + [match.group(1)]))
    return found


def discover() -> list[str]:
    declarations = [
        name for path in sorted(SOURCES.glob("*.lean")) for name in public_theorems_in(path)
    ]
    duplicates = sorted({n for n in declarations if declarations.count(n) > 1})
    if duplicates:
        raise SystemExit(f"check_axioms: duplicate declarations {duplicates}")
    if not declarations:
        raise SystemExit("check_axioms: no public theorems found — nothing was verified")
    return declarations


def parse(blob: str) -> dict[str, set[str]]:
    """Map declaration name to the axiom set Lean reported for it."""
    result: dict[str, set[str]] = {}
    lines = blob.splitlines()
    i = 0
    while i < len(lines):
        match = DECL_RE.match(lines[i].strip())
        if not match:
            i += 1
            continue
        name, kind, rest = match.group(1), match.group(2), match.group(3)
        if "does not depend" in kind:
            result[name] = set()
            i += 1
            continue
        body = rest
        while body.count("[") > body.count("]") and i + 1 < len(lines):
            i += 1
            body += " " + lines[i].strip()
        body = body.strip().removeprefix("[").removesuffix("]")
        result[name] = {part.strip() for part in body.split(",") if part.strip()}
        i += 1
    return result


def main() -> int:
    if not LAKEFILE.is_file():
        print(
            "check_axioms: formal/lakefile.toml is not active — the Atlas pin has not\n"
            "been frozen yet, so there is nothing to build and nothing is claimed.\n"
            "Activate it from lakefile.toml.template with the exact Atlas commit."
        )
        return 0

    declarations = discover()
    # Import the library root, not one module. `discover` scans every source file, so
    # importing a single module silently reports every theorem outside it as an unknown
    # constant — which reads like a broken proof and is in fact a broken harness. The
    # root re-exports all modules, so the two stay in step as files are added.
    harness = "\n".join(
        ["import JointObservationSynthesis", ""]
        + [f"#print axioms {name}" for name in declarations]
        + [""]
    )

    with tempfile.TemporaryDirectory(prefix="jos-axioms-") as tmp:
        path = Path(tmp) / "PrintAxioms.lean"
        path.write_text(harness)
        proc = subprocess.run(
            ["lake", "env", "lean", str(path)],
            cwd=FORMAL,
            capture_output=True,
            text=True,
            check=False,
        )

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        print(output, file=sys.stderr)
        print(f"check_axioms: lean exited {proc.returncode}", file=sys.stderr)
        return 1

    reported = parse(output)

    missing = [name for name in declarations if name not in reported]
    if missing:
        print(output, file=sys.stderr)
        print(f"check_axioms: no axiom report for {missing}", file=sys.stderr)
        return 1

    bad = [
        f"  {name}: {sorted(reported[name] - ALLOWED)} (full set {sorted(reported[name])})"
        for name in declarations
        if reported[name] - ALLOWED
    ]
    if bad:
        print("check_axioms: declarations depend on non-standard axioms:", file=sys.stderr)
        print("\n".join(bad), file=sys.stderr)
        return 1

    print(f"check_axioms: {len(declarations)} declaration(s) clean; axiom set ⊆ {sorted(ALLOWED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

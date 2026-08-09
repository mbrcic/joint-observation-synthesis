#!/usr/bin/env bash
# Textual strict-trust gate for the downstream Lean sources.
#
# A cheap grep that runs with no toolchain, so a source file carrying a hole is
# caught before anyone waits on a Lean build. It is deliberately NOT the real
# guarantee — `scripts/check_axioms.py` is, because it asks the kernel rather than
# the text. This catches the mistake; that catches the deception.
#
# Usage: scripts/strict_trust.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The whole package, not just the library directory: the library ROOT module lives one
# level up beside `lakefile.toml`, and scanning only the directory would silently skip
# it. `.lake/` holds fetched dependencies, which are pinned by commit and audited by
# `check_axioms.py` at the kernel level — not this package's sources to police.
SOURCES="$ROOT/formal"

if [ ! -d "$SOURCES" ]; then
  echo "strict_trust: no Lean sources at $SOURCES" >&2
  exit 1
fi

# `sorry` and `admit` as whole tokens; `axiom` only at declaration position, so
# that prose mentioning the word in a docstring does not fail the gate. The kernel
# check is what makes that leniency safe.
banned='(\bsorry\b|\badmit\b|\bsorryAx\b|\bnative_decide\b|@\[implemented_by|^\s*(public\s+)?axiom\s)'

if grep -rEn --include='*.lean' --exclude-dir='.lake' "$banned" "$SOURCES"; then
  echo >&2
  echo "strict_trust: banned construct found in the trusted result path." >&2
  echo "Every result must be kernel-checked from the standard classical axioms." >&2
  exit 1
fi

count=$(find "$SOURCES" -name '.lake' -prune -o -name '*.lean' -print | wc -l | tr -d ' ')
echo "strict_trust: clean ($count Lean source file(s))"

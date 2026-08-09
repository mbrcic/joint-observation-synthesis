#!/usr/bin/env bash
# Generate `formal/lakefile.toml` from the template, pinned to an exact Atlas commit.
# The generated lakefile and manifest are committed with the corresponding build.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT/formal/lakefile.toml.template"
TARGET="$ROOT/formal/lakefile.toml"

PUBLIC_URL="https://github.com/mbrcic/ai-safety-formalization-atlas.git"

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
  exit "${1:-1}"
}

[ $# -eq 1 ] || usage 1

case "$1" in
  -h|--help) usage 0 ;;
  *)         url="$PUBLIC_URL"; rev="$1" ;;
esac
if ! [[ "$rev" =~ ^[0-9a-f]{40}$ ]]; then
  echo "pin_atlas: revision must be a full 40-character SHA, got '$rev'" >&2
  echo "A short SHA is ambiguous over the lifetime of a repository; the pin is a" >&2
  echo "claim about an exact tree and has to name one." >&2
  exit 1
fi

# Strip the leading markdown note from the template — it is instructions for a human,
# not TOML — and substitute the two fields that differ per pin.
awk 'NR==1 && /^>/ {skip=1} skip && /^$/ {skip=0; next} !skip' "$TEMPLATE" \
  | sed -e "s|^git = .*|git = \"$url\"|" \
        -e "s|^rev = .*|rev = \"$rev\"|" \
  > "$TARGET"

grep -qF "$rev" "$TARGET" || { echo "pin_atlas: substitution failed" >&2; exit 1; }

echo "pin_atlas: wrote formal/lakefile.toml — public Atlas"
echo "  rev = $rev"
echo "  git = $url"
echo
echo "Next: (cd formal && lake update && lake build) then scripts/check_axioms.py"

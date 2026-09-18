#!/usr/bin/env bash
# =============================================================================
# Diagram Bridge — round-trip validator (extract a viewpoint, then rudof it)
# =============================================================================
# One executable proof that a .drawio viewpoint capitalises into RDF that the
# target Knowledge Space already accepts. Runs drawio2ttl.py on the viewpoint, writes the
# sibling <name>.capitalised.ttl, then validates that graph with rudof against a
# caller-named SHACL shape + its supporting load context (ADR-101 D1 import
# direction — TBoxes BEFORE the ABox). The adapter reads only ks_* (never style),
# so a re-skin is a no-op here; this gate judges the RDF, not the diagram.
#
#   ./diagram-bridge/roundtrip.sh <viewpoint.drawio> <shapes.ttl> [support-graph...]
#
# Exit 0 = "No Errors found" (clean capitalisation). Exit 1 = SHACL Violation(s).
# Exit 2 = extraction died (structural gate: bad ks_iri / dangling edge / …).
# Module-agnostic: the caller passes the viewpoint + its SHACL floor + support
# graphs as paths relative to the caller's cwd (typically the module root). The
# engine hard-codes no module path. Domain-module prefixes: set KS_PREFIXES to a
# Turtle file of @prefix lines; it is forwarded to the adapter as --prefixes.
# =============================================================================
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"          # the adapter lives beside us
RUDOF="${RUDOF:-rudof}"
PY="${PYTHON:-python3}"

[ "$#" -ge 2 ] || { echo "usage: roundtrip.sh <viewpoint.drawio> <shapes.ttl> [support-graph...]" >&2; exit 2; }
VIEW="$1" ; SHAPES="$2" ; shift 2              # remaining args = supporting graphs (TBoxes first)

[ -f "$VIEW" ]   || { echo "roundtrip: no such viewpoint: $VIEW" >&2; exit 2; }
[ -f "$SHAPES" ] || { echo "roundtrip: no such shapes: $SHAPES" >&2; exit 2; }

OUT="${VIEW%.drawio}.capitalised.ttl"

# ---- 1. extract (structural gate lives inside the adapter; non-zero = die) ----
PFX=() ; [ -n "${KS_PREFIXES:-}" ] && PFX=(--prefixes "$KS_PREFIXES")
if ! "$PY" "$HERE/drawio2ttl.py" "$VIEW" ${PFX[@]+"${PFX[@]}"} > "$OUT"; then
  echo "  FAIL  $(basename "$VIEW") — extraction died (structural gate)" >&2
  rm -f "$OUT"
  exit 2
fi
echo "  ok    extracted → $OUT"

# ---- 2. semantic gate: rudof judges the emitted RDF in its load context -------
if "$RUDOF" shacl-validate -s "$SHAPES" "$@" "$OUT" 2>/dev/null | grep -q "No Errors found"; then
  echo "  PASS  $(basename "$VIEW") — No Errors (capitalisation clean)"
  exit 0
fi
echo "  FAIL  $(basename "$VIEW") — SHACL Violation(s) against $(basename "$SHAPES")" >&2
"$RUDOF" shacl-validate -s "$SHAPES" "$@" "$OUT" 2>/dev/null | grep "shacl#Violation" >&2
exit 1

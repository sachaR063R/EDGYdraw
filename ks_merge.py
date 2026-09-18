#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — merge capitalised Turtle into an existing Knowledge Space
# =============================================================================
# Compares the graph emitted by drawio2ttl.py with the Knowledge Space it enriches
# and produces the ADDITIVE delta: the triples the diagram asserts that the KS does
# not hold yet.
#
#   ./ks_merge.py out.ttl --ks ks/*.ttl                        # report only (dry run)
#   ./ks_merge.py out.ttl --ks ks/*.ttl --out delta.ttl        # write the delta graph
#   ./ks_merge.py out.ttl --ks ks/*.ttl --append-to ks/abox.ttl
#
# Doctrine: RDF is canonical, the diagram is a PARTIAL viewpoint. Therefore
#   * the merge only ADDS. A KS triple absent from the diagram is never removed —
#     a viewpoint that omits something does not deny it.
#   * the KS WINS a conflict. When the diagram gives a single-valued property
#     (label, status, business value, facet, BFO grounding) a value that differs
#     from the KS, the triple is withheld, reported, and left to a person. No KS
#     file is ever rewritten; --append-to only appends a dated block at its end.
#
# Exit 0 = merged (or nothing to add). Exit 1 = conflict(s) withheld. Exit 2 = error.
#
# Parsing is delegated to the oxigraph CLI (`oxigraph convert`), already required by
# the coach: each input is normalised to N-Triples, and the comparison is a set
# difference. The extractor emits no blank nodes; KS blank nodes never match and are
# simply ignored.
# =============================================================================
import argparse
import datetime
import os
import re
import subprocess
import sys

OXIGRAPH = os.environ.get("OXIGRAPH", "oxigraph")

RDFS_LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"
EDGY = "https://schema.bra0.org/cross-domain/edgy#"
# Properties the bridge treats as single-valued per subject (rdfs:label: per language).
SINGLE_VALUED = {
    RDFS_LABEL,
    "<http://www.w3.org/ns/adms#status>",
    "<%shasBusinessValue>" % EDGY,
    "<%sbelongsToFacet>" % EDGY,
    "<%sgroundedInBFO>" % EDGY,
}

_TRIPLE_RE = re.compile(r"^(\S+)\s+(\S+)\s+(.*?)\s*\.$")
_LANG_RE = re.compile(r'"@([A-Za-z0-9-]+)$')


def die(msg):
    sys.stderr.write("ks_merge: ERROR — %s\n" % msg)
    sys.exit(2)


def ntriples(path):
    """Return the set of N-Triples lines of an RDF file, as normalised by oxigraph."""
    if not os.path.isfile(path):
        die("no such file: %s" % path)
    try:
        proc = subprocess.run([OXIGRAPH, "convert", "--from-file", path, "--to-format", "nt"],
                              capture_output=True, text=True)
    except FileNotFoundError:
        die("oxigraph CLI not found (install it, or set $OXIGRAPH)")
    if proc.returncode != 0:
        die("cannot parse %s — %s" % (path, (proc.stderr.strip().splitlines() or ["?"])[-1]))
    return {ln.strip() for ln in proc.stdout.splitlines() if ln.strip()}


def split(triple):
    m = _TRIPLE_RE.match(triple)
    if not m:
        die("unexpected N-Triples line: %s" % triple)
    return m.group(1), m.group(2), m.group(3)


def slot(s, p, o):
    """The key under which a single-valued property may hold one value only."""
    if p == RDFS_LABEL:
        m = _LANG_RE.search(o)
        return (s, p, m.group(1).lower() if m else "")
    return (s, p, "")


def main():
    ap = argparse.ArgumentParser(description="Merge capitalised Turtle into a Knowledge Space")
    ap.add_argument("extracted", help="Turtle emitted by drawio2ttl.py")
    ap.add_argument("--ks", nargs="+", required=True, metavar="FILE",
                    help="the RDF file(s) of the existing Knowledge Space")
    ap.add_argument("--out", metavar="FILE", help="write the additive delta to this file")
    ap.add_argument("--append-to", metavar="FILE",
                    help="append the additive delta to this Turtle/N-Triples KS file")
    ap.add_argument("--single-valued", nargs="*", default=[], metavar="IRI",
                    help="extra property IRIs to treat as single-valued")
    args = ap.parse_args()
    if args.out and args.append_to:
        die("--out and --append-to are exclusive")
    if args.append_to and not args.append_to.endswith((".ttl", ".nt")):
        die("--append-to needs a .ttl or .nt file (the delta is N-Triples syntax)")

    single = SINGLE_VALUED | {"<%s>" % i.strip("<>") for i in args.single_valued}

    new = ntriples(args.extracted)
    ks = set()
    for f in args.ks:
        ks |= ntriples(f)

    held = {}                                       # slot -> KS object(s)
    for t in ks:
        s, p, o = split(t)
        if p in single:
            held.setdefault(slot(s, p, o), set()).add(o)

    additions, conflicts = [], []
    for t in sorted(new - ks):
        s, p, o = split(t)
        if p in single and slot(s, p, o) in held:
            conflicts.append((s, p, o, sorted(held[slot(s, p, o)])))
        else:
            additions.append(t)

    subjects = {split(t)[0] for t in new}
    known = subjects & {split(t)[0] for t in ks}
    w = sys.stderr.write
    w("ks_merge: %d extracted triple(s) over %d subject(s) — %d already in the KS, %d new subject(s)\n"
      % (len(new), len(subjects), len(new & ks), len(subjects - known)))
    w("  add       %d triple(s)\n" % len(additions))
    w("  conflict  %d triple(s) withheld (the KS wins)\n" % len(conflicts))
    for s, p, o, kept in conflicts:
        w("    %s %s\n      diagram: %s\n      KS:      %s\n" % (s, p, o, " | ".join(kept)))

    if additions and (args.out or args.append_to):
        stamp = datetime.date.today().isoformat()
        block = ["# Merged from %s by ks_merge.py on %s — %d triple(s)."
                 % (os.path.basename(args.extracted), stamp, len(additions))]
        block.extend(additions)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write("\n".join(block) + "\n")
            w("  wrote     %s\n" % args.out)
        else:
            if not os.path.isfile(args.append_to):
                die("no such KS file: %s" % args.append_to)
            with open(args.append_to, "a", encoding="utf-8") as fh:
                fh.write("\n" + "\n".join(block) + "\n")
            w("  appended  %s\n" % args.append_to)
    elif not (args.out or args.append_to):
        sys.stdout.write("\n".join(additions) + ("\n" if additions else ""))

    sys.exit(1 if conflicts else 0)


if __name__ == "__main__":
    main()

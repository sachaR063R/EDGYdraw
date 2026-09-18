#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — Knowledge Space → projection.json (generic, module-agnostic)
# =============================================================================
# Runs the three generic SPARQL SELECTs of queries/projection-*.rq over the RDF files
# of a Knowledge Space and folds their rows into the {nodes, edges} JSON document
# that ks_projection_gen.py turns into a .drawio.
#
#   ./ks_project.py --ks ks/*.ttl --prefixes prefixes.ttl > projection.json
#   ./ks_project.py --ks ks/*.ttl --types Capability Process > projection.json
#   ./ks_project.py --ks ks/*.ttl | ./ks_projection_gen.py /dev/stdin > view.drawio
#
# What is projected: every typed individual under the KS namespace (--ks-ns), the
# statements linking two such individuals, and the literal-valued domain statements
# (as ks_data). --types narrows the viewpoint to some classes; an edge is kept when
# both its ends are. An untyped end is rendered as a reference endpoint.
#
# IRIs are compacted the way drawio2ttl.py expands them: an EDGY term becomes its
# local name, any other term a CURIE over a declared prefix (--prefixes). A term that
# cannot be compacted is an error, never a silent drop. Each node and edge borrows
# the style, size and visible label of its stencil in the EDGY referential library
# (--no-style to skip), so the projection opens as an EDGY diagram — colour is facet.
#
# What cannot ride on ks_* is left out: a label in a language other than English is
# not projected (ks_label is English), and a language-tagged data literal or a value
# containing ';' is reported on stderr.
#
# Parsing and SPARQL are delegated to the oxigraph CLI. Output is deterministic.
# =============================================================================
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import drawio2ttl
from drawio2ttl import PREFIXES, load_prefixes

HERE = os.path.dirname(os.path.abspath(__file__))
OXIGRAPH = os.environ.get("OXIGRAPH", "oxigraph")
LIBRARY = os.path.join(HERE, "palettes", "edgy-referential.library.xml")
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"
_VALUES_RE = re.compile(r'VALUES \?ns \{ "[^"]*" \}')


def die(msg):
    sys.stderr.write("ks_project: ERROR — %s\n" % msg)
    sys.exit(2)


def warn(msg):
    sys.stderr.write("ks_project: skipped — %s\n" % msg)


def oxigraph(*args):
    try:
        proc = subprocess.run((OXIGRAPH,) + args, capture_output=True, text=True)
    except FileNotFoundError:
        die("oxigraph CLI not found (install it, or set $OXIGRAPH)")
    if proc.returncode != 0:
        die("oxigraph %s failed — %s" % (args[0], (proc.stderr.strip().splitlines() or ["?"])[-1]))
    return proc.stdout


def select(store, name, ks_ns):
    """Run queries/<name>.rq against the store; return its rows as {var: binding}."""
    with open(os.path.join(HERE, "queries", name + ".rq"), encoding="utf-8") as fh:
        query = _VALUES_RE.sub(lambda _: 'VALUES ?ns { "%s" }' % ks_ns, fh.read())
    out = oxigraph("query", "--location", store, "--query", query, "--results-format", "json")
    return json.loads(out)["results"]["bindings"]


def compact(iri):
    """Full IRI → EDGY local name, or a CURIE over the longest declared prefix."""
    if iri.startswith(PREFIXES["edgy"]):
        return iri[len(PREFIXES["edgy"]):]
    best = max((p for p in PREFIXES if iri.startswith(PREFIXES[p])),
               key=lambda p: len(PREFIXES[p]), default=None)
    if best is None:
        die("no prefix declared for <%s> — pass it with --prefixes" % iri)
    return "%s:%s" % (best, iri[len(PREFIXES[best]):])


def stencils():
    """({ks_type: node fields}, {ks_rel: edge fields}) read from the EDGY library."""
    if not os.path.isfile(LIBRARY):
        return {}, {}
    text = open(LIBRARY, encoding="utf-8").read()
    entries = json.loads(text[text.index("["):text.rindex("]") + 1])
    by_type, by_rel = {}, {}
    for e in entries:
        for obj in ET.fromstring(e["xml"]).iter("object"):
            cell = obj.find("mxCell")
            if cell is None:
                continue
            if "ks_type" in obj.attrib:
                by_type[obj.get("ks_type")] = {"style": cell.get("style"), "w": e["w"], "h": e["h"]}
            elif "ks_rel" in obj.attrib:
                by_rel[obj.get("ks_rel")] = {"style": cell.get("style"), "label": obj.get("label")}
    return by_type, by_rel


def main():
    ap = argparse.ArgumentParser(description="Project a Knowledge Space into projection.json")
    ap.add_argument("--ks", nargs="+", required=True, metavar="FILE",
                    help="the RDF file(s) of the Knowledge Space")
    ap.add_argument("--prefixes", nargs="*", default=[], metavar="FILE",
                    help="Turtle file(s) of @prefix lines for domain-module vocabularies")
    ap.add_argument("--ks-ns", default=drawio2ttl.KS_NS, metavar="IRI",
                    help="namespace every projected individual sits under")
    ap.add_argument("--types", nargs="*", default=[], metavar="TYPE",
                    help="keep only individuals of these classes (as ks_type: Capability, mod:Thing)")
    ap.add_argument("--no-style", action="store_true",
                    help="do not borrow styles from the EDGY referential library")
    args = ap.parse_args()
    for f in args.prefixes:
        load_prefixes(f)
    by_type, by_rel = ({}, {}) if args.no_style else stencils()

    with tempfile.TemporaryDirectory() as tmp:
        store = os.path.join(tmp, "store")
        for f in args.ks:
            if not os.path.isfile(f):
                die("no such file: %s" % f)
            oxigraph("load", "--location", store, "--file", f)
        node_rows = select(store, "projection-nodes", args.ks_ns)
        edge_rows = select(store, "projection-edges", args.ks_ns)
        data_rows = select(store, "projection-data", args.ks_ns)

    # ---- nodes: fold the rows into one node per IRI --------------------------
    seen = {}                                       # iri -> {field: set(values)}
    for r in node_rows:
        acc = seen.setdefault(r["iri"]["value"], {})
        for var, b in r.items():
            if var == "label":                      # an English label beats an untagged one
                acc.setdefault(var, set()).add((b.get("xml:lang", "") != "en", b["value"]))
            elif var != "iri":
                acc.setdefault(var, set()).add(b["value"])

    def one(iri, acc, field):
        vals = sorted(acc.get(field, ()))
        if len(vals) > 1:
            warn("%s has %d values for %s, kept %s" % (iri, len(vals), field, vals[0]))
        return vals[0] if vals else None

    nodes = {}
    for iri, acc in seen.items():
        types = sorted(compact(t) for t in acc["type"])
        if args.types and not set(types) & set(args.types):
            continue
        n = {"iri": iri, "type": ",".join(types)}
        v = {f: one(iri, acc, f) for f in ("label", "facet", "bfo", "status", "value", "tag")}
        if v["label"]:
            n["label"] = v["label"][1]
        if v["facet"]:
            n["facet"] = compact(v["facet"])
        if v["bfo"] and v["bfo"].startswith(PREFIXES["obo"]):
            n["bfo"] = v["bfo"][len(PREFIXES["obo"]):]
        elif v["bfo"]:
            warn("%s is grounded in <%s>, outside the obo: namespace" % (iri, v["bfo"]))
        if v["status"]:
            n["status"] = v["status"]
        if v["value"]:
            n["value"] = int(v["value"])
        if v["tag"]:
            n["tag"] = v["tag"]
        n.update(next((by_type[t] for t in types if t in by_type), {}))
        nodes[iri] = n

    # ---- ks_data: literal-valued domain statements ---------------------------
    data = {}
    for r in data_rows:
        iri, val = r["iri"]["value"], r["val"]
        if iri not in nodes:
            continue
        pred = compact(r["pred"]["value"])
        if "xml:lang" in val:
            warn("%s %s \"%s\"@%s — ks_data carries no language tag"
                 % (iri, pred, val["value"], val["xml:lang"]))
        elif ";" in val["value"] or "\n" in val["value"]:
            warn("%s %s — ks_data cannot carry a value containing ';' or a line break" % (iri, pred))
        elif val.get("datatype", XSD_STRING) == XSD_STRING:
            data.setdefault(iri, []).append("%s = %s" % (pred, val["value"]))
        else:
            data.setdefault(iri, []).append("%s %s = %s" % (pred, compact(val["datatype"]), val["value"]))
    for iri, entries in data.items():
        nodes[iri]["data"] = "; ".join(sorted(entries))

    # ---- edges: both ends projected; an untyped end is a reference endpoint --
    edges = []
    for r in edge_rows:
        s, t = r["source"]["value"], r["target"]["value"]
        if any(end not in nodes and end in seen for end in (s, t)):
            continue                                # an end was filtered out by --types
        for end in (s, t):
            nodes.setdefault(end, {"iri": end})     # untyped → reference endpoint
        rel = compact(r["rel"]["value"])
        e = {"rel": rel, "source": s, "target": t}
        e.update(by_rel.get(rel, {}))
        edges.append(e)

    proj = {"nodes": [nodes[i] for i in sorted(nodes)],
            "edges": sorted(edges, key=lambda e: (e["source"], e["rel"], e["target"]))}
    json.dump(proj, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stderr.write("ks_project: %d node(s), %d edge(s)\n" % (len(proj["nodes"]), len(proj["edges"])))


if __name__ == "__main__":
    main()

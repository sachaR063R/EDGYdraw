#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — drawio → Turtle adapter (offline, deterministic, stdlib-only)
# =============================================================================
# One-way capitalisation of an offline draw.io viewpoint into the sovereign RDF
# Knowledge Space, per README.md (the convention spec). Reads a
# .drawio file (uncompressed OR draw.io's deflate+base64 <diagram> body), walks
# every ks_-tagged <object>/<UserObject>, and emits Turtle. The emitted graph is
# judged by rudof against the existing AF1 + E1-E4 cross-domain SHACL floor — NO
# new vocabulary, NO new shapes, NO network.
#
#   ./drawio2ttl.py viewpoints/capability-map.drawio > out.ttl
#   ./drawio2ttl.py viewpoints/capability-map.drawio --prefixes prefixes.ttl > out.ttl
#
# Domain-module prefixes are NOT built in: pass them with --prefixes <file.ttl>
# (repeatable; plain `@prefix p: <iri> .` lines). --ks-ns overrides the
# capitalisation boundary.
#
# Doctrine: RDF is canonical; the diagram is a viewpoint surface. ks_type / ks_rel
# MUST resolve to terms that already exist (zero-mint). A node with ks_iri but no
# ks_type is a reference endpoint (typed in another graph) — it emits no triples.
# =============================================================================
import sys
import os
import re
import base64
import zlib
import urllib.parse
import xml.etree.ElementTree as ET

PREFIXES = {
    "edgy":      "https://schema.bra0.org/cross-domain/edgy#",
    "archimate": "https://purl.org/archimate#",
    "dcterms":   "http://purl.org/dc/terms/",
    "adms":      "http://www.w3.org/ns/adms#",
    "obo":       "http://purl.obolibrary.org/obo/",
    "skos":      "http://www.w3.org/2004/02/skos/core#",
    "rdfs":      "http://www.w3.org/2000/01/rdf-schema#",
    "rdf":       "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd":       "http://www.w3.org/2001/XMLSchema#",
}
# KS_NS is the capitalisation boundary: every ks_iri MUST sit under it. The default
# covers the whole bra0 KS module family (slash- and hash-namespaced modules alike);
# override with --ks-ns for a Knowledge Space hosted elsewhere.
KS_NS = "https://schema.bra0.org/ks-modules/"

_PREFIX_RE = re.compile(r"^\s*@prefix\s+([A-Za-z][\w-]*):\s*<([^>]+)>\s*\.", re.M)


def load_prefixes(path):
    """Merge the `@prefix p: <iri> .` declarations of a Turtle file into PREFIXES.
    A built-in prefix may not be rebound to a different IRI."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        die("cannot read prefixes file %s (%s)" % (path, e))
    for pfx, iri in _PREFIX_RE.findall(text):
        if pfx in PREFIXES and PREFIXES[pfx] != iri:
            die("prefix '%s' in %s rebinds a known prefix (%s)" % (pfx, path, PREFIXES[pfx]))
        PREFIXES[pfx] = iri


def die(msg):
    sys.stderr.write("drawio2ttl: ERROR — %s\n" % msg)
    sys.exit(2)


def graph_models(path):
    """Yield each <mxGraphModel> element, decompressing draw.io bodies if needed."""
    tree = ET.parse(path)
    root = tree.getroot()
    diagrams = root.iter("diagram") if root.tag != "mxGraphModel" else []
    if root.tag == "mxGraphModel":
        yield root
        return
    found = False
    for dia in diagrams:
        model = dia.find("mxGraphModel")
        if model is not None:                       # uncompressed
            found = True
            yield model
        elif (dia.text or "").strip():              # deflate+base64 body
            raw = base64.b64decode(dia.text.strip())
            xml = zlib.decompress(raw, -15).decode("utf-8")
            xml = urllib.parse.unquote(xml)
            found = True
            yield ET.fromstring(xml)
    if not found:
        die("no <mxGraphModel> found in %s" % path)


def resolve_term(token):
    """Local name → edgy:<token> ; CURIE (has ':') → expanded <full-iri>."""
    token = token.strip()
    if ":" in token:
        pfx, local = token.split(":", 1)
        if pfx not in PREFIXES:
            die("unknown prefix '%s' in term '%s'" % (pfx, token))
        return "<%s%s>" % (PREFIXES[pfx], local)
    return "<%s%s>" % (PREFIXES["edgy"], token)


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# ---- UI/presentation layer (ADR-126) ---------------------------------------
# Optional second output: the geometry/style/colour/ring that the content path
# DISCARDS, captured as a *.ui.ttl graph keyed by ui:rendersIndividual (the
# binding). The content stdout path is untouched; this is purely additive.

UI_NS = "https://schema.bra0.org/cross-domain/ui#"
_FILL_RE = re.compile(r"fillColor=(#[0-9A-Fa-f]{3,8})")
_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
# The ratified EDGY facet palette (viewpoint-ui.tbox.ttl ui:canonicalColor). A fill
# in this set is a GOVERNED facet claim → ui:facetColor (judged by colour-is-facet).
# Any other fill (white/neutral/accent) is cosmetic → ui:fillColor (ungoverned): it
# makes no facet claim, so it never trips the law. Compared case-insensitively.
CANONICAL_FACET_COLOURS = frozenset({"#5abb67", "#2d60ad", "#ee2e66"})


def _fill_colour(style):
    if not style:
        return None
    m = _FILL_RE.search(style)
    return m.group(1) if m else None


def emit_ui(nodes, viewpoint):
    """Build the UI-layer Turtle: one ui:Placement per rendered vertex, bound to
    its content individual by ui:rendersIndividual. Geometry/style/colour are
    captured verbatim; nothing here is judged by the content KS_NS boundary."""
    sep = "-" if "#" in viewpoint else "#"
    blocks = []
    for cell_id in sorted(nodes, key=lambda c: nodes[c]["iri"]):
        n = nodes[cell_id]
        iri, a, obj = n["iri"], n["attrs"], n["obj"]
        inner = obj.find("mxCell")
        if inner is None or inner.get("vertex") != "1":
            continue                                # only vertices are placed
        g = inner.find("mxGeometry")
        if g is None:
            continue
        pid = "%s%splacement-%s" % (viewpoint, sep, cell_id)
        props = ["a ui:Placement",
                 "ui:rendersIndividual <%s>" % iri,
                 "ui:inViewpoint <%s>" % viewpoint]
        style = inner.get("style")
        fill = _fill_colour(style)
        if fill:
            if fill.lower() in CANONICAL_FACET_COLOURS:
                props.append('ui:facetColor "%s"' % fill)   # governed facet claim
            else:
                props.append('ui:fillColor "%s"' % fill)    # cosmetic, ungoverned
        if "ks_ring" in a:
            props.append('ui:onRing "%s"' % esc(a["ks_ring"]))
        if style:
            props.append('ui:style "%s"' % esc(style))
        for prop, gattr in (("ui:x", "x"), ("ui:y", "y"), ("ui:w", "width"), ("ui:h", "height")):
            v = (g.get(gattr) or "").strip()
            if _NUM_RE.match(v):
                props.append("%s %s" % (prop, v))
        blocks.append("<%s>\n    %s ." % (pid, " ;\n    ".join(props)))

    out = ["# UI/presentation layer captured from the viewpoint by drawio2ttl.py --ui-out (ADR-126).",
           "# Bound to content by ui:rendersIndividual; judged by ui-binding.shapes.ttl.",
           "@prefix ui: <%s> ." % UI_NS,
           "@prefix rdf: <%s> ." % PREFIXES["rdf"],
           "",
           "<%s> a ui:Viewpoint ." % viewpoint,
           ""]
    out.extend(blocks)
    out.append("")
    return "\n".join(out)


def main(path, ui_out=None, viewpoint=None):
    nodes = {}   # cell_id -> dict(iri, attrs)
    edges = []   # (rel_token, src_cell_id, tgt_cell_id)

    for model in graph_models(path):
        for obj in list(model.iter("object")) + list(model.iter("UserObject")):
            a = obj.attrib
            cell_id = a.get("id")
            inner = obj.find("mxCell")
            if "ks_rel" in a:                       # semantic edge
                if inner is None or inner.get("edge") != "1":
                    die("ks_rel on non-edge object id=%s" % cell_id)
                edges.append((a["ks_rel"], inner.get("source"), inner.get("target")))
            if "ks_iri" in a:                       # node (full or reference)
                nodes[cell_id] = {"iri": a["ks_iri"], "attrs": a, "obj": obj}

    triples = []

    # ---- nodes -------------------------------------------------------------
    for cell_id in sorted(nodes, key=lambda c: nodes[c]["iri"]):
        n = nodes[cell_id]
        iri, a = n["iri"], n["attrs"]
        if not iri.startswith(KS_NS):
            die("ks_iri '%s' is outside the KS namespace %s" % (iri, KS_NS))
        if "ks_type" not in a:
            continue                                # reference endpoint — emits nothing
        s = "<%s>" % iri
        types = [resolve_term(t) for t in a["ks_type"].split(",") if t.strip()]
        triples.append("%s rdf:type %s ." % (s, " , ".join(types)))
        label = a.get("ks_label") or a.get("label")
        if label:
            triples.append('%s rdfs:label "%s"@en .' % (s, esc(label)))
        if "ks_facet" in a:
            triples.append("%s edgy:belongsToFacet %s ." % (s, resolve_term(a["ks_facet"])))
        if "ks_bfo" in a:
            triples.append("%s edgy:groundedInBFO obo:%s ." % (s, a["ks_bfo"]))
        if "ks_status" in a:
            triples.append('%s adms:status "%s" .' % (s, esc(a["ks_status"])))
        if "ks_value" in a:
            v = a["ks_value"].strip()
            if not v.lstrip("-").isdigit():
                die("ks_value '%s' on %s is not an integer" % (v, iri))
            triples.append("%s edgy:hasBusinessValue %s ." % (s, v))
        if "ks_tag" in a:
            triples.append('%s edgy:hasTag "%s" .' % (s, esc(a["ks_tag"])))
        if "ks_data" in a:                          # generic domain datatype props
            for entry in a["ks_data"].split(";"):
                entry = entry.strip()
                if not entry:
                    continue
                if "=" not in entry:
                    die("ks_data entry '%s' on %s lacks '=' (want 'pred [datatype] = value')" % (entry, iri))
                lhs, val = entry.split("=", 1)
                toks = lhs.split()
                val = val.strip()
                if len(toks) == 1:                  # plain string literal
                    obj = '"%s"' % esc(val)
                elif len(toks) == 2:                # explicit datatype (CURIE, or bare → xsd:)
                    dt = toks[1] if ":" in toks[1] else "xsd:" + toks[1]
                    obj = '"%s"^^%s' % (esc(val), resolve_term(dt))
                else:
                    die("ks_data entry '%s' on %s malformed (want 'pred [datatype] = value')" % (entry, iri))
                triples.append("%s %s %s ." % (s, resolve_term(toks[0]), obj))

    # ---- edges -------------------------------------------------------------
    rows = []
    for rel, src, tgt in edges:
        if src not in nodes or tgt not in nodes:
            die("edge ks_rel=%s dangles (source=%s target=%s)" % (rel, src, tgt))
        rows.append("<%s> %s <%s> ." % (nodes[src]["iri"], resolve_term(rel), nodes[tgt]["iri"]))
    triples.extend(sorted(rows))

    out = ["# Capitalised from %s by drawio2ttl.py — DO NOT hand-edit." % path,
           "# RDF is canonical; this is a one-way drawio→RDF capitalisation (README.md)."]
    for p in ("rdf", "rdfs", "edgy", "archimate", "obo", "adms", "dcterms"):
        out.append("@prefix %s: <%s> ." % (p, PREFIXES[p]))
    out.append("")
    out.extend(triples)
    out.append("")
    sys.stdout.write("\n".join(out))

    # ---- UI/presentation layer (ADR-126, optional) -------------------------
    if ui_out is not None:
        if viewpoint is None:
            base = os.path.splitext(os.path.basename(path))[0]
            viewpoint = "https://schema.bra0.org/ks-modules/viewpoints/" + base
        with open(ui_out, "w", encoding="utf-8") as fh:
            fh.write(emit_ui(nodes, viewpoint))


if __name__ == "__main__":
    args = sys.argv[1:]
    path = ui_out = viewpoint = None
    i = 0
    while i < len(args):
        if args[i] == "--ui-out":
            ui_out = args[i + 1]; i += 2
        elif args[i] == "--viewpoint":
            viewpoint = args[i + 1]; i += 2
        elif args[i] == "--prefixes":
            load_prefixes(args[i + 1]); i += 2
        elif args[i] == "--ks-ns":
            KS_NS = args[i + 1]; i += 2
        elif path is None:
            path = args[i]; i += 1
        else:
            die("unexpected argument '%s'" % args[i])
    if path is None:
        die("usage: drawio2ttl.py <file.drawio> [--prefixes <file.ttl>]... [--ks-ns <iri>] "
            "[--ui-out <file.ui.ttl>] [--viewpoint <iri>]")
    main(path, ui_out=ui_out, viewpoint=viewpoint)

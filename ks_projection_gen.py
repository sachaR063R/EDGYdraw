#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — KS projection → draw.io generator (offline, deterministic,
# stdlib-only). The READ-ONLY reverse of drawio2ttl.py, fenced by ADR-124.
# =============================================================================
# Reads a {nodes, edges} JSON projection of the sovereign RDF KS (a SPARQL
# SELECT result) and writes a .drawio whose <object> wrappers carry the full
# ks_* substrate, so drawio2ttl.py round-trips the result LOSSLESSLY.
#
#   ./ks_projection_gen.py projection.json > viewpoint.skeleton.drawio
#
# Doctrine (ADR-124): RDF stays canonical. This emits the SEMANTIC EDGE SKELETON
# (which ks_rel edges exist between which ks_iri nodes) — a derived viewpoint a
# human then arranges (polar EDGY layout) and re-skins. It does NOT regenerate
# authoritative LAYOUT (placement is a scaffold, overridable per node), and it
# MINTS NOTHING — every node/edge must already exist in the KS projection.
#
# Pattern credit: the {nodes,edges}-JSON → .drawio generator SHAPE is inspired
# by `drawio-skill` (MIT, (c) Agents365-ai 2026, github.com/Agents365-ai/
# drawio-skill) per spike 2026-06-13. No code copied; the data model here emits
# <object> wrappers (NOT plain <mxCell>) to preserve KS canonicity.
#
# Round-trip contract: ks_projection_gen.py(P) | drawio2ttl.py == capitalise(P)
# i.e. the projected diagram capitalises back to the triples it came from.
# =============================================================================
import sys
import json
import html

# ----------------------------------------------------------------------------
# JSON input schema (a KS projection; produced by a SPARQL SELECT, see the
# module-specific projection query). Unknown keys are ignored.
#
# {
#   "nodes": [
#     {                         # one per ks_iri to render
#       "iri":   "<full KS IRI>",          # -> ks_iri   (REQUIRED)
#       "type":  "Capability",             # -> ks_type  (CURIE/local; omit for a reference endpoint)
#       "label": "...",                    # -> ks_label
#       "facet": "ArchitectureFacet",      # -> ks_facet
#       "value": 50,                       # -> ks_value (int)
#       "tag":   "ai-unlock:45-55%",       # -> ks_tag
#       "bfo":   "BFO_0000016",            # -> ks_bfo
#       "status":"adopted",                # -> ks_status
#       "data":  "mod:x xsd:integer = 3",   # -> ks_data (verbatim, ';'-separated)
#       "x": 820, "y": 600, "w": 160, "h": 60,  # placeholder geometry (optional)
#       "style": "rounded=1;..."           # optional draw.io style (else neutral default)
#     }
#   ],
#   "edges": [
#     { "rel": "edgy:belongsToFacet", "source": "<iri>", "target": "<iri>", "label": "..." }
#   ]
# }
# ----------------------------------------------------------------------------

DEFAULT_NODE_STYLE = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#262626;"
DEFAULT_EDGE_STYLE = "endArrow=none;html=1;rounded=0;"
DEFAULT_W, DEFAULT_H = 160, 60
GRID_COLS, GRID_DX, GRID_DY, GRID_X0, GRID_Y0 = 6, 200, 110, 40, 40


def die(msg):
    sys.stderr.write("ks_projection_gen: ERROR — %s\n" % msg)
    sys.exit(2)


def attr(s):
    """Escape a value for an XML attribute (double-quoted)."""
    return html.escape(str(s), quote=True)


def main(path):
    try:
        with open(path, encoding="utf-8") as fh:
            proj = json.load(fh)
    except (OSError, ValueError) as e:
        die("cannot read JSON projection %s: %s" % (path, e))

    nodes = proj.get("nodes", [])
    edges = proj.get("edges", [])

    # ---- deterministic ordering & stable cell-ids --------------------------
    nodes = sorted(nodes, key=lambda n: n["iri"])
    iri_seen = {}
    iri_to_id = {}
    for i, n in enumerate(nodes):
        iri = n.get("iri")
        if not iri:
            die("node #%d has no 'iri'" % i)
        if iri in iri_seen:
            die("duplicate node iri '%s' (projection must be 1 node per iri)" % iri)
        iri_seen[iri] = True
        iri_to_id[iri] = "n%d" % i

    edges = sorted(edges, key=lambda e: (e.get("rel", ""), e.get("source", ""), e.get("target", "")))
    for e in edges:
        for end in ("source", "target"):
            if e.get(end) not in iri_to_id:
                die("edge rel=%s %s '%s' is not a projected node (would dangle)"
                    % (e.get("rel"), end, e.get(end)))
        if not e.get("rel"):
            die("edge %s->%s has no 'rel' predicate" % (e.get("source"), e.get("target")))

    # ---- emit --------------------------------------------------------------
    out = []
    out.append('<mxfile host="ks_projection_gen">')
    out.append('  <diagram id="ks-projection" name="KS projection (skeleton — ADR-124)">')
    out.append('    <mxGraphModel dx="1422" dy="900" grid="1" gridSize="10" guides="1" '
               'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
               'pageWidth="1654" pageHeight="1169" math="0" shadow="0">')
    out.append('      <root>')
    out.append('        <mxCell id="0" />')
    out.append('        <mxCell id="1" parent="0" />')

    # nodes
    KS_TO_OBJ = [
        ("type", "ks_type"), ("label", "ks_label"), ("facet", "ks_facet"),
        ("bfo", "ks_bfo"), ("status", "ks_status"), ("value", "ks_value"),
        ("tag", "ks_tag"), ("data", "ks_data"),
    ]
    for i, n in enumerate(nodes):
        cid = iri_to_id[n["iri"]]
        kvs = ['ks_iri="%s"' % attr(n["iri"])]
        for src, ks in KS_TO_OBJ:
            if src in n and n[src] is not None and str(n[src]) != "":
                kvs.append('%s="%s"' % (ks, attr(n[src])))
        # draw.io shows 'label' as the cell caption; mirror ks_label for legibility
        cap = n.get("label", n["iri"])
        kvs.append('label="%s"' % attr(cap))
        x = n.get("x", GRID_X0 + (i % GRID_COLS) * GRID_DX)
        y = n.get("y", GRID_Y0 + (i // GRID_COLS) * GRID_DY)
        w = n.get("w", DEFAULT_W)
        h = n.get("h", DEFAULT_H)
        style = n.get("style", DEFAULT_NODE_STYLE)
        out.append('        <object %s id="%s">' % (" ".join(kvs), cid))
        out.append('          <mxCell style="%s" vertex="1" parent="1">' % attr(style))
        out.append('            <mxGeometry x="%s" y="%s" width="%s" height="%s" as="geometry" />'
                   % (x, y, w, h))
        out.append('          </mxCell>')
        out.append('        </object>')

    # edges
    for j, e in enumerate(edges):
        eid = "e%d" % j
        s_id = iri_to_id[e["source"]]
        t_id = iri_to_id[e["target"]]
        kvs = ['ks_rel="%s"' % attr(e["rel"])]
        if e.get("label"):
            kvs.append('label="%s"' % attr(e["label"]))
        out.append('        <object %s id="%s">' % (" ".join(kvs), eid))
        out.append('          <mxCell style="%s" edge="1" parent="1" source="%s" target="%s">'
                   % (DEFAULT_EDGE_STYLE, s_id, t_id))
        out.append('            <mxGeometry relative="1" as="geometry" />')
        out.append('          </mxCell>')
        out.append('        </object>')

    out.append('      </root>')
    out.append('    </mxGraphModel>')
    out.append('  </diagram>')
    out.append('</mxfile>')
    out.append('')
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        die("usage: ks_projection_gen.py <projection.json>  (writes .drawio to stdout)")
    main(sys.argv[1])

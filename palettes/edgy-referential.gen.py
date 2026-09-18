#!/usr/bin/env python3
# =============================================================================
# EDGY referential — draw.io stencil-library GENERATOR (module-agnostic)
# =============================================================================
# Emits palettes/edgy-referential.library.xml: a draggable, semantically pre-wired
# draw.io library covering the ENTIRETY of the EDGY metamodel —
#   * 16 element stencils   (every edgy:<Element> class; ks_type/ks_facet/ks_bfo/
#                            ks_status pre-filled so a drop is ontologically armed)
#   * 28 connector stencils (every edgy: object property + the 3 core links; each
#                            carries ks_rel AND a VISIBLE rdfs:label on the canvas)
#
# This SUPERSEDES the opaque palettes/edgy-stencils.xml (no titles, no ks_*). The
# library is emitted as PLAIN (un-deflated, un-escaped) mxGraphModel fragments so it
# stays human-readable and evolvable: regenerate to extend, never hand-edit the .xml.
#
#   python3 palettes/edgy-referential.gen.py            # writes the .library.xml
#   python3 palettes/edgy-referential.gen.py --stdout   # print, do not write
#   python3 palettes/edgy-referential.gen.py --edgy-ttl edgy.ttl
#
# The rdfs:comment tooltips are read from edgy.ttl (--edgy-ttl <path>, or $EDGY_TTL;
# published at https://schema.bra0.org/cross-domain/edgy.ttl, CC BY-SA 4.0).
#
# Licensing: this script is MIT OR Apache-2.0, EXCEPT the embedded People image
# (PEOPLE_STYLE), carried verbatim from the EDGY-23 draw.io library (Eero
# Hosiaisluoma 2023, CC BY-SA 4.0). The generated .library.xml is CC BY-SA 4.0.
#
# Doctrine (README.md): RDF is canonical, the diagram is a viewpoint
# surface. ZERO-MINT — every ks_type / ks_rel below is an EXISTING term in
# edgy.ttl (verified against v1.0-draft). The placeholder
# ks_iri sits in the KS namespace and MUST be replaced by the modeller per drop.
#
# Colour IS the facet (ADR-126 colour-is-facet law): the 9 mono-facet elements carry
# the 3 GOVERNED canonical fills (Identity #5ABB67 / Architecture #2D60AD /
# Experience #EE2E66); the 4 base + 3 intersection elements carry cosmetic
# (ungoverned) fills, because they assert no single edgy:belongsToFacet.
# =============================================================================
import json
import os
import re
import sys

KS_NS = "https://schema.bra0.org/ks-modules/"
PLACEHOLDER = KS_NS + "REPLACE-ME#"   # modeller replaces REPLACE-ME + local per drop


EDGY_TTL_URL = "https://schema.bra0.org/cross-domain/edgy.ttl"


def find_edgy_ttl():
    """Locate edgy.ttl — the single source of truth for the rdfs:comment definitions
    injected into tooltips. Order: --edgy-ttl <path>, then $EDGY_TTL, then an
    ontologies/enterprise/edgy.ttl found by walking up from this script."""
    argv = sys.argv[1:]
    if "--edgy-ttl" in argv:
        i = argv.index("--edgy-ttl")
        if i + 1 >= len(argv):
            sys.exit("edgy-referential: --edgy-ttl needs a path")
        return argv[i + 1]
    if os.environ.get("EDGY_TTL"):
        return os.environ["EDGY_TTL"]
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        cand = os.path.join(d, "ontologies", "enterprise", "edgy.ttl")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            sys.exit("edgy-referential: edgy.ttl not found. Fetch the published ontology and "
                     "pass it:\n  curl -sLo edgy.ttl %s\n  python3 %s --edgy-ttl edgy.ttl"
                     % (EDGY_TTL_URL, os.path.basename(__file__)))
        d = parent


def edgy_comments():
    """Return ({class-name: definition}, {property-localname: definition}) parsed from
    edgy.ttl, handling both triple-quoted (classes) and single-quoted (properties)
    rdfs:comment literals, whitespace collapsed for clean single-line tooltips."""
    t = open(find_edgy_ttl(), encoding="utf-8").read()

    def grab(kind):
        d = {}
        for b in re.split(r'\n(?=edgy:\w[\w-]* rdf:type owl:%s)' % kind, t):
            m = re.match(r'edgy:([\w-]+) rdf:type owl:%s' % kind, b)
            if not m:
                continue
            c = (re.search(r'rdfs:comment\s+"""(.*?)"""', b, re.S)
                 or re.search(r'rdfs:comment\s+"(.*?)"(?:@\w+)?\s*[;\.]', b, re.S))
            if c:
                d[m.group(1)] = re.sub(r'\s+', ' ', c.group(1)).strip()
        return d
    return grab("Class"), grab("ObjectProperty")

# ---- canonical facet palette (the 3 GOVERNED dark fills) --------------------
ID_FILL,   ID_FONT   = "#5ABB67", "#0A2E12"   # IdentityFacet     (dark text on green)
ARCH_FILL, ARCH_FONT = "#2D60AD", "#FFFFFF"   # ArchitectureFacet (white text on blue)
EXP_FILL,  EXP_FONT  = "#EE2E66", "#FFFFFF"   # ExperienceFacet   (white text on pink)
BASE_FILL, BASE_FONT = "#F5F5F5", "#262626"   # base elements     (neutral, ungoverned)

# The People hexagon-figure image, carried verbatim from the official EDGY-23 library
# (Eero Hosiaisluoma 2023, CC BY-SA 4.0) so the figure survives the supersede.
PEOPLE_STYLE = (
    "shape=image;aspect=fixed;image=data:image/svg+xml,"
    "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c3ZnIGlkPSJMYXllcl8yIiB4bWxu"
    "cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGRlZnM+PHN0"
    "eWxlPi5jbHMtMXtmaWxsOiNmZmY7fS5jbHMtMiwuY2xzLTN7ZmlsbDojMjYyNjI2O30uY2xzLTN7b3Bh"
    "Y2l0eTowO308L3N0eWxlPjwvZGVmcz48ZyBpZD0iTGF5ZXJfMS0yIj48Zz48cmVjdCBjbGFzcz0iY2xz"
    "LTMiIHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIvPjxnPjxyZWN0IGNsYXNzPSJjbHMtMSIgeD0iMTEiIHk9"
    "IjQiIHdpZHRoPSIxMCIgaGVpZ2h0PSIxNCIgcng9IjUiIHJ5PSI1Ii8+PHBhdGggY2xhc3M9ImNscy0y"
    "IiBkPSJtMTYsMTljLTMuMzA4LDAtNi0yLjY5Mi02LTZ2LTRjMC0zLjMwOCwyLjY5Mi02LDYtNnM2LDIu"
    "NjkyLDYsNnY0YzAsMy4zMDgtMi42OTIsNi02LDZabTAtMTRjLTIuMjA2LDAtNCwxLjc5NC00LDR2NGMw"
    "LDIuMjA2LDEuNzk0LDQsNCw0czQtMS43OTQsNC00di00YzAtMi4yMDYtMS43OTQtNC00LTRaIi8+PC9n"
    "PjxnPjxwYXRoIGNsYXNzPSJjbHMtMSIgZD0ibTQsMjl2LTIuNWMwLTIuNzUsMi4yNS01LDUtNWgxNGMy"
    "Ljc1LDAsNSwyLjI1LDUsNXYyLjVINFoiLz48cGF0aCBjbGFzcz0iY2xzLTIiIGQ9Im0yOSwzMEgzdi0z"
    "LjVjMC0zLjMwOCwyLjY5Mi02LDYtNmgxNGMzLjMwOCwwLDYsMi42OTIsNiw2djMuNVptLTI0LTJoMjJ2"
    "LTEuNWMwLTIuMjA2LTEuNzk0LTQtNC00aC0xNGMtMi4yMDYsMC00LDEuNzk0LTQsNHYxLjVaIi8+PC9n"
    "PjwvZz48L2c+PC9zdmc+;"
    "strokeColor=#262626;strokeWidth=2;fontSize=14;fontColor=#262626;verticalAlign=top;"
    "labelPosition=center;verticalLabelPosition=bottom;align=center;whiteSpace=wrap;"
    "spacingBottom=0;spacingTop=-7;html=1;"
)

# ---- the 16 EDGY elements ---------------------------------------------------
# (name, archetype, fill, font, ks_facet | None, bfo)  — archetype ∈ outcome|activity|object|people
# bfo from ontologies/alignments/ontoledgy-bfo-alignment.ttl (class-level grounding).
ELEMENTS = [
    # base (no facet, neutral fill — ungoverned)
    ("People",       "people",   BASE_FILL, BASE_FONT, None,                "BFO_0000040"),
    ("Outcome",      "outcome",  BASE_FILL, BASE_FONT, None,                "BFO_0000020"),
    ("Activity",     "activity", BASE_FILL, BASE_FONT, None,                "BFO_0000015"),
    ("Object",       "object",   BASE_FILL, BASE_FONT, None,                "BFO_0000040"),
    # Identity facet (governed green)
    ("Purpose",      "outcome",  ID_FILL,   ID_FONT,   "IdentityFacet",     "BFO_0000034"),
    ("Story",        "activity", ID_FILL,   ID_FONT,   "IdentityFacet",     "BFO_0000031"),
    ("Content",      "object",   ID_FILL,   ID_FONT,   "IdentityFacet",     "BFO_0000031"),
    # Architecture facet (governed blue)
    ("Capability",   "outcome",  ARCH_FILL, ARCH_FONT, "ArchitectureFacet", "BFO_0000016"),
    ("Process",      "activity", ARCH_FILL, ARCH_FONT, "ArchitectureFacet", "BFO_0000015"),
    ("Asset",        "object",   ARCH_FILL, ARCH_FONT, "ArchitectureFacet", "BFO_0000040"),
    # Experience facet (governed pink)
    ("Task",         "outcome",  EXP_FILL,  EXP_FONT,  "ExperienceFacet",   "BFO_0000020"),
    ("Journey",      "activity", EXP_FILL,  EXP_FONT,  "ExperienceFacet",   "BFO_0000015"),
    ("Channel",      "object",   EXP_FILL,  EXP_FONT,  "ExperienceFacet",   "BFO_0000040"),
    # intersection (no single facet → intersectsWith at class level; cosmetic tints)
    ("Organization", "object",   "#80EAFF", "#262626", None,                "BFO_0000027"),
    ("Product",      "object",   "#E599FF", "#262626", None,                "BFO_0000040"),
    ("Brand",        "object",   "#FFD580", "#262626", None,                "BFO_0000031"),
]

# ---- the 28 EDGY connectors -------------------------------------------------
# (ks_rel local-name, visible canvas label = edgy rdfs:label, domain→range, arrow)
# arrow ∈ none|flow|tree|block.  rel + label verified against edgy.ttl v1.0-draft.
CONNECTORS = [
    # core
    ("link",            "link",           "Element→Element",                "none"),
    ("flow",            "flow",           "Element→Element",                "flow"),
    ("tree",            "tree",           "Element→Element",                "tree"),
    # people-domain
    ("achieves",        "achieves",       "People→Outcome",                 "block"),
    ("co-creates",      "co-creates",     "People→Capability",              "block"),
    ("performs",        "performs",       "People→Activity",                "block"),
    ("pursues",         "pursues",        "Organization→Purpose",           "block"),
    # identity facet
    ("contextualizes",  "contextualizes", "Story→Purpose",                  "block"),
    ("conveys",         "conveys",        "Content→Story",                  "block"),
    ("expresses",       "expresses",      "Content→Purpose",                "block"),
    ("authors",         "authors",        "Organization→Story",             "block"),
    # architecture facet
    ("realizes",        "realises",       "Process→Capability",             "block"),
    ("requires",        "requires",       "Process|Product|Capability→Capability|Asset", "block"),
    ("has",             "has",            "Organization→Capability",        "block"),
    # experience facet
    ("traverses",       "traverses",      "Journey→Channel",                "block"),
    ("isPartOf",        "is part of",     "Task→Journey",                   "block"),
    ("serves",          "serves",         "Product→Task",                   "block"),
    ("appearsIn",       "appears in",     "Brand→Journey",                  "block"),
    ("featuresIn",      "features in",    "Product→Journey",                "block"),
    # intersection / cross-facet
    ("builds",          "builds",         "Organization→Brand",             "block"),
    ("makes",           "makes",          "Organization→Product",           "block"),
    ("performsProcess", "performs",       "Organization→Process",           "block"),
    ("embodies",        "embodies",       "Product→Brand",                  "block"),
    ("evokes",          "evokes",         "Brand→Story",                    "block"),
    ("represents",      "represents",     "Brand→Purpose",                  "block"),
    # generic
    ("creates",         "creates",        "Process→Product",                "block"),
    ("uses",            "uses",           "People|Activity|Task→Object|Channel", "block"),
    ("supports",        "supports",       "Brand→Task",                     "block"),
]

ARROWS = {
    "none":  "endArrow=none;",
    "flow":  "endArrow=blockThin;endFill=1;",
    "tree":  "endArrow=diamondThin;endFill=0;",
    "block": "endArrow=block;endFill=1;",
}


def xesc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def slug(name):
    return name.lower().replace(" ", "-")


def elem_style(arch, fill, font):
    if arch == "people":
        return PEOPLE_STYLE
    base = ("html=1;whiteSpace=wrap;strokeColor=#FFFFFF;strokeWidth=2;"
            "fillColor=%s;fontColor=%s;fontSize=14;" % (fill, font))
    if arch == "outcome":
        return "rounded=1;" + base
    if arch == "object":
        return "rounded=0;" + base
    if arch == "activity":
        return "shape=mxgraph.arrows2.arrow;dx=22;notch=0;" + base
    raise ValueError("unknown archetype %r" % arch)


def element_entry(name, arch, fill, font, facet, bfo, definition="", where_used=""):
    """One library entry: an <object> pre-wired with the EDGY semantics so a drop is
    ontologically armed (ks_type/ks_facet/ks_bfo/ks_status), wearing its facet style.
    The hover tooltip (title) carries the EDGY class rdfs:comment definition. The
    optional where_used overlay (L2-only) appends the KS individuals instantiating the
    class — empty here (def-only, module-agnostic)."""
    attrs = [
        ('label', name),
        ('ks_iri', PLACEHOLDER + slug(name) + "-1"),
        ('ks_type', name),
        ('ks_label', name),
    ]
    if facet:
        attrs.append(('ks_facet', facet))
    attrs.append(('ks_bfo', bfo))
    attrs.append(('ks_status', 'candidate'))
    attr_str = " ".join('%s="%s"' % (k, xesc(v)) for k, v in attrs)
    w, h = (50, 50) if arch == "people" else (130, 80)
    xml = (
        '<mxGraphModel><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<object %s id="2">'
        '<mxCell style="%s" vertex="1" parent="1">'
        '<mxGeometry width="%d" height="%d" as="geometry"/>'
        '</mxCell></object>'
        '</root></mxGraphModel>'
        % (attr_str, xesc(elem_style(arch, fill, font)), w, h)
    )
    facet_tag = facet.replace("Facet", "") if facet else ("intersection"
                 if name in ("Organization", "Product", "Brand") else "base")
    title = "%s  ·  %s" % (name, facet_tag)
    if definition:
        title += "  —  " + definition
    if where_used:
        title += "  ⟢ " + where_used
    return {"xml": xml, "w": w, "h": h, "aspect": "fixed", "title": title}


def connector_entry(rel, label, signature, arrow, definition="", where_used=""):
    """One library entry: an edge pre-wired with ks_rel AND a VISIBLE label (the EDGY
    rdfs:label), so the object property is explicit and readable on the canvas.
    The hover tooltip (title) carries the EDGY object-property rdfs:comment definition.
    The optional where_used overlay (L2-only) appends the KS edges using the property."""
    style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeWidth=2;"
             "strokeColor=#262626;fontSize=11;fontColor=#262626;" + ARROWS[arrow])
    xml = (
        '<mxGraphModel><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<object label="%s" ks_rel="%s" id="2">'
        '<mxCell style="%s" edge="1" parent="1">'
        '<mxGeometry relative="1" as="geometry">'
        '<mxPoint x="0" y="40" as="sourcePoint"/>'
        '<mxPoint x="120" y="40" as="targetPoint"/>'
        '</mxGeometry></mxCell></object>'
        '</root></mxGraphModel>'
        % (xesc(label), xesc(rel), xesc(style))
    )
    title = "%s  ·  %s" % (label, signature)
    if definition:
        title += "  —  " + definition
    if where_used:
        title += "  ⟢ " + where_used
    return {"xml": xml, "w": 120, "h": 80, "aspect": "variable", "title": title}


def build(elem_where_used=None, conn_where_used=None):
    """Assemble the <mxlibrary>. With no overlays this is the L0 def-only referential.
    An L2 generator passes elem_where_used / conn_where_used ({name: where-used line})
    to compose the same entries with a KS where-used overlay — no entry-builder
    duplication (generic vs. module vs. client layering)."""
    elem_where_used = elem_where_used or {}
    conn_where_used = conn_where_used or {}
    class_defs, prop_defs = edgy_comments()
    entries = [element_entry(*e, definition=class_defs.get(e[0], ""),
                             where_used=elem_where_used.get(e[0], "")) for e in ELEMENTS]
    entries += [connector_entry(*c, definition=prop_defs.get(c[0], ""),
                                where_used=conn_where_used.get(c[0], "")) for c in CONNECTORS]
    return "<mxlibrary>" + json.dumps(entries, separators=(",", ":")) + "</mxlibrary>\n"


def main():
    out = build()
    if "--stdout" in sys.argv[1:]:
        sys.stdout.write(out)
        return
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "edgy-referential.library.xml")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(out)
    sys.stderr.write(
        "edgy-referential: wrote %s\n  %d element stencils + %d connector stencils = %d entries\n"
        % (dst, len(ELEMENTS), len(CONNECTORS), len(ELEMENTS) + len(CONNECTORS)))


if __name__ == "__main__":
    main()

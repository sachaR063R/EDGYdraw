# EDGYdraw

A two-way bridge between [draw.io](https://www.drawio.com/) diagrams and RDF Knowledge Spaces
modelled with [EDGY](https://enterprise.design/) (Enterprise Design Graph InterplaY).

- **Knowledge Space → diagram.** Project instances of an Enterprise Design Knowledge Space model
  into a `.drawio` file whose shapes carry their semantics.
- **Diagram → Knowledge Space.** Draw with the EDGY stencil library in draw.io desktop, then extract
  the diagram into Turtle to create or enrich a Knowledge Space that follows the same model.

RDF stays the source of truth. A `.drawio` file is a viewpoint on it.

## How it works

draw.io stores custom data as XML attributes on a shape (*Edit > Edit Data*). Every attribute the
bridge reads is prefixed `ks_`. A shape without `ks_` attributes is decorative and ignored, so a
whiteboard can mix committed model elements with free sketching.

| Attribute | On | Emits |
|---|---|---|
| `ks_iri` | node (required) | the subject IRI; must sit under the Knowledge Space namespace |
| `ks_type` | node | `rdf:type` — an EDGY class local name (`Capability`) or a CURIE |
| `ks_label` | node | `rdfs:label "…"@en` (falls back to the shape text) |
| `ks_facet` | node | `edgy:belongsToFacet` — `IdentityFacet`, `ArchitectureFacet`, `ExperienceFacet` |
| `ks_bfo` | node | `edgy:groundedInBFO obo:<id>` |
| `ks_status` | node | `adms:status` |
| `ks_value` | node | `edgy:hasBusinessValue` (integer) |
| `ks_tag` | node | `edgy:hasTag` |
| `ks_data` | node | domain datatype triples: `pred [datatype] = value; …` |
| `ks_rel` | edge | the predicate between the two nodes' `ks_iri` — EDGY local name or CURIE |

The bridge mints no vocabulary: `ks_type` and `ks_rel` must name terms that already exist in the
EDGY ontology (`https://schema.bra0.org/cross-domain/edgy#`) or in a domain module you declare.
A node with `ks_iri` and no `ks_type` is a reference endpoint: edges may attach to it, it emits no
triples of its own.

## Contents

| Path | Role |
|---|---|
| `palettes/edgy-referential.library.xml` | draw.io library: 16 EDGY element stencils + 28 connector stencils, each pre-wired with `ks_*` and a definition tooltip |
| `palettes/edgy-referential.gen.py` | generator of that library (regenerate, never hand-edit the `.xml`) |
| `ks_projection_gen.py` | Knowledge Space projection (JSON) → `.drawio` |
| `drawio2ttl.py` | `.drawio` → Turtle |
| `drawio_lint.py` | structural lint of a `.drawio` before extraction |
| `roundtrip.sh` | extract a viewpoint, then validate the Turtle with SHACL (rudof) |
| `coach.py` | learner-facing report over the same checks plus SPARQL guards (English/French) |
| `examples/bakery/` | a small neutral example, both directions |

## Quick start

Python 3 standard library only for the generators, the extractor and the lint.

```sh
# 1. Load the stencils: draw.io desktop > File > Open Library from > Device
#    > palettes/edgy-referential.library.xml
#    Drop a stencil, then replace REPLACE-ME in its ks_iri (Edit Data).

# 2. Knowledge Space -> diagram
./ks_projection_gen.py examples/bakery/projection.json > bakery.drawio

# 3. Diagram -> Knowledge Space
./drawio_lint.py bakery.drawio
./drawio2ttl.py bakery.drawio --prefixes examples/bakery/prefixes.ttl > bakery.ttl
```

`projection.json` is a `{nodes, edges}` document, typically the result of a SPARQL SELECT over the
Knowledge Space; its schema is documented at the top of `ks_projection_gen.py`. The generator places
nodes on a grid: it produces the semantic skeleton, and a person arranges the layout in draw.io.
Re-styling or moving a shape never changes the extracted Turtle, since the extractor reads `ks_*`
only.

Domain-module vocabularies are declared in a Turtle file of `@prefix` lines passed with
`--prefixes` (repeatable). `--ks-ns <iri>` moves the namespace boundary that every `ks_iri` must
sit under (default `https://schema.bra0.org/ks-modules/`).

SHACL validation and the coach need [rudof](https://github.com/rudof-project/rudof) and
[oxigraph](https://github.com/oxigraph/oxigraph) on the `PATH`:

```sh
KS_PREFIXES=examples/bakery/prefixes.ttl ./roundtrip.sh bakery.drawio <shapes.ttl> [support.ttl ...]
```

Regenerating the stencil library reads the EDGY ontology for its tooltips:

```sh
curl -sLo edgy.ttl https://schema.bra0.org/cross-domain/edgy.ttl
python3 palettes/edgy-referential.gen.py --edgy-ttl edgy.ttl
```

## Status

`0.1.0-draft`.

- Verified: the bakery example round-trips (projection → `.drawio` → lint → Turtle) deterministically,
  and the stencil library regenerates byte-identically from the published EDGY ontology.
- Not covered yet: merging extracted Turtle into an existing Knowledge Space (the extractor emits a
  standalone graph), a generic SPARQL query producing `projection.json`, automatic diagram layout,
  and the UI-layer validation behind `drawio2ttl.py --ui-out` (its vocabulary is unpublished).

## Licensing

Dual-licensed MIT OR Apache-2.0 (see `LICENSE-MIT`, `LICENSE-APACHE`).

Individual files may carry a distinct license header. Content derived from EDGY material is
CC-BY-SA-4.0, as required by the share-alike terms of its sources:

- `palettes/edgy-referential.library.xml` — CC-BY-SA-4.0. Tooltips quote the EDGY ontology
  (CC-BY-SA-4.0); the People figure comes from the "EDGY 23" draw.io stencils by Eero Hosiaisluoma
  (2023, CC-BY-SA-4.0). The same embedded figure inside `palettes/edgy-referential.gen.py` keeps
  that license.
- EDGY is a creation of the [Intersection Group](https://intersection.group/), published under
  CC-BY-SA-4.0.

The shape of the `{nodes, edges}` JSON → `.drawio` generator was inspired by
[drawio-skill](https://github.com/Agents365-ai/drawio-skill) (MIT); no code was copied.

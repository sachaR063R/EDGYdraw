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
| `ks_project.py` | Knowledge Space (RDF files) → `projection.json`, through the generic SPARQL queries |
| `queries/projection-*.rq` | the three generic SELECTs: nodes, edges, domain data |
| `ks_projection_gen.py` | `projection.json` → `.drawio` |
| `drawio2ttl.py` | `.drawio` → Turtle |
| `ks_merge.py` | merge the extracted Turtle into an existing Knowledge Space (additive, conflicts reported) |
| `drawio_lint.py` | structural lint of a `.drawio` before extraction |
| `roundtrip.sh` | extract a viewpoint, then validate the Turtle with SHACL (rudof) |
| `coach.py` | learner-facing report over the same checks plus SPARQL guards (English/French) |
| `examples/bakery/` | a small neutral example: both directions, then a merge into `ks.ttl` |

## Quick start

Python 3 standard library only for the generators, the extractor and the lint; the projection and
the merge also call the oxigraph CLI.

```sh
# 1. Load the stencils: draw.io desktop > File > Open Library from > Device
#    > palettes/edgy-referential.library.xml
#    Drop a stencil, then replace REPLACE-ME in its ks_iri (Edit Data).

# 2. Knowledge Space -> diagram
./ks_project.py --ks examples/bakery/ks.ttl --prefixes examples/bakery/prefixes.ttl > projection.json
./ks_projection_gen.py projection.json > ks-view.drawio

# 3. Diagram -> Knowledge Space (bakery.skeleton.drawio stands for a diagram someone drew)
cp examples/bakery/bakery.skeleton.drawio bakery.drawio
./drawio_lint.py bakery.drawio
./drawio2ttl.py bakery.drawio --prefixes examples/bakery/prefixes.ttl > bakery.ttl

# 4. Enrich an existing Knowledge Space (dry run, then append to a working copy)
cp examples/bakery/ks.ttl my-ks.ttl
./ks_merge.py bakery.ttl --ks my-ks.ttl
./ks_merge.py bakery.ttl --ks my-ks.ttl --append-to my-ks.ttl
```

### Projecting a Knowledge Space

`ks_project.py` loads the Knowledge Space file(s) given by `--ks` and runs the three queries of
`queries/`: every typed individual under the Knowledge Space namespace becomes a node, every
statement linking two of them an edge, and their literal-valued domain statements ride along as
`ks_data`. `--types Capability Process` narrows the viewpoint to some classes; an untyped edge end
is kept as a reference endpoint. The queries are plain SPARQL and run in any engine: edit their
`VALUES ?ns` line to change the namespace by hand.

Terms are compacted the way the extractor expands them (EDGY local name, or a CURIE over a prefix
declared with `--prefixes`); a term with no declared prefix is an error. Each node and edge borrows
the style, size and visible label of its stencil in the EDGY library, so the projection opens as an
EDGY diagram where colour is facet. A label in a language other than English is not projected, and
a language-tagged data literal is reported and left out, since `ks_*` cannot carry them.

`projection.json` is a `{nodes, edges}` document whose schema is documented at the top of
`ks_projection_gen.py`; it can also be written by hand (`examples/bakery/projection.json`). The
generator places nodes on a grid: it produces the semantic skeleton, edges may cross shapes, and a
person arranges the layout in draw.io.
Re-styling or moving a shape never changes the extracted Turtle, since the extractor reads `ks_*`
only.

Domain-module vocabularies are declared in a Turtle file of `@prefix` lines passed with
`--prefixes` (repeatable). `--ks-ns <iri>` moves the namespace boundary that every `ks_iri` must
sit under (default `https://schema.bra0.org/ks-modules/`).

### Merging into an existing Knowledge Space

`ks_merge.py` compares the extracted graph with the Knowledge Space file(s) given by `--ks` and
keeps the triples the Knowledge Space does not hold yet. Without an output option it prints that
delta and a report; `--out <file>` writes it as a separate graph; `--append-to <file.ttl>` appends
it as a dated block at the end of a Knowledge Space file.

- **The merge only adds.** A diagram is a partial viewpoint: what it omits is left untouched in the
  Knowledge Space.
- **The Knowledge Space wins a conflict.** Labels (per language), `adms:status`,
  `edgy:hasBusinessValue`, `edgy:belongsToFacet` and `edgy:groundedInBFO` are treated as
  single-valued (extend with `--single-valued <iri>`). When the diagram disagrees with the Knowledge
  Space on one of them, the triple is withheld and reported, and the exit code is 1. Resolve it by
  hand, in the Knowledge Space or in the diagram.
- No existing statement is rewritten, and running the merge twice adds nothing the second time.

On the bakery example: 36 extracted triples, 11 already known, 23 added, 2 conflicts withheld (a
label and a status the hand-authored `ks.ttl` states differently).

`ks_project.py` and `ks_merge.py` need the [oxigraph](https://github.com/oxigraph/oxigraph) CLI on
the `PATH` to parse and query RDF. SHACL validation and the coach need [rudof](https://github.com/rudof-project/rudof) and
oxigraph on the `PATH`:

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
  merges into `examples/bakery/ks.ttl` idempotently with its two conflicts reported, the merged
  Knowledge Space survives Knowledge Space → projection → `.drawio` → Turtle unchanged (39 triples,
  identical graphs), and the stencil library regenerates byte-identically from the published EDGY ontology.
- Not covered yet: retracting or replacing Knowledge Space statements from a diagram (the merge is
  additive), automatic diagram layout (the projection is laid out on a grid),
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

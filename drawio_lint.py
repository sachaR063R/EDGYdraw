#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — pre-emission structural linter (offline, stdlib-only).
# =============================================================================
# Checks a .drawio BEFORE capitalisation, so authoring errors surface with a
# clear message instead of an opaque drawio2ttl.py die() mid-extraction. It
# strengthens the option-A validation gate and the method-C re-validation step
# (ADR-124). It is a SYNTACTIC/STRUCTURAL gate only — rudof/SHACL remains the
# semantic judge of the emitted TTL.
#
#   ./drawio_lint.py viewpoints/capability-map.drawio
#
# Exit 0 = no errors (warnings allowed); exit 1 = errors found.
#
# Checks:
#   E1  duplicate ks_iri across semantic nodes (ks_iri + ks_type)
#   E2  ks_rel on a non-edge object
#   E3  ks_rel edge whose source/target cell is missing, or lacks ks_iri (dangles)
#   W1  two vertices with overlapping bounding boxes (visual only — warning)
#
# Pattern credit: the pre-emission structural-linter idea is inspired by
# `drawio-skill` (MIT, (c) Agents365-ai 2026) per spike 2026-06-13. No code
# copied; the checks here are specific to the ks_* substrate.
# =============================================================================
import sys
import base64
import zlib
import urllib.parse
import xml.etree.ElementTree as ET


def graph_models(path):
    """Yield each <mxGraphModel>, decompressing draw.io bodies if needed
    (same decode contract as drawio2ttl.py)."""
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag == "mxGraphModel":
        yield root
        return
    for dia in root.iter("diagram"):
        model = dia.find("mxGraphModel")
        if model is not None:
            yield model
        elif (dia.text or "").strip():
            raw = base64.b64decode(dia.text.strip())
            xml = urllib.parse.unquote(zlib.decompress(raw, -15).decode("utf-8"))
            yield ET.fromstring(xml)


def geom(cell):
    g = cell.find("mxGeometry")
    if g is None:
        return None
    try:
        return (float(g.get("x", 0)), float(g.get("y", 0)),
                float(g.get("width", 0)), float(g.get("height", 0)))
    except ValueError:
        return None


def overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def main(path):
    errors, warnings = [], []
    cells_by_id = {}      # cell_id -> ks_iri (or None)
    iri_count = {}        # ks_iri -> [cell_ids] (semantic nodes only)
    boxes = []            # (cell_id, label, geom) for vertices

    for model in graph_models(path):
        for obj in list(model.iter("object")) + list(model.iter("UserObject")):
            a = obj.attrib
            cid = a.get("id")
            inner = obj.find("mxCell")
            cells_by_id[cid] = a.get("ks_iri")
            if "ks_iri" in a and "ks_type" in a:
                iri_count.setdefault(a["ks_iri"], []).append(cid)
            if "ks_rel" in a:                                    # E2 / E3
                if inner is None or inner.get("edge") != "1":
                    errors.append("E2  ks_rel on non-edge object id=%s (rel=%s)"
                                  % (cid, a.get("ks_rel")))
                else:
                    for end in ("source", "target"):
                        ref = inner.get(end)
                        if ref is None:
                            errors.append("E3  ks_rel=%s edge id=%s has no %s"
                                          % (a["ks_rel"], cid, end))
            if inner is not None and inner.get("vertex") == "1":
                g = geom(inner)
                if g:
                    boxes.append((cid, a.get("ks_label") or a.get("label") or cid, g))

    # E1 — duplicate ks_iri
    for iri, ids in sorted(iri_count.items()):
        if len(ids) > 1:
            errors.append("E1  duplicate ks_iri '%s' on %d nodes (%s)"
                          % (iri, len(ids), ", ".join(ids)))

    # E3 (second pass) — edge ends must resolve to a cell carrying ks_iri
    for model in graph_models(path):
        for obj in list(model.iter("object")) + list(model.iter("UserObject")):
            a = obj.attrib
            if "ks_rel" not in a:
                continue
            inner = obj.find("mxCell")
            if inner is None or inner.get("edge") != "1":
                continue
            for end in ("source", "target"):
                ref = inner.get(end)
                if ref is None:
                    continue
                if ref not in cells_by_id:
                    errors.append("E3  ks_rel=%s edge id=%s %s '%s' references a missing cell"
                                  % (a["ks_rel"], a.get("id"), end, ref))
                elif cells_by_id[ref] is None:
                    errors.append("E3  ks_rel=%s edge id=%s %s '%s' points at a cell with no ks_iri"
                                  % (a["ks_rel"], a.get("id"), end, ref))

    # W1 — overlapping vertices (visual only)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if overlap(boxes[i][2], boxes[j][2]):
                warnings.append("W1  overlap: '%s' (%s) and '%s' (%s)"
                                % (boxes[i][1], boxes[i][0], boxes[j][1], boxes[j][0]))

    for w in warnings:
        sys.stderr.write("drawio_lint: WARN  %s\n" % w)
    for e in errors:
        sys.stderr.write("drawio_lint: ERROR %s\n" % e)
    sys.stderr.write("drawio_lint: %s — %d error(s), %d warning(s)\n"
                     % (path, len(errors), len(warnings)))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("usage: drawio_lint.py <file.drawio>\n")
        sys.exit(2)
    main(sys.argv[1])

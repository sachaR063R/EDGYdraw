#!/usr/bin/env python3
# =============================================================================
# Diagram Bridge — bi-surface Knowledge Space COACH (generic L0 engine)
# =============================================================================
# A learner-facing coach, NOT a bare validator. It capitalises an offline
# draw.io viewpoint and reports back kindly, in business terms, on TWO surfaces:
#
#   FLOOR        — rudof SHACL: structural / cardinality / range conformance.
#   SUITABILITY  — oxigraph SPARQL guards: cross-node business rules that the
#                  SHACL-Core floor cannot express (rudof 0.2.8 silently skips
#                  sh:sparql, so a green floor is NOT proof of suitability — a
#                  false green would betray the learner. The two surfaces are
#                  run separately and reported separately. This is the honesty
#                  contract: rudof decides the floor verdict, oxigraph decides
#                  the suitability verdict; this script orchestrates and phrases,
#                  it never invents a verdict.)
#
# Fault-tolerant by construction: a malformed diagram yields a kind message and
# a fix hint, NEVER a Python traceback or a tool stderr dump.
#
# Bilingual (FR/EN): learner-facing text is rendered in English, French, or both
# (default). The workshop audience is bilingual; --lang selects the surface.
#
#   coach.py <viewpoint.drawio> --shapes <s.ttl> \
#            [--support tbox1.ttl tbox2.ttl ...] \
#            [--guard guard1.rq guard2.rq ...] \
#            [--lang en|fr|both]
#
# Each --guard is a SPARQL SELECT that MUST return zero rows on a healthy KS;
# any returned row is a flagged business concern. A guard may carry a learner
# message on a line of the form:  #@coach <english message>
# and, optionally, a French one on:  #@coach.fr <message français>
#
# Exit: 0 all clear · 1 floor violation(s) · 2 diagram could not be read ·
#       3 floor clean but suitability flag(s).
# Engine binaries: rudof (SHACL) + oxigraph (SPARQL) — both sovereign, offline.
# stdlib only; no third-party Python.
# =============================================================================
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTER = os.path.join(HERE, "drawio2ttl.py")
PREFIX_FILES = []   # set in main() from --prefixes; forwarded to the adapter
RUDOF = os.environ.get("RUDOF", "rudof")
OXIGRAPH = os.environ.get("OXIGRAPH", "oxigraph")
PYTHON = os.environ.get("PYTHON", sys.executable or "python3")

# Active output languages, set in main() from --lang. Order = render order.
LANGS = ["en", "fr"]


# ----------------------------------------------------------------------------
# bilingual message catalogue
# ----------------------------------------------------------------------------
# Each key holds {"en": ..., "fr": ...}. `%` placeholders are filled at emit
# time and must match between the two languages.
MSG = {
    "header":            {"en": "KNOWLEDGE SPACE COACH — %s",
                          "fr": "COACH ESPACE DE CONNAISSANCE — %s"},
    "step1_label":       {"en": "1. Reading your diagram",
                          "fr": "1. Lecture de votre schéma"},
    "step1_ok":          {"en": "ok", "fr": "ok"},
    "step1_fail":        {"en": "could not read it",
                          "fr": "lecture impossible"},
    "nothing_changed":   {"en": "Nothing was changed. Fix the point above and run the coach again.",
                          "fr": "Rien n'a été modifié. Corrigez le point ci-dessus puis relancez le coach."},
    "step2_label":       {"en": "2. Checking structure (floor)",
                          "fr": "2. Vérification de la structure (socle)"},
    "step2_could_not":   {"en": "could not check", "fr": "vérification impossible"},
    "step2_conforms":    {"en": "conforms", "fr": "conforme"},
    "step2_issues":      {"en": "%d issue(s) to fix", "fr": "%d point(s) à corriger"},
    "step3_label":       {"en": "3. Checking business rules",
                          "fr": "3. Vérification des règles métier"},
    "step3_no_rules":    {"en": "no rules supplied", "fr": "aucune règle fournie"},
    "step3_could_not":   {"en": "could not check", "fr": "vérification impossible"},
    "step3_all_clear":   {"en": "all clear", "fr": "tout est conforme"},
    "step3_review":      {"en": "%d point(s) to review", "fr": "%d point(s) à revoir"},
    "structure_header":  {"en": "STRUCTURE — these must be fixed:",
                          "fr": "STRUCTURE — à corriger :"},
    "structure_value":   {"en": "On '%s', the field '%s' = %s is not allowed — %s.",
                          "fr": "Sur « %s », le champ « %s » = %s n'est pas autorisé — %s."},
    "structure_novalue": {"en": "On '%s' (%s) — %s.",
                          "fr": "Sur « %s » (%s) — %s."},
    "structure_fix":     {"en": "Fix: open these boxes in your diagram and adjust the flagged values.",
                          "fr": "Correction : ouvrez ces boîtes dans votre schéma et ajustez les valeurs signalées."},
    "business_header":   {"en": "BUSINESS RULES — please review (these are not blocking, but matter):",
                          "fr": "RÈGLES MÉTIER — à examiner (non bloquant, mais important) :"},
    "business_footnote": {"en": "These come from SPARQL business checks that the structural floor cannot see.",
                          "fr": "Elles proviennent de contrôles métier SPARQL que le socle structurel ne voit pas."},
    "allclear_lead":     {"en": "ALL CLEAR. Your drawing is now a queryable knowledge space —",
                          "fr": "TOUT EST CONFORME. Votre dessin est désormais un espace de connaissance interrogeable —"},
    "allclear_census":   {"en": "%d entities and %d relationships captured.",
                          "fr": "%d entités et %d relations capturées."},
    "allclear_plain":    {"en": "ALL CLEAR. Your drawing is now a queryable knowledge space.",
                          "fr": "TOUT EST CONFORME. Votre dessin est désormais un espace de connaissance interrogeable."},
    "allclear_backstage": {"en": "Backstage, bra0 turned it into RDF and checked it on two "
                                 "surfaces (SHACL structure + SPARQL business rules).",
                           "fr": "En coulisses, bra0 l'a transformé en RDF et vérifié sur deux "
                                 "surfaces (structure SHACL + règles métier SPARQL)."},
    "action_needed":     {"en": "ACTION NEEDED: fix the structure points above, then run again.",
                          "fr": "ACTION REQUISE : corrigez les points de structure ci-dessus, puis relancez."},
    "almost_there":      {"en": "ALMOST THERE: the structure is clean; please review the business points above.",
                          "fr": "PRESQUE : la structure est propre ; examinez les points métier ci-dessus."},
    "read_fail_generic": {"en": "Your diagram could not be read. Please check that it is a valid "
                                "draw.io file and that every semantic box has a name.",
                          "fr": "Votre schéma n'a pas pu être lu. Vérifiez qu'il s'agit d'un fichier "
                                "draw.io valide et que chaque boîte sémantique porte un nom."},
    "capitalise_fail":   {"en": "The diagram could not be capitalised: %s",
                          "fr": "Le schéma n'a pas pu être capitalisé : %s"},
    "guard_generic":     {"en": "Business rule: %s", "fr": "Règle métier : %s"},
    "safety_net":        {"en": "The coach hit an unexpected problem and stopped safely. Nothing was "
                                "changed. Please tell the workshop facilitator.",
                          "fr": "Le coach a rencontré un problème inattendu et s'est arrêté sans risque. "
                                "Rien n'a été modifié. Merci de prévenir l'animateur."},
}

# Structural-error translations: (regex, {"en": template, "fr": template}).
# Templates may carry {0} placeholders filled from the regex groups.
STRUCTURAL = [
    (r"outside the KS namespace",
     {"en": "One box has an identity (ks_iri) outside the knowledge space. Use an id under "
            "https://schema.bra0.org/ks-modules/ — or drag it from the palette.",
      "fr": "Une boîte a une identité (ks_iri) hors de l'espace de connaissance. Utilisez un id sous "
            "https://schema.bra0.org/ks-modules/ — ou glissez-la depuis la palette."}),
    (r"unknown prefix '([^']+)'",
     {"en": "One box uses an unknown vocabulary prefix '{0}'. Use a prefix from the module palette "
            "(declared in the --prefixes file).",
      "fr": "Une boîte utilise un préfixe de vocabulaire inconnu « {0} ». Utilisez un préfixe de la "
            "palette du module (déclaré dans le fichier --prefixes)."}),
    (r"ks_rel on non-edge",
     {"en": "A relationship label was put on a box instead of on an arrow. Move it onto a connector.",
      "fr": "Une étiquette de relation a été posée sur une boîte au lieu d'une flèche. Déplacez-la sur un connecteur."}),
    (r"dangles",
     {"en": "An arrow is not connected at both ends. Attach each connector to two boxes.",
      "fr": "Une flèche n'est pas reliée aux deux extrémités. Reliez chaque connecteur à deux boîtes."}),
    (r"is not an integer",
     {"en": "A numeric field holds something that is not a whole number. Check the value.",
      "fr": "Un champ numérique contient autre chose qu'un nombre entier. Vérifiez la valeur."}),
    (r"lacks '='|malformed",
     {"en": "A data field is malformed. Use the form  property [type] = value  (e.g. riskProfile xsd:integer = 3).",
      "fr": "Un champ de données est mal formé. Utilisez la forme  propriété [type] = valeur  (p. ex. riskProfile xsd:integer = 3)."}),
    (r"no <mxGraphModel>",
     {"en": "The diagram looks empty. Add at least one box from the palette.",
      "fr": "Le schéma semble vide. Ajoutez au moins une boîte depuis la palette."}),
]


# ----------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------
def short(iri):
    """Human-friendly tail of an IRI: the bit after the last # or /."""
    iri = iri.strip().strip("<>")
    for sep in ("#", "/"):
        if sep in iri:
            iri = iri.rsplit(sep, 1)[-1]
    return iri or "(unnamed)"


def run(cmd, **kw):
    """Run a command, capturing text output. Never raises on non-zero."""
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def loc(key):
    """The localized strings for an active-language key, in render order."""
    return [MSG[key][lg] for lg in LANGS]


def emit(out, indent, key, *fmt):
    """Append one localized line per active language, stacked (EN then FR)."""
    for s in loc(key):
        out.append(indent + (s % fmt if fmt else s))


def emit_verdict(out, label_key, verdict_key, *vfmt):
    """Append a `label ........ verdict` line per active language."""
    for lg in LANGS:
        label = MSG[label_key][lg]
        verdict = MSG[verdict_key][lg]
        if vfmt:
            verdict = verdict % vfmt
        out.append("  %-42s %s" % (label, verdict))


def guard_message(path):
    """Read a guard's learner messages: {"en": ..., "fr": ...}.

    `#@coach <msg>` is English; `#@coach.fr <msg>` is French. French falls
    back to English (then to the filename) when absent.
    """
    msgs = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                mfr = re.match(r"\s*#@coach\.fr\s+(.*\S)", line)
                if mfr:
                    msgs["fr"] = mfr.group(1)
                    continue
                men = re.match(r"\s*#@coach\s+(.*\S)", line)
                if men:
                    msgs["en"] = men.group(1)
    except OSError:
        pass
    if "en" not in msgs:
        msgs["en"] = MSG["guard_generic"]["en"] % os.path.basename(path)
    msgs.setdefault("fr", msgs["en"])
    return msgs


# ----------------------------------------------------------------------------
# surface 0 — capitalise the diagram (structural gate, fault-tolerant)
# ----------------------------------------------------------------------------
def capitalise(view, out_ttl):
    """drawio -> RDF. Return (True, None) or (False, {"en":..,"fr":..})."""
    cmd = [PYTHON, ADAPTER, view]
    for p in PREFIX_FILES:
        cmd += ["--prefixes", p]
    proc = run(cmd)
    if proc.returncode == 0:
        with open(out_ttl, "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        return True, None
    # The adapter dies cleanly with `drawio2ttl: ERROR — <reason>` (exit 2).
    m = re.search(r"drawio2ttl:\s*ERROR\s*[—-]\s*(.*)", proc.stderr)
    if m:
        return False, _translate_structural(m.group(1).strip())
    # Anything else (corrupt XML, etc.) — keep it kind, never leak a traceback.
    return False, dict(MSG["read_fail_generic"])


def _translate_structural(reason):
    """Turn the adapter's developer wording into a bilingual learner hint."""
    for pat, templates in STRUCTURAL:
        m = re.search(pat, reason)
        if m:
            try:
                return {lg: templates[lg].format(*m.groups()) for lg in ("en", "fr")}
            except (IndexError, KeyError):
                return dict(templates)
    return {lg: MSG["capitalise_fail"][lg] % reason for lg in ("en", "fr")}


# ----------------------------------------------------------------------------
# surface 1 — FLOOR (rudof SHACL)
# ----------------------------------------------------------------------------
def shacl_floor(shapes, supports, data):
    """Return (conforms: bool|None, results: list[dict]). None = engine error."""
    cmd = [RUDOF, "shacl-validate", "-s", shapes, "-r", "turtle"] + supports + [data]
    proc = run(cmd)
    report = proc.stdout
    if "sh:ValidationReport" not in report and "sh:conforms" not in report:
        return None, []  # engine could not produce a report
    conforms = "sh:conforms true" in report
    return conforms, _parse_shacl_turtle(report)


def _parse_shacl_turtle(report):
    """Pull one dict per sh:ValidationResult out of rudof's turtle report."""
    results = []
    # Each subject block starts at column 0 with `_:`; split keeps them whole.
    for block in re.split(r"(?m)^_:", report):
        if "sh:ValidationResult" not in block:
            continue
        def grab(pred, pat=r"<([^>]+)>"):
            m = re.search(pred + r"\s+" + pat, block)
            return m.group(1) if m else None
        results.append({
            "focus": grab("sh:focusNode"),
            "path": grab("sh:resultPath"),
            "value": (re.search(r"sh:value\s+([^\s;]+)", block) or [None, None])[1]
                     if re.search(r"sh:value\s+([^\s;]+)", block) else None,
            "component": (grab("sh:sourceConstraintComponent", r"sh:(\w+)") or "constraint"),
            "message": (re.search(r'sh:resultMessage\s+"([^"]*)"', block) or [None, ""])[1]
                       if re.search(r'sh:resultMessage\s+"([^"]*)"', block) else "",
        })
    return results


# ----------------------------------------------------------------------------
# surface 2 — SUITABILITY (oxigraph SPARQL guards)
# ----------------------------------------------------------------------------
def suitability(supports, data, guards):
    """Load the KS into a throwaway oxigraph store, run each guard.
    Return (ok: bool|None, flags: list[dict]). None = engine error."""
    if not guards:
        return True, []
    store = tempfile.mkdtemp(prefix="ks-coach-store-")
    try:
        for graph in supports + [data]:
            proc = run([OXIGRAPH, "load", "--location", store, "--file", graph])
            if proc.returncode != 0:
                return None, []
        flags = []
        for guard in guards:
            proc = run([OXIGRAPH, "query", "--location", store,
                        "--query-file", guard, "--results-format", "csv"])
            if proc.returncode != 0:
                continue  # a broken guard must not crash the coach
            lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
            if len(lines) <= 1:
                continue  # header only -> zero rows -> guard satisfied
            header = lines[0].split(",")
            rows = [dict(zip(header, ln.split(","))) for ln in lines[1:]]
            flags.append({"message": guard_message(guard), "rows": rows})
        return (len(flags) == 0), flags
    finally:
        shutil.rmtree(store, ignore_errors=True)


# ----------------------------------------------------------------------------
# reveal-as-reward — count what the learner just created
# ----------------------------------------------------------------------------
def census(data):
    try:
        text = open(data, encoding="utf-8").read()
    except OSError:
        return None
    entities = len(re.findall(r"(?m)^\S+ rdf:type ", text))
    edges = len(re.findall(r"(?m)^<\S+> <\S+> <\S+> \.\s*$", text))
    return entities, edges


# ----------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(add_help=True, description="Knowledge Space coach")
    ap.add_argument("viewpoint")
    ap.add_argument("--shapes", required=True)
    ap.add_argument("--support", nargs="*", default=[])
    ap.add_argument("--guard", nargs="*", default=[])
    ap.add_argument("--prefixes", nargs="*", default=[],
                    help="Turtle file(s) of @prefix lines for domain-module vocabularies")
    ap.add_argument("--lang", choices=["en", "fr", "both"], default="both",
                    help="learner-facing language (default: both)")
    args = ap.parse_args()

    global LANGS, PREFIX_FILES
    PREFIX_FILES = args.prefixes
    LANGS = {"en": ["en"], "fr": ["fr"], "both": ["en", "fr"]}[args.lang]

    name = os.path.basename(args.viewpoint)
    out = []
    out.append("")
    emit(out, "", "header", name)
    out.append("=" * 58)
    out.append("")

    # --- surface 0 : read the diagram ---------------------------------------
    data_ttl = os.path.splitext(args.viewpoint)[0] + ".capitalised.ttl"
    ok, msg = capitalise(args.viewpoint, data_ttl)
    if not ok:
        emit_verdict(out, "step1_label", "step1_fail")
        out.append("")
        for lg in LANGS:
            out.append("  " + msg[lg])
        out.append("")
        emit(out, "  ", "nothing_changed")
        out.append("")
        sys.stdout.write("\n".join(out))
        return 2
    emit_verdict(out, "step1_label", "step1_ok")

    # --- surface 1 : floor ---------------------------------------------------
    conforms, results = shacl_floor(args.shapes, args.support, data_ttl)
    if conforms is None:
        emit_verdict(out, "step2_label", "step2_could_not")
    elif conforms:
        emit_verdict(out, "step2_label", "step2_conforms")
    else:
        emit_verdict(out, "step2_label", "step2_issues", len(results))

    # --- surface 2 : suitability --------------------------------------------
    suit_ok, flags = suitability(args.support, data_ttl, args.guard)
    if not args.guard:
        emit_verdict(out, "step3_label", "step3_no_rules")
    elif suit_ok is None:
        emit_verdict(out, "step3_label", "step3_could_not")
    elif suit_ok:
        emit_verdict(out, "step3_label", "step3_all_clear")
    else:
        emit_verdict(out, "step3_label", "step3_review", len(flags))

    out.append("")
    out.append("-" * 58)

    # --- floor details -------------------------------------------------------
    if results:
        out.append("")
        emit(out, "", "structure_header")
        for r in results:
            f, p, v = short(r["focus"] or ""), short(r["path"] or ""), r["value"]
            detail = r["message"] or r["component"]
            if v is not None:
                emit(out, "  • ", "structure_value", f, p, v, detail)
            else:
                emit(out, "  • ", "structure_novalue", f, p or "?", detail)
        emit(out, "    ", "structure_fix")

    # --- suitability details -------------------------------------------------
    if flags:
        out.append("")
        emit(out, "", "business_header")
        for fl in flags:
            for lg in LANGS:
                out.append("  • " + fl["message"][lg])
            for row in fl["rows"]:
                pretty = "; ".join("%s=%s" % (k, short(v) if v.startswith("http") else v)
                                   for k, v in row.items() if v)
                out.append("      → %s" % pretty)
        emit(out, "    ", "business_footnote")

    # --- summary + reveal ----------------------------------------------------
    out.append("")
    out.append("-" * 58)
    if conforms and suit_ok:
        c = census(data_ttl)
        if c:
            emit(out, "", "allclear_lead")
            emit(out, "  ", "allclear_census", *c)
        else:
            emit(out, "", "allclear_plain")
        emit(out, "  ", "allclear_backstage")
        rc = 0
    elif conforms is False:
        emit(out, "", "action_needed")
        rc = 1
    else:
        emit(out, "", "almost_there")
        rc = 3
    out.append("")
    sys.stdout.write("\n".join(out))
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        # Last-resort net: a coach must never spit a traceback at a learner.
        sys.stderr.write("\n" + MSG["safety_net"]["en"] +
                         "\n" + MSG["safety_net"]["fr"] + "\n")
        sys.exit(2)

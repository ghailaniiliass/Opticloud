"""Génération du rapport de migration (Markdown + JSON) à partir du résultat de `run_import`."""
from __future__ import annotations

import json
from pathlib import Path

SRC, LEG, DJ_SQL, DJ_ORM = "fichier SQL", "legacy", "Django (SQL)", "Django (ORM)"


def _c(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(_c(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def render_markdown(r: dict) -> str:
    L: list[str] = []
    verdict = r.get("verdict", "?")
    L += ["# Rapport de migration Opti Cloud", "",
          f"**Verdict : {verdict}**", "",
          f"- Mode : {r.get('mode')}" + (" avec `--reset`" if r.get("reset") else ""),
          f"- Début : {r.get('started_at')} — durée : {r.get('duration_s', '?')} s", ""]

    env = r.get("environment") or {}
    if env:
        L += ["## 1. Environnement", ""]
        labels = {"version": "version du serveur", "host": "hôte", "port": "port", "database": "base", "user": "compte MySQL",
                  "charset": "jeu de caractères par défaut de la base", "collation": "collation par défaut de la base",
                  "time_zone": "fuseau horaire de session", "system_time_zone": "fuseau horaire du serveur"}
        L.append(_table(["", "Base cible (Django)", "Copie de travail (legacy)"], [
            [labels[k], (env.get("cible") or {}).get(k), (env.get("legacy") or {}).get(k)] for k in labels]))
        L += ["", "Les tables de la copie legacy restent en latin1 comme dans le dump d'origine (voir le §12) ; seul le défaut de la base est utf8mb4.",
              "", "Le fuseau horaire de session doit rester identique entre le chargement du dump et l'import (colonnes TIMESTAMP) ; "
                  "la comparaison fichier ↔ base le vérifie.", ""]

    arch = r.get("archive") or {}
    if arch:
        L += ["## 2. Archive des originaux (hors du projet, lecture seule)", "", f"Snapshot : `{arch.get('snapshot')}`", ""]
        L.append(_table(["Fichier", "SHA-256 attendu (manifeste)", "avant", "après", "intact"],
                        [[f["name"], f["sha256_expected"], "identique" if f.get("ok_before") else "DIFFÉRENT",
                          ("identique" if f.get("ok_after") else "DIFFÉRENT") if "ok_after" in f else "—",
                          "oui" if f.get("ok_before") and f.get("ok_after", True) else "NON"] for f in arch.get("files", [])]))
        L.append("")

    L += ["## 3. Journal des contrôles", ""]
    L.append(_table(["#", "Contrôle", "Statut", "Détail"], [[i + 1, c["name"], c["status"], c["detail"]] for i, c in enumerate(r.get("checks", []))]))
    L.append("")

    tables = r.get("tables") or {}
    if tables:
        L += ["## 4. Comptages par table (quatre sources)", ""]
        rows = []
        for t, v in tables.items():
            c = v["counts"]
            rows.append([t, c.get(SRC), c.get(LEG), c.get(DJ_SQL, "—"), c.get(DJ_ORM, "—"),
                         "OK" if len({x for x in c.values()}) == 1 and len(c) == 4 else ("à vérifier" if len(c) < 4 else "ÉCART")])
        tot = lambda k: sum(v["counts"].get(k, 0) for v in tables.values())
        rows.append(["**TOTAL**", tot(SRC), tot(LEG), tot(DJ_SQL), tot(DJ_ORM), ""])
        L.append(_table(["Table", SRC, LEG, DJ_SQL, DJ_ORM, "Statut"], rows))
        L += ["", "## 5. Intégrité des valeurs : empreintes SHA-256 par table", "",
              "Chaque table est sérialisée de façon canonique (lignes triées par clé, UTF-8, NULL distinct de la chaîne vide), puis hachée. "
              "Les textes sont comparés point de code par point de code, sans normalisation ni correction.", ""]
        rows = []
        for t, v in tables.items():
            fp = v["fingerprints"]
            same = len(set(fp.values())) == 1 and len(fp) == 4
            cmp_ = v.get("comparisons", {})
            diffs = sum(x["cell_diff_count"] for x in cmp_.values()) if cmp_ else v.get("file_vs_legacy", {}).get("cell_diff_count", "—")
            rows.append([t, fp.get(SRC, "")[:16], fp.get(LEG, "")[:16], fp.get(DJ_SQL, "—")[:16], fp.get(DJ_ORM, "—")[:16],
                         diffs, "identiques" if same else "—"])
        L.append(_table(["Table", f"SHA-256 {SRC}", f"{LEG}", "Django SQL", "Django ORM", "Cellules différentes", "Empreintes"], rows))
        L.append("")

    enc = (r.get("encoding") or {}).get("non_ascii")
    an = r.get("anomalies") or {}
    if enc is not None:
        L += ["## 6. Encodage latin1 → utf8mb4", "",
              "Le dump est en UTF-8 ; les tables d'origine sont déclarées en latin1. Caractères non ASCII présents :", ""]
        L.append(_table(["Caractère", "Point de code", "Nom", "Occurrences", "Représentable en latin1"],
                        [[x["char"], x["codepoint"], x["name"], x["count"], "oui" if x["latin1"] else "NON"] for x in enc]))
        L.append("")
        cor = an.get("corrupted", [])
        L += [f"### Texte déjà corrompu dans le dump d'origine : {len(cor)} cellule(s) — signalé, NON corrigé", ""]
        L.append(_table(["Table", "Clé", "Colonne", "Valeur (copiée telle quelle)"], [[x["table"], x["key"], x["column"], x["value"]] for x in cor]) if cor else "Aucune.")
        L.append("")

    ai = r.get("autoincrement") or {}
    if ai:
        L += ["## 7. Compteurs AUTO_INCREMENT", ""]
        L.append(_table(["Table", "Valeur du dump", "max(clé)+1", "Valeur visée", "Valeur lue après"],
                        [[t, e.get("dump"), e.get("max_pk_plus_1"), e.get("wanted"), e.get("applied", "(simulation)")] for t, e in ai.items()]))
        L.append("")

    if an.get("relations"):
        L += ["## 8. Relations logiques (aucune clé étrangère, conformément à la décision validée)", "",
              "Les valeurs sont conservées telles quelles, même sans correspondance.", ""]
        L.append(_table(["Colonne enfant", "Table parente", "Renseignées", "Avec correspondance", "Valeurs sans correspondance"],
                        [[x["child"], x["parent"], x["filled"], f"{x['valid']}/{x['filled']}", ", ".join(map(str, x["invalid_values"])) or "—"] for x in an["relations"]]))
        L.append("")
        L += ["## 9. Valeurs hors liste ENUM", ""]
        ev = an.get("enum_invalid", [])
        L.append(_table(["Table", "Clé", "Colonne", "Valeur"], [[x["table"], x["key"], x["column"], x["value"]] for x in ev]) if ev else "Aucune.")
        L += ["", "## 10. Enregistrements ressemblant à des données de test (CONSERVÉS)", "",
              "Liste d'observation établie lors de l'audit ; aucun enregistrement n'est supprimé.", ""]
        tl = an.get("test_like", [])
        L.append(_table(["Table", "Clé", "Colonne", "Valeur"], [[x["table"], x["key"], x["column"], x["value"]] for x in tl]) if tl else "Aucun.")
        L.append("")
        kc = an.get("key_collisions", [])
        L += ["## 11. Collisions de clés texte (collation insensible à la casse et aux accents)", "",
              "Aucune." if not kc else ", ".join(f"{x['table']}.{x['column']}" for x in kc), ""]

    sd = r.get("schema_diff") or []
    if sd:
        L += ["## 12. Écarts de schéma détectés automatiquement (legacy ↔ Django)", ""]
        L.append(_table(["Table", "Élément", "Legacy", "Django", "Statut", "Explication"],
                        [[d["table"], d["element"], d["legacy"], d["django"], d["status"], d["explication"]] for d in sd]))
        L.append("")
    return "\n".join(L) + "\n"


def write_reports(result: dict, report_dir: Path, failed: bool = False) -> list[Path]:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    if failed:
        stem = "migration_report_ECHEC"
    elif "simulation" in result.get("mode", ""):
        stem = "migration_report_dry_run"
    else:
        stem = "migration_report"
    md, js = report_dir / f"{stem}.md", report_dir / f"{stem}.json"
    md.write_text(render_markdown(result), encoding="utf-8", newline="\n")
    js.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8", newline="\n")
    return [md, js]

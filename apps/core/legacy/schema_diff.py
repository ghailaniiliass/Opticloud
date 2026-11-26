"""
Comparaison automatique des schémas (information_schema) : copie du dump d'origine ↔ base Django.

Chaque écart est classé « attendu » (décidé et expliqué) ou « INATTENDU » (à examiner).
"""
from __future__ import annotations

import re

from .registry import LEGACY_TABLES

EXPECTED_TYPE_CHANGES = {
    ("enum", "varchar"): "ENUM MySQL remplacé par VARCHAR : Django n'a pas d'ENUM natif ; les valeurs valides sont imposées par les formulaires (listes déroulantes) et les choix du modèle.",
    ("timestamp", "datetime"): "TIMESTAMP remplacé par DATETIME(6) : même valeur littérale, sans conversion de fuseau horaire ; défaut conservé côté base.",
    ("text", "longtext"): "TEXT remplacé par LONGTEXT : type TextField de Django ; capacité supérieure, aucune donnée affectée.",
}
PK_CHANGES = {
    ("categorie", "id_categorie"): "UNIQUE KEY devenue PRIMARY KEY (décision validée) ; aucune colonne `id` ajoutée.",
    ("client", "id_client"): "UNIQUE KEY devenue PRIMARY KEY (décision validée) ; aucune colonne `id` ajoutée.",
}
_COLS_SQL = """
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE,
       IS_NULLABLE, COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME
FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({marks})
"""
_IDX_SQL = """
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME
FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({marks})
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
"""
_TAB_SQL = """
SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ({marks})
"""


_NOW_SYNONYMS = {"now", "current_timestamp", "localtime", "localtimestamp"}


def _norm_default(v):
    """Normalise une valeur par défaut ; CURRENT_TIMESTAMP, NOW(), current_timestamp(6)… sont équivalents
    (la précision est couverte par l'écart de type TIMESTAMP → DATETIME(6))."""
    if v is None:
        return None
    s = str(v).strip().strip("'").lower()
    s = re.sub(r"\(\d*\)", "", s).strip("()")
    return "current_timestamp" if s in _NOW_SYNONYMS else s


def fetch_schema(connection) -> dict:
    tables = list(LEGACY_TABLES)
    marks = ", ".join(["%s"] * len(tables))
    schema: dict = {t: {"columns": {}, "indexes": {}, "engine": None, "collation": None} for t in tables}
    with connection.cursor() as cur:
        cur.execute(_COLS_SQL.format(marks=marks), tables)
        for t, c, dt, ln, pr, sc, nul, dflt, extra, cs, coll in cur.fetchall():
            schema[t]["columns"][c] = {
                "type": str(dt).lower(), "length": ln, "precision": pr, "scale": sc,
                "nullable": nul == "YES", "default": dflt, "auto_increment": "auto_increment" in str(extra).lower(),
                "charset": cs, "collation": coll,
            }
        cur.execute(_IDX_SQL.format(marks=marks), tables)
        for t, idx, non_unique, _seq, col in cur.fetchall():
            schema[t]["indexes"].setdefault(idx, {"unique": non_unique == 0, "columns": []})["columns"].append(col)
        cur.execute(_TAB_SQL.format(marks=marks), tables)
        for t, eng, coll in cur.fetchall():
            schema[t]["engine"], schema[t]["collation"] = eng, coll
    return schema


def diff_schemas(legacy: dict, django: dict) -> list[dict]:
    out: list[dict] = []

    def add(table, element, a, b, expected, why=""):
        out.append({"table": table, "element": element, "legacy": a, "django": b,
                    "status": "attendu" if expected else "INATTENDU", "explication": why})

    for t in LEGACY_TABLES:
        L, D = legacy[t], django[t]
        if not L["columns"]:
            add(t, "table", "absente", "—", False, "Table absente de la copie legacy.")
            continue
        if not D["columns"]:
            add(t, "table", "présente", "absente", False, "Table absente de la base Django (migrate non appliqué ?).")
            continue
        if L["engine"] != D["engine"]:
            add(t, "moteur", L["engine"], D["engine"], False)
        if L["collation"] != D["collation"]:
            add(t, "jeu de caractères / collation de la table", L["collation"], D["collation"], True,
                "latin1 → utf8mb4 : toutes les valeurs sont conservées à l'identique (vérifié caractère par caractère) ; "
                "le texte déjà corrompu dans le dump n'est pas corrigé.")
        for c in sorted(set(L["columns"]) | set(D["columns"])):
            a, b = L["columns"].get(c), D["columns"].get(c)
            if a is None or b is None:
                add(t, f"colonne {c}", "présente" if a else "absente", "présente" if b else "absente", False)
                continue
            pair = (a["type"], b["type"])
            if a["type"] != b["type"]:
                why = EXPECTED_TYPE_CHANGES.get(pair)
                add(t, f"colonne {c} : type", a["type"], b["type"], why is not None, why or "")
            else:
                if a["length"] != b["length"] and a["type"] in ("varchar", "char"):
                    add(t, f"colonne {c} : longueur", a["length"], b["length"], False)
                if (a["precision"], a["scale"]) != (b["precision"], b["scale"]) and a["type"] == "decimal":
                    add(t, f"colonne {c} : précision", f"({a['precision']},{a['scale']})", f"({b['precision']},{b['scale']})", False)
            if a["nullable"] != b["nullable"]:
                add(t, f"colonne {c} : NULL autorisé", a["nullable"], b["nullable"], False)
            if a["auto_increment"] != b["auto_increment"]:
                add(t, f"colonne {c} : auto-incrément", a["auto_increment"], b["auto_increment"], False)
            if _norm_default(a["default"]) != _norm_default(b["default"]):
                add(t, f"colonne {c} : valeur par défaut", a["default"], b["default"], False)
        # Index : comparés par colonnes (Django génère ses propres noms)
        def sets(idx):
            uniq = {tuple(v["columns"]) for v in idx.values() if v["unique"]}
            plain = {tuple(v["columns"]) for v in idx.values() if not v["unique"]}
            return uniq, plain
        (lu, lp), (du, dp) = sets(L["indexes"]), sets(D["indexes"])
        if lu != du:
            add(t, "index uniques", sorted(lu), sorted(du), False)
        if lp != dp:
            add(t, "index non uniques", sorted(lp), sorted(dp), False)
        lpk = L["indexes"].get("PRIMARY", {}).get("columns")
        dpk = D["indexes"].get("PRIMARY", {}).get("columns")
        if lpk != dpk:
            key = (t, (dpk or [None])[0])
            why = PK_CHANGES.get(key)
            add(t, "clé primaire", lpk or "aucune", dpk, why is not None, why or "")
        ln = {n for n in L["indexes"] if n != "PRIMARY"}
        dn = {n for n in D["indexes"] if n != "PRIMARY"}
        if ln != dn and lp == dp and lu - ({tuple(dpk)} if dpk else set()) <= du:
            why = ("L'index UNIQUE d'origine est remplacé par la clé primaire (mêmes colonnes)." if (t, (dpk or [None])[0]) in PK_CHANGES
                   else "Django génère ses propres noms d'index ; les colonnes indexées sont identiques.")
            add(t, "noms des index", sorted(ln), sorted(dn), True, why)
    return out

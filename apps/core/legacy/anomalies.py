"""Détection (JAMAIS de correction) des anomalies présentes dans les données d'origine."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .dumpparser import Dump

# Séquences typiques de texte déjà corrompu : « ï¿½ » (U+FFFD mal décodé), U+FFFD, double encodage UTF-8.
CORRUPTION = re.compile("ï¿½|\ufffd|Ã[\u0080-\u00bf]|â€")

# Relations logiques (sans clé étrangère) : (table enfant, colonne, table parent, colonne parent)
RELATIONS = [
    ("monture", "idmarque", "marque", "idmarque"),
    ("monture", "idfournisseur", "fournisseur", "idfournisseur"),
    ("monture", "idcategorie", "categorie", "id_categorie"),
    ("verre", "code_fournisseur", "fournisseur", "idfournisseur"),
    ("lentille", "marque", "marque", "idmarque"),
    ("lentille", "idfournisseur", "fournisseur", "idfournisseur"),
    ("ordonnance", "idpatient", "patient", "id"),
    ("ordonnance", "idmonture", "monture", "idmonture"),
    ("ordonnance", "idverre_od", "verre", "code_verre"),
    ("ordonnance", "idverre_og", "verre", "code_verre"),
    ("ordonnance", "idlentille", "lentille", "idlentille"),
]

# Valeurs qui ressemblent à des saisies d'essai : listées dans le rapport, JAMAIS supprimées.
# Détection générique ; des valeurs propres à votre base (noms de test, par exemple) peuvent s'ajouter via TEST_LIKE_VALUES dans le .env local.
_TEST_PATTERNS = (
    re.compile(r"(.)\1{3,}"),                          # même caractère répété 4 fois ou plus (« aaaaa », « Exempleeee »)
    re.compile(r"^0+$"),                                # que des zéros
    re.compile(r"^9+$"),                                # que des neuf
    re.compile(r"\btest(ing)?\b", re.IGNORECASE),      # le mot « test » ou « testing »
)


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.casefold()) if unicodedata.category(c) != "Mn")


def _label(table, key_cols, row, cols):
    return ", ".join(f"{c}={row[cols.index(c)]}" for c in key_cols)


def analyze(dump: Dump, extra_test_values=()) -> dict:
    extra = {str(x) for x in extra_test_values}
    res: dict = {"non_ascii": [], "corrupted": [], "relations": [], "enum_invalid": [], "test_like": [], "key_collisions": []}
    for tname, t in dump.tables.items():
        cols = t.column_names
        for row in t.rows:
            for col, v in zip(t.columns, row):
                if not isinstance(v, str):
                    continue
                if CORRUPTION.search(v):
                    res["corrupted"].append({"table": tname, "key": _label(tname, t.key_columns, row, cols), "column": col.name, "value": v})
                if col.base_type == "enum" and v != "" and v not in col.enum_values:
                    res["enum_invalid"].append({"table": tname, "key": _label(tname, t.key_columns, row, cols), "column": col.name, "value": v})
                if col.base_type == "enum" and v == "":
                    res["enum_invalid"].append({"table": tname, "key": _label(tname, t.key_columns, row, cols), "column": col.name, "value": "(chaîne vide)"})
                if v in extra or (col.name.startswith(("nom", "medecin")) and any(p.search(v) for p in _TEST_PATTERNS)):
                    res["test_like"].append({"table": tname, "key": _label(tname, t.key_columns, row, cols), "column": col.name, "value": v})
    res["non_ascii"] = analyze_chars(dump)
    for child, ccol, parent, pcol in RELATIONS:
        ct, pt = dump.tables[child], dump.tables[parent]
        ci, pi = ct.column_names.index(ccol), pt.column_names.index(pcol)
        parents = {r[pi] for r in pt.rows if r[pi] is not None}
        values = [r[ci] for r in ct.rows if r[ci] is not None]
        bad = sorted({v for v in values if v not in parents})
        res["relations"].append({"child": f"{child}.{ccol}", "parent": f"{parent}.{pcol}", "filled": len(values),
                                 "valid": len(values) - sum(1 for v in values if v not in parents), "invalid_values": bad})
    for tname, t in dump.tables.items():
        for c in t.key_columns:
            col = next(x for x in t.columns if x.name == c)
            if col.base_type in ("varchar", "char"):
                i = t.column_names.index(c)
                vals = [r[i] for r in t.rows]
                if len({_fold(v) for v in vals}) != len(vals):
                    res["key_collisions"].append({"table": tname, "column": c})
    return res


def analyze_chars(dump: Dump) -> list[dict]:
    chars: Counter = Counter()
    for t in dump.tables.values():
        for row in t.rows:
            for v in row:
                if isinstance(v, str):
                    chars.update(ch for ch in v if ord(ch) > 127)
    out = []
    for ch, n in sorted(chars.items()):
        try:
            ch.encode("cp1252")
            ok = True
        except UnicodeEncodeError:
            ok = False
        out.append({"char": ch, "codepoint": f"U+{ord(ch):04X}", "name": unicodedata.name(ch, "?"), "count": n, "latin1": ok})
    return out

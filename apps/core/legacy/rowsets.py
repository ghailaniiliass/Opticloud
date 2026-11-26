"""
Représentation canonique des lignes pour comparer EXACTEMENT trois sources :
fichier SQL, base `legacy`, base Django (SQL brut puis ORM).

Aucune normalisation Unicode, aucune correction : les textes sont comparés point de code par point de code.
NULL et chaîne vide restent distincts ; les types (entier / décimal / date…) sont étiquetés.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .dumpparser import (
    Column, Dump, Table, _DATE_TYPES, _DATETIME_TYPES, _DECIMAL_TYPES, _INT_TYPES, _STRING_TYPES,
)

MAX_DIFFS_KEPT = 50


def canon_cell(value, col: Column):
    if value is None:
        return None
    t = col.base_type
    if t in _INT_TYPES:
        if isinstance(value, Decimal) and value == value.to_integral_value():
            value = int(value)
        if isinstance(value, int) and not isinstance(value, bool):
            return ["i", str(value)]
    elif t in _DECIMAL_TYPES:
        if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
            return ["d", format(Decimal(value).quantize(Decimal(1).scaleb(-(col.scale or 0))), "f")]
    elif t in _STRING_TYPES:
        if isinstance(value, str):
            return ["s", value]
    elif t in _DATE_TYPES:
        if isinstance(value, date) and not isinstance(value, datetime):
            return ["D", value.isoformat()]
    elif t in _DATETIME_TYPES:
        if isinstance(value, datetime):
            return ["T", value.strftime("%Y-%m-%d %H:%M:%S") + (f".{value.microsecond:06d}" if value.microsecond else "")]
    return ["?", f"{type(value).__name__}:{value!r}"]   # type inattendu : fera apparaître l'écart


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@dataclass
class RowSet:
    label: str
    rows: dict[str, list] = field(default_factory=dict)       # clé (JSON) -> cellules canoniques
    duplicates: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.rows)

    def fingerprint(self) -> str:
        """SHA-256 de toutes les lignes triées par clé, encodées en UTF-8."""
        h = hashlib.sha256()
        for k in sorted(self.rows):
            h.update(_j(self.rows[k]).encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()


def build_rowset(label: str, table: Table, typed_rows) -> RowSet:
    key_idx = [table.column_names.index(c) for c in table.key_columns]
    rs = RowSet(label=label)
    for row in typed_rows:
        cells = [canon_cell(v, c) for v, c in zip(row, table.columns)]
        key = _j([cells[i] for i in key_idx])
        if key in rs.rows:
            rs.duplicates.append(key)
        rs.rows[key] = cells
    return rs


def compare(a: RowSet, b: RowSet, table: Table) -> dict:
    names = table.column_names
    missing = sorted(set(a.rows) - set(b.rows))
    extra = sorted(set(b.rows) - set(a.rows))
    diffs, n_diffs = [], 0
    for key in sorted(set(a.rows) & set(b.rows)):
        for name, ca, cb in zip(names, a.rows[key], b.rows[key]):
            if ca != cb:
                n_diffs += 1
                if len(diffs) < MAX_DIFFS_KEPT:
                    diffs.append({"key": key, "column": name, a.label: ca, b.label: cb})
    return {
        "pair": f"{a.label} ↔ {b.label}",
        "count_a": len(a), "count_b": len(b),
        "missing_in_b": missing, "extra_in_b": extra,
        "cell_diff_count": n_diffs, "cell_diffs": diffs,
        "duplicates_a": a.duplicates, "duplicates_b": b.duplicates,
        "fingerprint_equal": a.fingerprint() == b.fingerprint(),
        "ok": not missing and not extra and n_diffs == 0 and not a.duplicates and not b.duplicates,
    }


# ---------------------------------------------------------------------------
# Lecteurs
# ---------------------------------------------------------------------------
def rowset_from_file(dump: Dump, table: str, label: str = "fichier SQL") -> RowSet:
    t = dump.tables[table]
    return build_rowset(label, t, t.typed_rows())


def select_rows(connection, table: Table) -> list[tuple]:
    cols = ", ".join(f"`{c}`" for c in table.column_names)
    with connection.cursor() as cur:
        cur.execute(f"SELECT {cols} FROM `{table.name}`")
        return [tuple(r) for r in cur.fetchall()]


def rowset_from_sql(connection, table: Table, label: str) -> tuple[RowSet, list[tuple]]:
    rows = select_rows(connection, table)
    return build_rowset(label, table, rows), rows


def rowset_from_orm(model, table: Table, alias: str, label: str) -> RowSet:
    rows = list(model.objects.using(alias).values_list(*table.column_names))
    return build_rowset(label, table, rows)

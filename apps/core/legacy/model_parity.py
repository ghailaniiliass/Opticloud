"""Contrôle AVANT import : les modèles Django reproduisent-ils exactement la structure du dump d'origine ?"""
from __future__ import annotations

from django.db import models
from django.db.models.functions import Now

from .dumpparser import Dump, _DECIMAL_TYPES, _INT_TYPES
from .registry import LEGACY_TABLES, get_model


def check_table_set(dump: Dump) -> list[str]:
    issues = []
    for t in sorted(set(dump.tables) - set(LEGACY_TABLES)):
        issues.append(f"Table du dump sans modèle Django : {t} (l'import s'arrête, aucune donnée ne sera ignorée)")
    for t in sorted(set(LEGACY_TABLES) - set(dump.tables)):
        issues.append(f"Table attendue absente du dump : {t}")
    return issues


def check_model_parity(dump: Dump) -> list[str]:
    issues: list[str] = []
    for tname, table in dump.tables.items():
        if tname not in LEGACY_TABLES:
            continue
        model = get_model(tname)
        if model._meta.db_table != tname:
            issues.append(f"{tname}: db_table du modèle = {model._meta.db_table!r}")
        fields = {f.column: f for f in model._meta.concrete_fields}
        dump_cols = {c.name: c for c in table.columns}
        for name in sorted(set(dump_cols) - set(fields)):
            issues.append(f"{tname}.{name}: colonne du dump sans champ dans le modèle (donnée qui serait perdue)")
        for name in sorted(set(fields) - set(dump_cols)):
            issues.append(f"{tname}.{name}: champ du modèle absent du dump")
        if table.foreign_keys:
            issues.append(f"{tname}: le dump déclare des clés étrangères alors que la décision validée est « aucune »")
        pk = [f.column for f in model._meta.concrete_fields if f.primary_key]
        if table.key_columns != pk:
            issues.append(f"{tname}: clé du dump {table.key_columns} ≠ clé du modèle {pk}")
        for name, col in dump_cols.items():
            f = fields.get(name)
            if f is None:
                continue
            where = f"{tname}.{name}"
            if not f.primary_key and col.nullable != f.null:
                issues.append(f"{where}: nullabilité du dump ({col.nullable}) ≠ modèle ({f.null})")
            if col.auto_increment != isinstance(f, models.AutoField):
                issues.append(f"{where}: auto-incrément du dump ({col.auto_increment}) ≠ modèle")
            t = col.base_type
            kind = type(f)
            if t in _INT_TYPES:
                if not isinstance(f, models.IntegerField):
                    issues.append(f"{where}: type entier attendu, modèle = {kind.__name__}")
            elif t in _DECIMAL_TYPES:
                if kind is not models.DecimalField or (f.max_digits, f.decimal_places) != (col.precision, col.scale):
                    issues.append(f"{where}: decimal({col.precision},{col.scale}) attendu")
            elif t in ("char", "varchar"):
                if kind is not models.CharField or f.max_length != col.length:
                    issues.append(f"{where}: varchar({col.length}) attendu, modèle = {kind.__name__}({getattr(f, 'max_length', None)})")
            elif t == "enum":
                if kind is not models.CharField:
                    issues.append(f"{where}: ENUM attendu comme CharField + choices")
                else:
                    choices = [c[0] for c in f.choices or []]
                    if choices != list(col.enum_values):
                        issues.append(f"{where}: choix du modèle {choices} ≠ ENUM du dump {list(col.enum_values)}")
                    if f.max_length < max((len(v) for v in col.enum_values), default=0):
                        issues.append(f"{where}: max_length trop court pour les valeurs de l'ENUM")
            elif "text" in t:
                if kind is not models.TextField:
                    issues.append(f"{where}: TextField attendu")
            elif t == "date":
                if kind is not models.DateField:
                    issues.append(f"{where}: DateField attendu")
            elif t in ("datetime", "timestamp"):
                if kind is not models.DateTimeField:
                    issues.append(f"{where}: DateTimeField attendu")
            if col.has_default and col.default is not None:
                if col.default.upper().startswith("CURRENT_TIMESTAMP"):
                    if not isinstance(f.db_default, Now):
                        issues.append(f"{where}: défaut CURRENT_TIMESTAMP non reproduit (db_default=Now())")
                elif str(f.db_default) != str(col.default):
                    issues.append(f"{where}: défaut du dump {col.default!r} ≠ db_default du modèle {f.db_default!r}")
        for key_name, cols in table.keys:
            for c in cols:
                if c in fields and not (fields[c].db_index or fields[c].primary_key):
                    issues.append(f"{tname}.{c}: index `{key_name}` du dump non reproduit (db_index)")
    return issues

"""
Orchestration de la migration : archive vérifiée → comparaison triple → import transactionnel → vérification → rapport.

Principes
  * Source de vérité = fichier SQL archivé (hors projet). La base `legacy` n'est qu'une copie de travail, lue en lecture seule.
  * Rien n'est modifié ni corrigé : les valeurs sont copiées telles quelles ; les anomalies sont seulement signalées.
  * Import + vérification se font dans UNE transaction : au moindre écart, tout est annulé (y compris un --reset).
"""
from __future__ import annotations

import time
from datetime import datetime

from django.conf import settings
from django.db import DatabaseError, connections, transaction

from . import anomalies, archive, model_parity, rowsets, safety, schema_diff
from .dumpparser import DumpParseError, parse_dump_file
from .registry import LEGACY_TABLES, get_model

SRC = "fichier SQL"
LEG = "legacy"
DJ_SQL = "Django (SQL)"
DJ_ORM = "Django (ORM)"


class MigrationFailure(Exception):
    def __init__(self, message: str, result: dict):
        super().__init__(message)
        self.result = result


class _Rollback(Exception):
    """Annule volontairement la transaction (simulation)."""


def _read_target_sql(connection, table):
    """Lecture de la base cible en SQL brut (point d'extension utilisé par les tests d'échec)."""
    return rowsets.rowset_from_sql(connection, table, DJ_SQL)[0]


def _set_readonly(conn, readonly: bool) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY" if readonly else "SET SESSION TRANSACTION READ WRITE")
        return True
    except DatabaseError:
        return False


def _server_info(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT VERSION(), @@port, @@time_zone, @@system_time_zone, @@character_set_database, @@collation_database")
        v, port, tz, systz, cs, coll = cur.fetchone()
    s = conn.settings_dict
    return {"version": v, "port": port, "host": s.get("HOST"), "database": s.get("NAME"), "user": s.get("USER"),
            "time_zone": tz, "system_time_zone": systz, "charset": cs, "collation": coll}


def _auto_increment_value(conn, table: str):
    with conn.cursor() as cur:
        try:
            cur.execute("SET SESSION information_schema_stats_expiry = 0")   # MySQL 8 : évite des statistiques en cache
        except DatabaseError:
            pass
        cur.execute("SELECT AUTO_INCREMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", [table])
        row = cur.fetchone()
        return row[0] if row else None


def _restore_counters(conn, saved: dict) -> None:
    """Un ROLLBACK n'annule pas les compteurs AUTO_INCREMENT d'InnoDB : on les remet à leur valeur d'avant."""
    for table, value in saved.items():
        if value:
            try:
                with conn.cursor() as cur:
                    cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = {int(value)}")
            except DatabaseError:
                pass


def run_import(*, archive_dir, snapshot=None, dry_run=False, reset=False, confirm_database=None, log=lambda m: None) -> dict:
    t0 = time.perf_counter()
    default, legacy = connections["default"], connections["legacy"]
    result: dict = {
        "mode": "simulation (dry-run)" if dry_run else "import réel",
        "reset": reset, "started_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": "OK", "checks": [], "tables": {}, "autoincrement": {}, "schema_diff": [],
        "anomalies": {}, "archive": {}, "environment": {},
    }

    def record(name: str, status: str = "OK", detail: str = "") -> None:
        result["checks"].append({"name": name, "status": status, "detail": detail})
        log(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

    def fail(name: str, detail: str):
        record(name, "ÉCHEC", detail)
        result["verdict"] = "ÉCHEC"
        result["duration_s"] = round(time.perf_counter() - t0, 2)
        raise MigrationFailure(f"{name} : {detail}", result)

    # 0. Garde-fous : à chaque exécution, simulation comprise ---------------------------------------
    extra = list(getattr(settings, "PROTECTED_DATABASES", []))
    if reset:
        safety.assert_reset_allowed(default.settings_dict, legacy.settings_dict, confirm_database, extra)
    else:
        safety.assert_safe_config(default.settings_dict, legacy.settings_dict, extra)
    record("Garde-fous de configuration", "OK",
           f"cible={default.settings_dict['NAME']!r}, legacy={legacy.settings_dict['NAME']!r}, bases protégées respectées, serveur local")

    # 1. Archive d'origine : vérification des empreintes AVANT -------------------------------------
    adir = archive.resolve_archive_dir(archive_dir)
    snap = archive.resolve_snapshot(adir, snapshot)
    before = archive.verify_snapshot(snap)
    result["archive"] = {"snapshot": snap.name, "directory": str(snap), "files": [
        {"name": r["name"], "sha256_expected": r["expected"], "sha256_before": r["actual"], "ok_before": r["ok"]} for r in before]}
    bad = [r["name"] for r in before if not r["ok"]]
    if bad:
        raise archive.ArchiveError(f"Empreinte SHA-256 différente du manifeste pour : {', '.join(bad)}. Les originaux ont été altérés : import refusé.")
    record("Archive d'origine intacte (SHA-256 avant)", "OK", f"{snap.name} : {len(before)} fichier(s)")
    dump_path = archive.dump_file_of(snap)
    try:
        dump = parse_dump_file(dump_path)
    except DumpParseError as exc:
        fail("Lecture du dump d'origine", str(exc))
    record("Lecture du dump d'origine (lecture seule)", "OK", f"{len(dump.tables)} tables, {sum(dump.row_counts().values())} lignes")

    # 2. Pré-vérifications structurelles --------------------------------------------------------------
    issues = model_parity.check_table_set(dump)
    if issues:
        fail("Toutes les tables du dump ont un modèle", " ; ".join(issues))
    record("Les 9 tables du dump ont chacune un modèle Django")
    issues = model_parity.check_model_parity(dump)
    if issues:
        fail("Parité modèles ↔ dump (colonnes, types, longueurs, clés)", " ; ".join(issues[:8]))
    record("Parité modèles ↔ dump : aucune colonne oubliée, types et longueurs identiques")
    chars = anomalies.analyze_chars(dump)
    result["encoding"] = {"non_ascii": chars}
    non_l1 = [c for c in chars if not c["latin1"]]
    if non_l1:
        fail("Encodage : caractères représentables en latin1", "caractères hors latin1 : " + ", ".join(f"{c['char']} ({c['codepoint']})" for c in non_l1))
    record("Encodage : tous les caractères du dump sont représentables en latin1", "OK", f"{len(chars)} caractère(s) non ASCII distinct(s)")

    ro_ok = _set_readonly(legacy, True)
    try:
        record("Connexion legacy en lecture seule" if ro_ok else "Connexion legacy : mode lecture seule non confirmé",
               "OK" if ro_ok else "ATTENTION")

        # 3. Base legacy : tables, comptages et valeurs comparés au fichier ----------------------------
        with legacy.cursor() as cur:
            cur.execute("SHOW TABLES")
            legacy_tables = {r[0] for r in cur.fetchall()} - {"django_migrations"}
        extra_tables = sorted(legacy_tables - set(LEGACY_TABLES))
        if extra_tables:
            fail("Aucune table de la copie legacy oubliée", f"tables présentes dans legacy mais non migrées : {extra_tables}")
        missing_tables = sorted(set(LEGACY_TABLES) - legacy_tables)
        if missing_tables:
            fail("Les 9 tables sont chargées dans la copie legacy", f"tables absentes : {missing_tables}")

        file_sets, legacy_sets, legacy_rows = {}, {}, {}
        for tname, table in dump.tables.items():
            file_sets[tname] = rowsets.rowset_from_file(dump, tname, SRC)
            legacy_sets[tname], legacy_rows[tname] = rowsets.rowset_from_sql(legacy, table, LEG)
            result["tables"][tname] = {"model": LEGACY_TABLES[tname], "counts": {SRC: len(file_sets[tname]), LEG: len(legacy_sets[tname])},
                                       "fingerprints": {SRC: file_sets[tname].fingerprint(), LEG: legacy_sets[tname].fingerprint()}}
        bad_tables = []
        for tname, table in dump.tables.items():
            c = rowsets.compare(file_sets[tname], legacy_sets[tname], table)
            result["tables"][tname]["file_vs_legacy"] = c
            if not c["ok"]:
                bad_tables.append(tname)
        if bad_tables:
            fail("Copie legacy identique au fichier SQL (valeurs, caractère par caractère)",
                 f"écarts dans {bad_tables} : la copie de travail ne correspond pas au dump. Rechargez-la en UTF-8 "
                 "(jeu de caractères du fichier = utf-8). Aucune écriture n'a été faite dans la base Django.")
        record("Copie legacy = fichier SQL : comptages et valeurs identiques, texte exact", "OK",
               f"{sum(len(s) for s in file_sets.values())} lignes comparées sur 9 tables")

        # 4. Base cible ----------------------------------------------------------------------------------
        if not safety.target_is_django_db(default):
            fail("La base cible est bien la base Django", "table django_migrations absente ou migrations non appliquées (python manage.py migrate)")
        record("La base cible est bien la base Django (django_migrations présent, 8 applications migrées)")
        existing = {t: get_model(t).objects.using("default").count() for t in dump.tables}
        result["target_rows_before"] = existing
        if any(existing.values()) and not reset:
            fail("La base cible est vide", f"lignes déjà présentes : { {t: n for t, n in existing.items() if n} }. "
                 f"Pour recommencer : --reset --confirm-database {default.settings_dict['NAME']}")
        record("Base cible " + ("vidée dans la transaction (--reset)" if reset and any(existing.values()) else "vide"), "OK",
               f"{sum(existing.values())} ligne(s) existante(s)")

        # 5. Import + vérification dans UNE transaction ---------------------------------------------------
        def verify_inside_transaction():
            for tname, table in dump.tables.items():
                model = get_model(tname)
                rd = _read_target_sql(default, table)
                ro = rowsets.rowset_from_orm(model, table, "default", DJ_ORM)
                cmp_ = {
                    f"{SRC} ↔ {DJ_SQL}": rowsets.compare(file_sets[tname], rd, table),
                    f"{LEG} ↔ {DJ_SQL}": rowsets.compare(legacy_sets[tname], rd, table),
                    f"{SRC} ↔ {DJ_ORM}": rowsets.compare(file_sets[tname], ro, table),
                }
                tr = result["tables"][tname]
                tr["counts"][DJ_SQL], tr["counts"][DJ_ORM] = len(rd), len(ro)
                tr["fingerprints"][DJ_SQL], tr["fingerprints"][DJ_ORM] = rd.fingerprint(), ro.fingerprint()
                tr["comparisons"] = cmp_
                fps = set(tr["fingerprints"].values())
                tr["ok"] = all(c["ok"] for c in cmp_.values()) and len(fps) == 1
            bad = [t for t, v in result["tables"].items() if not v["ok"]]
            if bad:
                fail("Vérification des données importées", f"écarts détectés dans {bad} : TRANSACTION ANNULÉE, rien n'a été conservé")
            record("Vérification : comptages, clés, valeurs et empreintes SHA-256 identiques (fichier = legacy = Django SQL = Django ORM)",
                   "OK", f"{sum(len(s) for s in file_sets.values())} lignes, 9 tables")

        ai_tables = [t for t, tb in dump.tables.items() if any(c.auto_increment for c in tb.columns)]
        saved_counters = {t: _auto_increment_value(default, t) for t in ai_tables}
        try:
            with transaction.atomic(using="default"):
                if reset:
                    for tname in dump.tables:
                        get_model(tname).objects.using("default").all().delete()
                for tname, table in dump.tables.items():
                    model = get_model(tname)
                    objs = [model(**dict(zip(table.column_names, row))) for row in legacy_rows[tname]]
                    model.objects.using("default").bulk_create(objs, batch_size=500)
                record("Copie des lignes dans la base Django", "OK", "valeurs reprises telles quelles, clés conservées")
                verify_inside_transaction()
                if dry_run:
                    raise _Rollback()
        except _Rollback:
            _restore_counters(default, saved_counters)
            record("Simulation : transaction annulée volontairement, la base Django n'a pas été modifiée (lignes et compteurs)", "OK")
        except BaseException:
            _restore_counters(default, saved_counters)      # échec : lignes annulées par la transaction, compteurs remis en l'état
            raise

        # 6. Après validation : compteurs auto-incrément + relecture ------------------------------------
        for tname, table in dump.tables.items():
            ai = [c for c in table.columns if c.auto_increment]
            if not ai:
                continue
            pk_i = table.column_names.index(ai[0].name)
            max_pk = max((r[pk_i] for r in legacy_rows[tname]), default=0)
            wanted = max(table.auto_increment or 1, max_pk + 1)
            entry = {"dump": table.auto_increment, "max_pk_plus_1": max_pk + 1, "wanted": wanted}
            if not dry_run:
                with default.cursor() as cur:
                    cur.execute(f"ALTER TABLE `{tname}` AUTO_INCREMENT = {int(wanted)}")
                entry["applied"] = _auto_increment_value(default, tname)
            result["autoincrement"][tname] = entry
        if not dry_run:
            bad_ai = [t for t, e in result["autoincrement"].items() if e["applied"] != e["wanted"]]
            if bad_ai:
                fail("Compteurs auto-incrément", f"valeur appliquée différente de la valeur attendue pour {bad_ai}")
            record("Compteurs auto-incrément reportés à l'identique", "OK",
                   ", ".join(f"{t}={e['applied']}" for t, e in result["autoincrement"].items()))
            for tname, table in dump.tables.items():
                after = _read_target_sql(default, table)
                if after.fingerprint() != file_sets[tname].fingerprint():
                    fail("Relecture après validation", f"table {tname} : empreinte différente du fichier SQL")
            record("Relecture après validation : empreintes identiques au fichier SQL (9 tables)")
        else:
            record("Compteurs auto-incrément : valeurs calculées (non appliquées en simulation)", "INFO",
                   ", ".join(f"{t}={e['wanted']}" for t, e in result["autoincrement"].items()))

        # 7. Schéma, anomalies, environnement -----------------------------------------------------------
        diffs = schema_diff.diff_schemas(schema_diff.fetch_schema(legacy), schema_diff.fetch_schema(default))
        result["schema_diff"] = diffs
        unexpected = [d for d in diffs if d["status"] == "INATTENDU"]
        record("Comparaison des schémas legacy ↔ Django", "ATTENTION" if unexpected else "OK",
               f"{len(diffs) - len(unexpected)} écart(s) attendu(s), {len(unexpected)} inattendu(s)")
        result["anomalies"] = anomalies.analyze(dump, getattr(settings, "TEST_LIKE_VALUES", []))
        a = result["anomalies"]
        record("Anomalies détectées (signalées, jamais corrigées)", "INFO",
               f"{len(a['corrupted'])} cellule(s) corrompue(s), {sum(len(r['invalid_values']) > 0 for r in a['relations'])} relation(s) sans correspondance complète, "
               f"{len(a['test_like'])} valeur(s) ressemblant à des essais")
        result["environment"] = {"cible": _server_info(default), "legacy": _server_info(legacy)}
    finally:
        if ro_ok:
            _set_readonly(legacy, False)

    # 8. Archive : empreintes APRÈS -------------------------------------------------------------------------
    after = {r["name"]: r for r in archive.verify_snapshot(snap)}
    for f in result["archive"]["files"]:
        f["sha256_after"] = after[f["name"]]["actual"]
        f["ok_after"] = after[f["name"]]["ok"]
    if not all(f["ok_after"] for f in result["archive"]["files"]):
        fail("Archive d'origine intacte (SHA-256 après)", "un fichier de l'archive a changé pendant l'exécution")
    record("Archive d'origine intacte (SHA-256 après exécution)")
    result["duration_s"] = round(time.perf_counter() - t0, 2)
    return result

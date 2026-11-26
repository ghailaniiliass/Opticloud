"""Tests de la migration, sur une vraie base MySQL, avec des données fictives."""
import json
import os
from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.core.management.base import CommandError
from django.db import connections
from django.test import override_settings

from apps.core.legacy import importer
from apps.core.legacy.registry import LEGACY_TABLES, get_model
from apps.core.tests.helpers import (
    EXPECTED_COUNTS, MigrationTestBase, count_all, fixture_text, legacy_execute, load_into_legacy, make_snapshot,
)
from apps.fournisseurs.models import Fournisseur
from apps.marques.models import Marque
from apps.montures.models import Monture
from apps.patients.models import Ordonnance, Patient

CORRUPTED = "\u00ef\u00bf\u00bd"    # « ï¿½ » : séquence déjà corrompue dans les données d'origine


class DryRunTests(MigrationTestBase):
    def test_dry_run_verifies_everything_but_changes_nothing(self):
        out = self.run_cmd(dry_run=True)
        self.assertIn("SIMULATION", out)
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})
        self.assertTrue((self.report_dir / "migration_report_dry_run.md").exists())
        self.assertFalse((self.report_dir / "migration_report.md").exists(), "un rapport de simulation ne remplace pas le rapport réel")
        self.assertEqual(self.report_json("migration_report_dry_run.json")["verdict"], "OK")

    def test_dry_run_does_not_touch_auto_increment_counters(self):
        self.run_cmd(dry_run=True)
        self.assertEqual(Fournisseur.objects.create(nom="x").pk, 1)


class ImportTests(MigrationTestBase):
    def setUp(self):
        super().setUp()
        self.run_cmd()

    def test_row_counts_of_the_nine_tables(self):
        self.assertEqual(count_all(), EXPECTED_COUNTS)

    def test_text_is_copied_exactly_corrupted_text_included_and_never_repaired(self):
        self.assertEqual(Monture.objects.get(pk=11).materiau, "Ac" + CORRUPTED + "tate")
        self.assertEqual(Marque.objects.get(pk="M003").description, "Marque c" + CORRUPTED + "l" + CORRUPTED + "bre")
        self.assertEqual(Marque.objects.get(pk="M004").description, "C:\\opti\\fichier\nsuite ; avec point-virgule -- et tirets")
        self.assertEqual(Marque.objects.get(pk="M001").description, "Description avec accent é et apostrophe d'or")
        self.assertEqual(get_model("categorie").objects.get(pk=30).nom_categorie, "Catégorie 'test'")
        self.assertEqual(get_model("categorie").objects.get(pk=2).nom_categorie, "Lunettes d'enfant")

    def test_null_and_empty_string_stay_distinct(self):
        f2, f7 = Fournisseur.objects.get(pk=2), Fournisseur.objects.get(pk=7)
        self.assertIsNone(f2.responsable)
        self.assertEqual((f7.adresse, f7.telephone), ("", ""))
        self.assertIsNone(Monture.objects.get(pk=15).stock)
        self.assertEqual(Monture.objects.get(pk=15).description, "")
        self.assertEqual(Monture.objects.get(pk=12).stock, 0)

    def test_numbers_dates_and_enums_are_exact(self):
        self.assertEqual(Monture.objects.get(pk=11).prix, Decimal("2800.00"))
        self.assertEqual(Monture.objects.get(pk=11).genre, "femme")
        lt = get_model("lentille").objects.get(pk="LT001")
        self.assertEqual((lt.type, lt.correction, lt.puissance_min, lt.diametre), ("hebdomadaire", "sphérique", Decimal("-6.00"), Decimal("14.0")))
        self.assertEqual(get_model("lentille").objects.get(pk="LT002").type, "journalière")
        p = Patient.objects.get(pk=1)
        self.assertEqual((p.date_naissance, p.date_creation, p.sexe), (date(1992, 5, 14), datetime(2026, 4, 24, 9, 41, 53), "M"))
        self.assertEqual(Patient.objects.get(pk=3).date_creation, datetime(2026, 11, 3, 23, 59, 59))
        o = Ordonnance.objects.get(pk=1)
        self.assertEqual((o.od_sphere, o.og_axe, o.idverre_od, o.ecart_pupillaire_vl), (Decimal("-2.50"), 175, "ES19", Decimal("64.0")))

    def test_primary_keys_are_preserved_including_non_contiguous_ones(self):
        self.assertEqual(sorted(Fournisseur.objects.values_list("pk", flat=True)), [1, 2, 7])
        self.assertEqual(sorted(get_model("categorie").objects.values_list("pk", flat=True)), [1, 2, 30])

    def test_auto_increment_counters_continue_the_original_numbering(self):
        self.assertEqual(Fournisseur.objects.create(nom="Nouveau").pk, 8)
        self.assertEqual(Monture.objects.create(reference="R").pk, 16)
        self.assertEqual(Patient.objects.create(nom="N", prenom="P").pk, 4)
        self.assertEqual(Ordonnance.objects.create(idpatient=1, date_ordonnance=date(2026, 1, 1)).pk, 3)

    def test_database_defaults_still_work(self):
        m = Monture.objects.create(reference="R2")
        m.refresh_from_db()
        self.assertEqual(m.stock, 0)
        p = Patient.objects.create(nom="N", prenom="P")
        p.refresh_from_db()
        self.assertIsNotNone(p.date_creation)

    def test_report_files_describe_the_migration(self):
        md = (self.report_dir / "migration_report.md").read_text(encoding="utf-8")
        self.assertIn("**Verdict : OK**", md)
        for table in LEGACY_TABLES:
            self.assertIn(f"| {table} |", md)
        self.assertIn("M003", md)
        self.assertIn(CORRUPTED, md)
        self.assertIn("NON corrigé", md)
        rep = self.report_json()
        self.assertEqual(rep["verdict"], "OK")
        self.assertEqual(set(rep["tables"]), set(LEGACY_TABLES))
        for t, v in rep["tables"].items():
            counts = set(v["counts"].values())
            self.assertEqual(len(counts), 1, t)
            self.assertEqual(len(set(v["fingerprints"].values())), 1, f"empreintes différentes pour {t}")
            self.assertEqual(len(v["fingerprints"]), 4)
            self.assertTrue(v["ok"])
        self.assertTrue(all(c["status"] != "ÉCHEC" for c in rep["checks"]))

    def test_archive_hashes_are_checked_before_and_after(self):
        for f in self.report_json()["archive"]["files"]:
            self.assertTrue(f["ok_before"] and f["ok_after"])
            self.assertEqual(f["sha256_before"], f["sha256_after"])
            self.assertEqual(f["sha256_before"], f["sha256_expected"])

    def test_corrupted_text_and_dangling_relations_are_reported_not_fixed(self):
        an = self.report_json()["anomalies"]
        self.assertEqual({(c["table"], c["key"], c["column"]) for c in an["corrupted"]},
                         {("marque", "idmarque=M003", "description"), ("monture", "idmonture=11", "materiau")})
        rel = {r["child"]: r for r in an["relations"]}
        self.assertEqual(rel["monture.idmarque"]["invalid_values"], ["CH"])
        self.assertEqual(rel["monture.idfournisseur"]["valid"], 2)
        self.assertEqual(Monture.objects.get(pk=11).idmarque, "CH", "une relation sans correspondance est conservée telle quelle")

    def test_schema_differences_are_all_expected(self):
        diffs = self.report_json()["schema_diff"]
        self.assertTrue(diffs)
        self.assertEqual([d for d in diffs if d["status"] == "INATTENDU"], [])
        elements = {(d["table"], d["element"]) for d in diffs}
        self.assertIn(("categorie", "clé primaire"), elements)
        self.assertIn(("client", "clé primaire"), elements)
        self.assertIn(("monture", "colonne genre : type"), elements)

    def test_legacy_connection_is_left_writable_for_the_next_run(self):
        legacy_execute("CREATE TABLE IF NOT EXISTS `autre` (`id` int)")
        legacy_execute("DROP TABLE `autre`")

    def test_second_import_is_refused_when_the_target_is_not_empty(self):
        with self.assertRaises(CommandError):
            self.run_cmd()
        self.assertIn("vide", self.err.getvalue())
        self.assertEqual(count_all(), EXPECTED_COUNTS)


class ResetTests(MigrationTestBase):
    def setUp(self):
        super().setUp()
        self.run_cmd()

    def test_reset_without_confirmation_is_refused_and_deletes_nothing(self):
        Monture.objects.filter(pk=11).update(reference="MODIFIÉ")
        with self.assertRaisesMessage(CommandError, "--confirm-database"):
            self.run_cmd(reset=True)
        self.assertEqual(Monture.objects.get(pk=11).reference, "MODIFIÉ")
        self.assertEqual(count_all(), EXPECTED_COUNTS)

    def test_reset_with_a_wrong_database_name_is_refused(self):
        for typed in ("opti_cloud_legacy", "opti cloud", self.target_name.upper(), "autre_base"):
            with self.subTest(typed):
                with self.assertRaises(CommandError):
                    self.run_cmd(reset=True, confirm_database=typed)
        self.assertEqual(count_all(), EXPECTED_COUNTS)

    def test_confirmation_without_reset_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "--reset"):
            self.run_cmd(confirm_database=self.target_name)

    def test_reset_restores_the_original_data_in_one_transaction(self):
        Monture.objects.filter(pk=11).update(reference="MODIFIÉ")
        Monture.objects.create(reference="INTRUS")
        self.assertEqual(Monture.objects.count(), 4)
        self.run_cmd(reset=True, confirm_database=self.target_name)
        self.assertEqual(count_all(), EXPECTED_COUNTS)
        self.assertEqual(Monture.objects.get(pk=11).reference, "REF011")
        self.assertEqual(Monture.objects.create(reference="R").pk, 16)

    def test_reset_is_refused_on_a_protected_database(self):
        with override_settings(PROTECTED_DATABASES=[self.target_name]):
            with self.assertRaisesMessage(CommandError, "PROTÉGÉE"):
                self.run_cmd(reset=True, confirm_database=self.target_name)
        self.assertEqual(count_all(), EXPECTED_COUNTS)

    def test_dry_run_with_reset_leaves_existing_data_untouched(self):
        Monture.objects.filter(pk=11).update(reference="MODIFIÉ")
        self.run_cmd(dry_run=True, reset=True, confirm_database=self.target_name)
        self.assertEqual(Monture.objects.get(pk=11).reference, "MODIFIÉ")
        self.assertEqual(count_all(), EXPECTED_COUNTS)

    def test_reset_refuses_the_legacy_database_as_target(self):
        legacy = connections["legacy"].settings_dict["NAME"]
        patched = dict(connections["default"].settings_dict, NAME=legacy)
        with mock.patch.dict(connections["default"].settings_dict, patched):
            with self.assertRaises(CommandError):
                self.run_cmd(reset=True, confirm_database=legacy)
        self.assertEqual(count_all(), EXPECTED_COUNTS)


def _evil_reader(real, table_name="marque"):
    """Simule une altération des données écrites : le contrôle INTERNE à la transaction doit tout annuler."""
    def evil(conn, table):
        rs = real(conn, table)
        if table.name == table_name and rs.rows:
            first = next(iter(rs.rows))
            rs.rows[first][1] = ["s", "ALTÉRÉ"]
        return rs
    return evil


class FailureAndRollbackTests(MigrationTestBase):
    def assertFailed(self, text):
        with self.assertRaises(CommandError):
            self.run_cmd()
        self.assertIn(text, self.err.getvalue() + self.out.getvalue())
        self.assertTrue((self.report_dir / "migration_report_ECHEC.md").exists())
        self.assertFalse((self.report_dir / "migration_report.md").exists())

    def test_altered_legacy_value_is_detected_before_any_write(self):
        legacy_execute("UPDATE `marque` SET `nom` = 'ALTÉRÉ' WHERE `idmarque` = 'M001'")
        self.assertFailed("Copie legacy identique au fichier SQL")
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_double_encoded_text_in_legacy_is_detected(self):
        legacy_execute("UPDATE `marque` SET `description` = 'Description avec accent Ã© et apostrophe d\\'or' WHERE `idmarque` = 'M001'")
        self.assertFailed("Copie legacy identique au fichier SQL")
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_row_missing_in_legacy_is_detected(self):
        legacy_execute("DELETE FROM `monture` WHERE `idmonture` = 12")
        self.assertFailed("Copie legacy identique au fichier SQL")
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_missing_legacy_table_is_detected(self):
        legacy_execute("DROP TABLE `client`")
        self.assertFailed("Les 9 tables sont chargées")

    def test_unmigrated_extra_table_in_legacy_is_detected(self):
        legacy_execute("CREATE TABLE `autre` (`id` int)")
        self.assertFailed("Aucune table de la copie legacy oubliée")

    def test_verification_failure_inside_the_transaction_rolls_everything_back(self):
        with mock.patch.object(importer, "_read_target_sql", _evil_reader(importer._read_target_sql)):
            self.assertFailed("TRANSACTION ANNULÉE")
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES}, "aucune ligne ne doit subsister")
        self.assertEqual(Fournisseur.objects.create(nom="x").pk, 1, "les compteurs n'ont pas été modifiés")

    def test_failed_reset_keeps_the_previous_data(self):
        self.run_cmd()
        Monture.objects.filter(pk=11).update(reference="MODIFIÉ")
        with mock.patch.object(importer, "_read_target_sql", _evil_reader(importer._read_target_sql)):
            with self.assertRaises(CommandError):
                self.run_cmd(reset=True, confirm_database=self.target_name)
        self.assertEqual(count_all(), EXPECTED_COUNTS, "le --reset annulé ne doit rien supprimer")
        self.assertEqual(Monture.objects.get(pk=11).reference, "MODIFIÉ")

    def test_tampered_archive_is_refused_and_nothing_is_written(self):
        victim = self.snapshot / "opti cloud.sql"
        os.chmod(victim, 0o644)
        victim.write_bytes(victim.read_bytes() + b"\n-- altere")
        with self.assertRaisesMessage(CommandError, "SHA-256"):
            self.run_cmd()
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_dump_with_a_table_that_has_no_model_aborts(self):
        text = fixture_text() + "\nCREATE TABLE `autre` (\n  `id` int(11) NOT NULL,\n  PRIMARY KEY  (`id`)\n) ENGINE=InnoDB DEFAULT CHARSET=latin1;\n"
        archive_dir, _, _ = make_snapshot(self.tmp / "v2", text) if (self.tmp / "v2").mkdir() is None else (None, None, None)
        with self.assertRaises(CommandError):
            self.run_cmd(archive_dir=str(archive_dir))
        self.assertIn("sans modèle Django", self.err.getvalue())
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_dump_with_a_column_that_has_no_field_aborts(self):
        text = fixture_text().replace("  `nom_client` varchar(100) NOT NULL,", "  `nom_client` varchar(100) NOT NULL,\n  `fax` varchar(20) default NULL,")
        self.assertIn("`fax`", text)
        (self.tmp / "v2").mkdir()
        archive_dir, _, _ = make_snapshot(self.tmp / "v2", text)
        with self.assertRaises(CommandError):
            self.run_cmd(archive_dir=str(archive_dir))
        self.assertIn("client.fax", self.err.getvalue())
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_character_outside_latin1_aborts_before_comparing_with_legacy(self):
        text = fixture_text().replace("Brand Two", "Brand Ś")
        (self.tmp / "v2").mkdir()
        archive_dir, _, _ = make_snapshot(self.tmp / "v2", text)
        with self.assertRaises(CommandError):
            self.run_cmd(archive_dir=str(archive_dir))
        self.assertIn("U+015A", self.err.getvalue())
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_protected_database_is_refused_even_for_a_dry_run(self):
        with override_settings(PROTECTED_DATABASES=[self.target_name]):
            with self.assertRaisesMessage(CommandError, "PROTÉGÉE"):
                self.run_cmd(dry_run=True)
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_target_that_is_not_the_django_database_is_refused(self):
        with mock.patch("apps.core.legacy.importer.safety.target_is_django_db", return_value=False):
            self.assertFailed("base cible est bien la base Django")
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})

    def test_a_failed_run_never_modifies_the_archive(self):
        legacy_execute("UPDATE `marque` SET `nom` = 'ALTÉRÉ' WHERE `idmarque` = 'M001'")
        before = {p.name: p.read_bytes() for p in self.snapshot.iterdir()}
        with self.assertRaises(CommandError):
            self.run_cmd()
        self.assertEqual({p.name: p.read_bytes() for p in self.snapshot.iterdir()}, before)


class TestLikeValuesTests(MigrationTestBase):
    """Détection des valeurs « d'essai » : générique, et complétée par une liste personnelle (TEST_LIKE_VALUES). Jamais de suppression."""

    # Le jeu de test contient déjà deux valeurs contenant le mot « test » (volontairement, pour les apostrophes et la ponctuation).
    BASELINE = {("categorie", "Catégorie 'test'"), ("ordonnance", "Dr. Test")}

    def flagged(self, text=None, extra=()):
        from apps.core.legacy.anomalies import analyze
        from apps.core.legacy.dumpparser import parse_dump_text
        return {(x["table"], x["value"]) for x in analyze(parse_dump_text(text or fixture_text()), extra)["test_like"]}

    def test_generic_patterns_flag_obvious_test_entries_without_deleting_them(self):
        text = fixture_text().replace("'Marque Un'", "'Marqueeeee Un'").replace("'Optique générale'", "'TESTING'").replace("'Brand Two'", "'000000'")
        self.assertEqual(self.flagged(text), self.BASELINE | {("marque", "Marqueeeee Un"), ("categorie", "TESTING"), ("marque", "000000")})

    def test_ordinary_values_are_not_flagged(self):
        self.assertEqual(self.flagged(), self.BASELINE)

    def test_a_personal_watchlist_adds_values(self):
        self.assertEqual(self.flagged(extra=["Société Béta"]), self.BASELINE | {("fournisseur", "Société Béta")})

    def test_the_import_report_uses_the_env_setting_and_deletes_nothing(self):
        with override_settings(TEST_LIKE_VALUES=["Lunettes d'enfant"]):
            self.run_cmd(dry_run=True)
        flagged = {x["value"] for x in self.report_json("migration_report_dry_run.json")["anomalies"]["test_like"]}
        self.assertEqual(flagged, {"Catégorie 'test'", "Dr. Test", "Lunettes d'enfant"})
        self.assertEqual(count_all(), {t: 0 for t in LEGACY_TABLES})        # simulation : rien n'est écrit, et jamais rien n'est supprimé

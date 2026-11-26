from django.apps import apps
from django.core.management import call_command
from django.db import models
from django.test import SimpleTestCase, TestCase

from apps.core.legacy import model_parity
from apps.core.legacy.dumpparser import parse_dump_file
from apps.core.legacy.registry import LEGACY_TABLES, get_model
from apps.core.tests.helpers import FIXTURE


class ModelStructureTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dump = parse_dump_file(FIXTURE)

    def test_nine_models_with_original_table_names(self):
        for table in LEGACY_TABLES:
            self.assertEqual(get_model(table)._meta.db_table, table)
        self.assertEqual(len(LEGACY_TABLES), 9)

    def test_models_reproduce_the_original_structure_exactly(self):
        self.assertEqual(model_parity.check_table_set(self.dump), [])
        self.assertEqual(model_parity.check_model_parity(self.dump), [])

    def test_categorie_and_client_use_their_existing_unique_column_as_primary_key(self):
        for table, col in (("categorie", "id_categorie"), ("client", "id_client")):
            model = get_model(table)
            names = [f.name for f in model._meta.concrete_fields]
            self.assertEqual(model._meta.pk.name, col)
            self.assertNotIn("id", names, "aucune colonne id supplémentaire ne doit être ajoutée")
            self.assertNotIsInstance(model._meta.pk, models.AutoField)

    def test_auto_increment_tables(self):
        for table in ("fournisseur", "monture", "patient", "ordonnance"):
            self.assertIsInstance(get_model(table)._meta.pk, models.AutoField)

    def test_no_foreign_key_anywhere(self):
        for table in LEGACY_TABLES:
            self.assertFalse([f.name for f in get_model(table)._meta.get_fields() if f.is_relation], table)

    def test_enum_choices_keep_the_original_accented_values(self):
        lent = get_model("lentille")
        self.assertEqual([c[0] for c in lent._meta.get_field("type").choices], ["journalière", "hebdomadaire", "mensuelle", "annuelle"])
        self.assertEqual([c[0] for c in lent._meta.get_field("correction").choices], ["sphérique", "torique", "multifocale"])
        self.assertEqual([c[0] for c in get_model("monture")._meta.get_field("genre").choices], ["homme", "femme", "enfant", "mixte"])
        self.assertEqual([c[0] for c in get_model("patient")._meta.get_field("sexe").choices], ["M", "F", "Autre"])

    def test_original_indexes_are_kept(self):
        indexed = {
            "monture": {"idmarque", "idfournisseur", "idcategorie"},
            "lentille": {"marque", "idfournisseur"},
            "ordonnance": {"idpatient", "idmonture", "idverre_od", "idverre_og", "idlentille"},
        }
        for table, cols in indexed.items():
            model = get_model(table)
            self.assertEqual({f.name for f in model._meta.concrete_fields if f.db_index}, cols)

    def test_every_model_belongs_to_a_project_app(self):
        self.assertEqual({m._meta.app_label for m in apps.get_models()}, {l.split(".")[0] for l in LEGACY_TABLES.values()})


class MigrationsInSyncTests(TestCase):
    def test_no_pending_model_change(self):
        # Lève SystemExit(1) si un modèle diffère de ses migrations.
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)

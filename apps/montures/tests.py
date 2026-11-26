"""Tests du module Montures : batterie commune (apps/core/tests/module_tests.py) + cas propres au module."""
import re
from decimal import Decimal

from django.test import TestCase

from apps.core.tests.module_tests import ModuleBehaviour

from .forms import MontureForm
from .models import Monture


class MontureModuleTests(ModuleBehaviour, TestCase):
    prefix = "/montures/"
    model = Monture
    form_class = MontureForm
    pk_name = "idmonture"
    pk_kind = "autoint"
    pk_editable = False                      # règle d'origine : « ID Monture » en lecture seule à la modification
    required = ("reference", "modele", "couleur", "materiau", "genre", "prix", "stock", "idmarque", "idfournisseur", "idcategorie")
    select_fields = ("genre",)
    numeric_fields = ("prix", "stock", "idfournisseur")
    max_lengths = {"reference": 50, "modele": 100, "couleur": 50, "materiau": 50, "idmarque": 10, "idcategorie": 10, "description": 255}
    nullable = ("modele", "couleur", "materiau", "genre", "prix", "stock", "idmarque", "idfournisseur", "idcategorie", "description")
    text_field = "modele"
    add_labels = edit_labels = ("ID Monture", "Référence", "Modèle", "Couleur", "Matériau", "Genre", "Prix", "Stock",
                                "Marque (ID)", "Fournisseur (ID)", "Catégorie (ID)", "Description")
    add_header = "Formulaire Monture"
    edit_header = "Modifier Monture"
    list_texts = ("Gestion des montures", "Liste des montures", "Nombre de montures", "Monture optique", "reference-pill", "gender-pill",
                  "stock-pill", "Gérez les références, modèles, couleurs, matériaux, prix et stock des montures.", "module_montures.css")
    empty_texts = ("Aucune monture trouvée", "Commencez par ajouter une nouvelle monture.")
    confirm_texts = ("supprimer cette monture", "ID Monture", "Modèle")
    pdf_title = "Liste des montures"
    pdf_headers = ("ID", "Ref", "Modèle", "Couleur", "Matériau", "Genre", "Prix", "Stock", "Marque", "Fourn.", "Cat.")
    pdf_total = "Nombre total de montures"
    pdf_filename = "liste_montures.pdf"
    pdf_landscape = True

    def fields(self, i=1, **over):
        values = {"idmonture": self.pk_value(i), "reference": f"R{i}", "modele": f"Model {i}", "couleur": "Noir", "materiau": "Acétate",
                  "genre": "femme", "prix": "1500.00", "stock": "7", "idmarque": "M001", "idfournisseur": "1", "idcategorie": "CAT01",
                  "description": f"Desc {i}"}
        values.update(over)
        return values

    # ---- cas propres au module ----
    def test_the_add_button_works_the_original_pointed_to_a_file_that_does_not_exist(self):
        self.assertIn('href="/montures/ajouter/"', self.page(self.url()))
        self.assertEqual(self.client.get("/montures/ajouter/").status_code, 200)
        self.assertNotIn("monture_add_form", self.page(self.url()))

    def test_genre_is_a_dropdown_with_only_the_valid_values(self):
        html = self.page(self.url("ajouter/"))
        self.assertEqual(html.count("<select"), 1)
        for value in ("homme", "femme", "enfant", "mixte"):
            self.assertIn(f'<option value="{value}">', html)

    def test_genre_is_preselected_when_editing_and_invalid_values_are_refused(self):
        obj = self.make(1, genre="enfant")
        self.assertIn('<option value="enfant" selected>', self.page(self.edit_url(obj.pk)))
        for bad in ("Homme", "garçon", ""):
            with self.subTest(bad):
                r = self.client.post(self.url("ajouter/"), self.valid_data(2, genre=bad))
                self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 1)

    def test_id_zero_is_refused_because_mysql_would_silently_replace_it(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, idmonture="0"))
        self.assertContains(r, "L&#x27;ID ne peut pas être 0.")
        self.assertEqual(self.model.objects.count(), 0)

    def test_the_id_typed_by_the_user_is_the_id_saved_and_numbering_continues_after_it(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, idmonture="7000"))
        self.assertEqual(sorted(self.model.objects.values_list("pk", flat=True)), [7000])
        self.assertEqual(self.model.objects.create(reference="auto").pk, 7001)

    def test_relations_stay_plain_text_with_no_foreign_key_check(self):
        # Décision validée : aucune clé étrangère. Les valeurs d'origine (« CH », « CAT07 ») ne correspondent à aucune ligne
        # de Marques ou de Catégories et restent acceptées telles quelles.
        self.client.post(self.url("ajouter/"), self.valid_data(1, idmarque="CH", idcategorie="CAT07", idfournisseur="99"))
        saved = self.model.objects.get(pk=self.pk_value(1))
        self.assertEqual((saved.idmarque, saved.idcategorie, saved.idfournisseur), ("CH", "CAT07", 99))

    def test_price_and_stock_are_validated(self):
        for field, bad in (("prix", "-5"), ("prix", "1.234"), ("prix", "abc"), ("stock", "-1"), ("stock", "1.5"), ("stock", "abc"), ("idfournisseur", "x")):
            with self.subTest(field=field, value=bad):
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{field: bad}))
                self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 0)

    def test_price_accepts_a_comma_and_is_shown_with_a_dot(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, prix="2800,5"))
        self.assertEqual(self.model.objects.get(pk=self.pk_value(1)).prix, Decimal("2800.50"))
        self.assertIn("2800.50 DH", self.page(self.url()))
        self.assertNotIn("2800,50", self.page(self.url()))

    def test_only_the_description_is_optional(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, description=""))
        self.assertRedirects(r, self.url())

    def test_the_list_shows_the_same_eight_columns_as_the_original(self):
        self.make(1)
        html = self.page(self.url())
        for header in ("ID", "Référence", "Modèle", "Couleur", "Matériau", "Genre", "Prix", "Stock", "Actions"):
            self.assertIn(f"<th>{header}</th>" if header != "Actions" else '<th width="140">Actions</th>', html)
        self.assertEqual(len(re.findall(r"<th[ >]", html)), 9)

    def test_the_pdf_shows_all_eleven_columns_including_the_one_the_original_cut_in_half(self):
        self.make(1, idcategorie="CAT42")
        reader, text = self.pdf_text()
        self.assertIn("Cat.", text)
        self.assertIn("CAT42", text)
        self.assertEqual(len(self.pdf_headers), 11)

    def test_a_forged_request_cannot_change_the_id(self):
        obj = self.make(1)
        self.client.post(self.edit_url(obj.pk), {**self.valid_data(1), "idmonture": "55555", "modele": "Forgé"})
        self.assertEqual(list(self.model.objects.values_list("pk", flat=True)), [obj.pk])
        self.assertEqual(self.model.objects.get(pk=obj.pk).modele, "Forgé")

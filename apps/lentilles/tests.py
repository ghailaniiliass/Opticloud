"""Tests du module Lentilles : batterie commune (apps/core/tests/module_tests.py) + cas propres au module."""
import re
from decimal import Decimal

from django.test import TestCase

from apps.core.tests.module_tests import ModuleBehaviour

from .forms import LentilleForm
from .models import Lentille


class LentilleModuleTests(ModuleBehaviour, TestCase):
    prefix = "/lentilles/"
    model = Lentille
    form_class = LentilleForm
    pk_name = "idlentille"
    pk_kind = "str"
    pk_prefix = "LT"
    pk_max_length = 10
    pk_editable = False                      # règle d'origine : « ID Lentille » en lecture seule à la modification
    required = ("nom", "marque", "type", "materiau", "correction", "diametre", "rayon_courbure", "puissance_min",
                "puissance_max", "prix", "stock", "idfournisseur")
    select_fields = ("type", "correction")
    numeric_fields = ("diametre", "rayon_courbure", "puissance_min", "puissance_max", "prix", "stock", "idfournisseur")
    max_lengths = {"nom": 100, "marque": 5, "materiau": 50, "couleur": 50, "description": 255}
    nullable = ("marque", "type", "materiau", "correction", "couleur", "diametre", "rayon_courbure", "puissance_min",
                "puissance_max", "prix", "stock", "idfournisseur", "description")
    row_marker_per_row = 2                   # la liste affiche deux pastilles « id-pill » par ligne (ID et fournisseur)
    text_field = "nom"
    add_labels = ("ID lentille", "Nom", "Marque", "Type", "Matériau", "Correction", "Couleur", "Diamètre", "Rayon de courbure",
                  "Puissance min", "Puissance max", "Prix", "Stock", "ID fournisseur", "Description")
    edit_labels = ("ID Lentille", "Nom", "Marque", "Type", "Matériau", "Correction", "Couleur", "Diamètre", "Rayon de courbure",
                   "Puissance min", "Puissance max", "Prix", "Stock", "ID fournisseur", "Description")
    add_header = "Formulaire lentille"
    edit_header = "Modifier Lentille"
    list_texts = ("Gestion des lentilles", "Liste des lentilles", "Nombre de lentilles", "Lentille optique", "badge-type", "badge-stock",
                  "Gérez les lentilles, corrections, matériaux, couleurs, prix et stock disponible.", "module_lentilles.css",
                  "Puissance min", "Puissance max", "Diamètre")
    empty_texts = ("Aucune lentille trouvée", "Commencez par ajouter une nouvelle lentille.")
    confirm_texts = ("supprimer cette lentille", "ID Lentille")
    pdf_title = "Liste des lentilles"
    pdf_headers = ("ID", "Nom", "Marque", "Type", "Matériau", "Correction", "Couleur", "Diam", "Rayon", "P.Min", "P.Max", "Prix", "Stock", "Fourn.")
    pdf_total = "Nombre total de lentilles"
    pdf_filename = "liste_lentilles.pdf"
    pdf_landscape = True

    def fields(self, i=1, **over):
        values = {"idlentille": self.pk_value(i), "nom": f"Lens test {i}", "marque": "CK", "type": "mensuelle", "materiau": "Hydrogel",
                  "correction": "sphérique", "couleur": "bleu", "diametre": "14.2", "rayon_courbure": "8.60", "puissance_min": "-6.00",
                  "puissance_max": "4.00", "prix": "180.00", "stock": "25", "idfournisseur": "2", "description": f"Desc {i}"}
        values.update(over)
        return values

    # ---- cas propres au module ----
    def test_editing_a_lens_never_resets_its_supplier(self):
        """Bogue de l'original : le formulaire de modification n'envoyait pas « idfournisseur », que le script de mise à jour
        écrivait quand même : chaque modification remettait donc le fournisseur à 0."""
        obj = self.make(1, idfournisseur="3")
        html = self.page(self.edit_url(obj.pk))
        self.assertIn('name="idfournisseur"', html)
        self.assertIn('value="3"', html)
        self.client.post(self.edit_url(obj.pk), self.valid_data(1, nom="Renommée", idfournisseur="3"))
        saved = self.model.objects.get(pk=obj.pk)
        self.assertEqual((saved.nom, saved.idfournisseur), ("Renommée", 3))

    def test_type_and_correction_are_dropdowns_with_only_the_valid_values(self):
        html = self.page(self.url("ajouter/"))
        self.assertEqual(html.count("<select"), 2)
        for value in ("journalière", "hebdomadaire", "mensuelle", "annuelle", "sphérique", "torique", "multifocale"):
            self.assertIn(f'<option value="{value}">', html)
        self.assertEqual(html.count('class="form-select"'), 2)

    def test_the_current_values_are_preselected_when_editing(self):
        obj = self.make(1, type="annuelle", correction="multifocale")
        html = self.page(self.edit_url(obj.pk))
        self.assertIn('<option value="annuelle" selected>', html)
        self.assertIn('<option value="multifocale" selected>', html)

    def test_values_outside_the_original_enum_are_refused(self):
        for field, bad in (("type", "hebdo"), ("type", ""), ("correction", "Sphérique"), ("correction", "autre")):
            with self.subTest(field=field, value=bad):
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{field: bad}))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 0)

    def test_accented_enum_values_are_saved_exactly(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, type="journalière", correction="sphérique"))
        saved = self.model.objects.get(pk=self.pk_value(1))
        self.assertEqual((saved.type, saved.correction), ("journalière", "sphérique"))

    def test_numbers_are_validated_with_the_database_precision(self):
        cases = {"diametre": ("1000.0", "14.25", "abc"), "rayon_courbure": ("100.00", "8.123"), "puissance_min": ("1000.00", "1.234"),
                 "puissance_max": ("-1000.00",), "prix": ("-5", "1.234"), "stock": ("-1", "1.5", "abc"), "idfournisseur": ("abc", "1.5")}
        for field, bad_values in cases.items():
            for bad in bad_values:
                with self.subTest(field=field, value=bad):
                    r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{field: bad}))
                    self.assertEqual(r.status_code, 200)
                    self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 0)

    def test_negative_powers_and_comma_decimals_are_accepted(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, puissance_min="-12,50", puissance_max="+8,25", diametre="14,5"))
        saved = self.model.objects.get(pk=self.pk_value(1))
        self.assertEqual((saved.puissance_min, saved.puissance_max, saved.diametre), (Decimal("-12.50"), Decimal("8.25"), Decimal("14.5")))

    def test_decimals_are_shown_with_a_dot_like_the_original(self):
        self.make(1, diametre="14.2", puissance_min="-6.00", prix="180.00")
        html = self.page(self.url())
        for expected in ("14.2", "-6.00", "180.00 DH"):
            self.assertIn(expected, html)
        self.assertNotIn("14,2", html)
        self.assertNotIn("-6,00", html)
        self.assertIn("-6.00", self.pdf_text()[1])

    def test_couleur_and_description_are_the_only_optional_fields(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, couleur="", description=""))
        self.assertRedirects(r, self.url())

    def test_the_wide_table_keeps_its_sticky_header_and_actions_column(self):
        self.make(1)
        html = self.page(self.url())
        self.assertIn('class="actions-header"', html)
        self.assertIn("actions-cell", html)
        self.assertEqual(len(re.findall(r"<th[ >]", html)), 16)

    def test_add_form_has_icons_on_the_first_seven_fields_and_edit_form_has_none(self):
        self.assertEqual(self.page(self.url("ajouter/")).count('class="input-group-text"'), 7)
        self.assertEqual(self.page(self.edit_url(self.make(1).pk)).count("input-group-text"), 0)

    def test_the_pdf_shows_every_column_including_the_ones_the_original_cut_off(self):
        self.make(1, stock="99", idfournisseur="7")
        text = self.pdf_text()[1]
        for header in ("Stock", "Fourn."):
            self.assertIn(header, text)
        self.assertIn("99", text)

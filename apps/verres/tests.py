"""Tests du module Verres : batterie commune (apps/core/tests/module_tests.py) + cas propres au module."""
from decimal import Decimal

from django.test import TestCase

from apps.core.tests.module_tests import ModuleBehaviour

from .forms import VerreForm
from .models import Verre


class VerreModuleTests(ModuleBehaviour, TestCase):
    prefix = "/verres/"
    model = Verre
    form_class = VerreForm
    pk_name = "code_verre"
    pk_kind = "str"
    pk_prefix = "V"
    pk_max_length = 10
    pk_editable = False                      # règle d'origine : « Code Verre » en lecture seule à la modification
    required = ("nom", "type_verre", "indice", "traitement", "prix", "code_fournisseur")
    numeric_fields = ("prix",)
    max_lengths = {"nom": 100, "type_verre": 50, "indice": 10, "traitement": 50, "code_fournisseur": 10}
    nullable = ("traitement", "code_fournisseur", "description")
    row_marker = 'class="code-pill"'
    text_field = "nom"
    add_labels = edit_labels = ("Code Verre", "Nom", "Type Verre", "Indice", "Traitement", "Prix", "Code Fournisseur", "Description")
    add_header = "Ajouter Verre"
    edit_header = "Modifier Verre"
    list_texts = ("Gestion des verres", "Liste des verres", "Nombre de verres", "Verre optique", "supplier-pill", "traitement-pill",
                  "Gérez les verres optiques, types, indices, traitements, prix et fournisseurs.", "module_verres.css")
    empty_texts = ("Aucun verre trouvé", "Commencez par ajouter un nouveau verre.")
    confirm_texts = ("supprimer ce verre", "Code Verre")
    pdf_title = "Liste des verres"
    pdf_headers = ("Code", "Nom", "Type", "Indice", "Traitement", "Prix", "Fournisseur", "Description")
    pdf_total = "Nombre total de verres"
    pdf_filename = "liste_verres.pdf"
    pdf_landscape = True

    def fields(self, i=1, **over):
        values = {"code_verre": self.pk_value(i), "nom": f"Verre test {i}", "type_verre": "Progressif", "indice": "1.60",
                  "traitement": "Antireflet", "prix": "350.00", "code_fournisseur": "ES", "description": f"Description {i}"}
        values.update(over)
        return values

    # ---- cas propres au module ----
    def test_price_is_shown_with_a_dot_like_the_original_never_with_a_french_comma(self):
        self.make(1, prix="350.50")
        self.assertIn("350.50 DH", self.page(self.url()))
        self.assertIn('value="350.50"', self.page(self.edit_url(self.pk_value(1))))
        self.assertNotIn("350,50", self.page(self.url()))
        self.assertIn("350.50", self.pdf_text()[1])

    def test_price_accepts_a_comma_or_a_dot_and_is_stored_exactly(self):
        for typed, expected in (("350,50", "350.50"), ("350.5", "350.50"), (" 99 ", "99.00"), ("0", "0.00"), ("12345678.99", "12345678.99")):
            with self.subTest(typed):
                self.model.objects.all().delete()
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, prix=typed))
                self.assertRedirects(r, self.url())
                self.assertEqual(self.model.objects.get(pk=self.pk_value(1)).prix, Decimal(expected))

    def test_invalid_prices_are_refused(self):
        for bad in ("abc", "-1", "1.234", "123456789", "1e3", "1,2,3"):
            with self.subTest(bad):
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, prix=bad))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 0)

    def test_multiline_description_survives_an_edit(self):
        obj = self.make(1, description="ligne 1\nligne 2\n\nligne 4")
        self.client.post(self.edit_url(obj.pk), self.valid_data(1, description="ligne 1\r\nligne 2\r\n\r\nligne 4"))
        self.assertEqual(self.model.objects.get(pk=obj.pk).description.replace("\r\n", "\n"), "ligne 1\nligne 2\n\nligne 4")
        self.assertIn("<textarea", self.page(self.edit_url(obj.pk)))

    def test_description_is_optional(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, description=""))
        self.assertRedirects(r, self.url())

    def test_the_verre_form_has_no_icons_like_the_original(self):
        html = self.page(self.url("ajouter/"))
        self.assertNotIn("input-group-text", html)
        self.assertNotIn("bi-save", html)
        self.assertNotIn("bi-arrow-left\"></i> Retour</a>", html.replace("btn-back-dashboard", ""))
        self.assertIn("bi-box", html)

    def test_supplier_code_is_free_text_like_the_original(self):
        # Les valeurs d'origine (« ES », « HO ») ne correspondent à aucun ID de fournisseur : elles restent acceptées telles quelles.
        self.client.post(self.url("ajouter/"), self.valid_data(1, code_fournisseur="HO"))
        self.assertEqual(self.model.objects.get(pk=self.pk_value(1)).code_fournisseur, "HO")

"""Tests du module Marques : mêmes comportements contrôlés pour tous les modules (voir apps/core/tests/module_tests.py)."""
from django.test import TestCase

from apps.core.tests.module_tests import ModuleBehaviour

from .forms import MarqueForm
from .models import Marque


class MarqueModuleTests(ModuleBehaviour, TestCase):
    prefix = "/marques/"
    model = Marque
    form_class = MarqueForm
    pk_name = "idmarque"
    pk_kind = "str"
    pk_prefix = "M"
    pk_max_length = 10
    pk_editable = True                       # règle d'origine : ID modifiable
    required = ("nom", "pays", "description")
    max_lengths = {"nom": 100, "pays": 100, "description": 255}
    nullable = ("nom", "pays", "description")
    text_field = "nom"
    add_labels = ("ID marque", "NOM Marque", "Pays", "Description")
    edit_labels = ("ID Marque", "Nom marque", "Pays", "Description")
    add_header = "Formulaire marque"
    edit_header = "Modifier Marque"
    list_texts = ("Gestion des marques", "Liste des marques", "Nombre de marques", "Marque optique",
                  "Consultez, modifiez ou supprimez les marques existantes.", "country-pill", "description-cell", "module_marques.css")
    empty_texts = ("Aucune marque trouvée", "Commencez par ajouter une nouvelle marque.")
    confirm_texts = ("supprimer cette marque", "ID Marque", "Nom Marque")
    pdf_title = "Liste des marques"
    pdf_headers = ("ID", "Nom", "Pays", "Description")
    pdf_total = "Nombre total de marques"
    pdf_filename = "liste_marques.pdf"

    def fields(self, i=1, **over):
        values = {"idmarque": self.pk_value(i), "nom": f"Marque test {i}", "pays": f"Pays {i}", "description": f"Description de la marque {i}"}
        values.update(over)
        return values

    # ---- cas propres au module ----
    def test_original_values_with_corrupted_text_are_displayed_as_they_are(self):
        self.make(1, description="Marque c\u00ef\u00bf\u00bdl\u00ef\u00bf\u00bdbre")        # texte déjà corrompu dans l'original : jamais « réparé »
        self.assertIn("Marque c\u00ef\u00bf\u00bdl\u00ef\u00bf\u00bdbre", self.page(self.url()))
        self.assertIn("Marque c\u00ef\u00bf\u00bdl\u00ef\u00bf\u00bdbre", self.pdf_text()[1])

    def test_the_country_field_of_the_edit_form_has_the_same_style_as_the_others(self):
        # Dans l'original, ce champ utilisait une classe CSS inexistante (« pays-control ») et s'affichait sans style.
        html = self.page(self.edit_url(self.make(1).pk))
        self.assertNotIn("pays-control", html)
        self.assertEqual(html.count('class="form-control"'), 4)

    def test_module_css_is_scoped_to_the_marques_page(self):
        html = self.page(self.url())
        self.assertIn('class="page-list page-marques"', html)
        self.assertNotIn("module_marques.css", self.page("/categories/"))

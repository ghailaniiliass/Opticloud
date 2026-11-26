"""Tests du module Fournisseurs : mêmes comportements contrôlés pour tous les modules (voir apps/core/tests/module_tests.py)."""
from django.test import TestCase

from apps.core.tests.module_tests import ModuleBehaviour

from .forms import FournisseurForm
from .models import Fournisseur


class FournisseurModuleTests(ModuleBehaviour, TestCase):
    prefix = "/fournisseurs/"
    model = Fournisseur
    form_class = FournisseurForm
    pk_name = "idfournisseur"
    pk_kind = "autoint"
    pk_editable = True                       # règle d'origine : ID saisi à l'ajout et modifiable
    required = ("nom", "responsable", "adresse", "ville", "telephone", "email")
    max_lengths = {"nom": 100, "responsable": 100, "adresse": 200, "ville": 100, "telephone": 20, "email": 100}
    nullable = ("nom", "responsable", "adresse", "ville", "telephone", "email")
    text_field = "nom"
    add_labels = ("ID Fournisseur", "NOM Fournisseur", "Responsable", "Adresse", "Ville", "Téléphone", "Email")
    edit_labels = ("ID Fournisseur", "Nom fournisseur", "Responsable", "Adresse", "Ville", "Téléphone", "Email")
    add_header = "Formulaire Fournisseur"
    edit_header = "Modifier Fournisseur"
    list_texts = ("Gestion des fournisseurs", "Liste des fournisseurs", "Nombre de fournisseurs", "Fournisseur optique", "Téléphone",
                  "Consultez, modifiez ou supprimez les fournisseurs existants.", "email-text", "info-text", "module_fournisseurs.css")
    empty_texts = ("Aucun fournisseur trouvé", "Commencez par ajouter un nouveau fournisseur.")
    confirm_texts = ("supprimer ce fournisseur", "ID Fournisseur", "Nom Fournisseur")
    pdf_title = "Liste des fournisseurs"
    pdf_headers = ("ID", "Nom", "Responsable", "Adresse", "Ville", "Téléphone", "Email")
    pdf_total = "Nombre total de fournisseurs"
    pdf_filename = "liste_fournisseurs.pdf"
    pdf_landscape = True

    def fields(self, i=1, **over):
        values = {"idfournisseur": self.pk_value(i), "nom": f"Fournisseur test {i}", "responsable": f"Responsable {i}",
                  "adresse": f"{i} rue de l'Optique", "ville": "Tanger", "telephone": f"05390000{i:02d}", "email": f"contact{i}@exemple.ma"}
        values.update(over)
        return values

    # ---- cas propres au module ----
    def test_email_format_is_checked(self):
        for bad in ("pas-un-email", "a@b", "a b@c.ma", "@exemple.ma", "a@@exemple.ma"):
            with self.subTest(bad):
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, email=bad))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "adresse de courriel valide")
        self.assertEqual(Fournisseur.objects.count(), 0)

    def test_email_field_stays_a_text_input_like_the_original(self):
        html = self.page(self.url("ajouter/"))
        self.assertIn('name="email"', html)
        self.assertNotIn('type="email"', html)

    def test_id_zero_is_refused_because_mysql_would_silently_replace_it(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, idfournisseur="0"))
        self.assertContains(r, "L&#x27;ID ne peut pas être 0.")
        self.assertEqual(Fournisseur.objects.count(), 0)

    def test_the_id_typed_by_the_user_is_the_id_saved_not_the_next_automatic_number(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, idfournisseur="7"))
        self.client.post(self.url("ajouter/"), self.valid_data(2, idfournisseur="42"))
        self.assertEqual(sorted(Fournisseur.objects.values_list("pk", flat=True)), [7, 42])

    def test_automatic_numbering_continues_after_manually_typed_ids(self):
        # ID choisi très au-dessus du compteur courant (qui persiste d'un test à l'autre) : le suivant doit être ID + 1.
        self.client.post(self.url("ajouter/"), self.valid_data(1, idfournisseur="5000"))
        self.assertEqual(Fournisseur.objects.create(nom="Sans ID saisi").pk, 5001)

    def test_negative_id_is_accepted_like_the_original(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, idfournisseur="-5"))
        self.assertTrue(Fournisseur.objects.filter(pk=-5).exists())
        self.assertEqual(self.client.get(self.edit_url(-5)).status_code, 200)

    def test_pdf_columns_fit_exactly_in_the_landscape_page(self):
        from .pdf import FOURNISSEURS_PDF
        self.assertEqual(sum(c.width_mm for c in FOURNISSEURS_PDF.columns), 277)
        self.assertEqual([c.header for c in FOURNISSEURS_PDF.columns], list(self.pdf_headers))

    def test_long_email_is_not_cut_in_the_pdf(self):
        long_email = "prenom.nom.tres.long@fournisseur-optique-maroc.com"
        self.make(1, email=long_email)
        self.assertIn(long_email, self.pdf_text()[1].replace("\n", ""))

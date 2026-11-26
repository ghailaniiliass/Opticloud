"""Tests du module Catégories : ajout, liste, modification (ID modifiable), suppression, PDF, sécurité."""
import io

from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from pypdf import PdfReader

from apps.core.tests.html_utils import html_problems
from apps.core.tests.test_pdf import HAS_POPPLER, ink_in_margins, render_pages

from .models import Categorie

LIST, ADD, PRINT = "/categories/", "/categories/ajouter/", "/categories/imprimer/"


def edit(pk):
    return f"/categories/{pk}/modifier/"


def delete(pk):
    return f"/categories/{pk}/supprimer/"


class CategorieTestCase(TestCase):
    def make(self, *pairs):
        for pk, name in pairs:
            Categorie.objects.create(id_categorie=pk, nom_categorie=name)


class ListTests(CategorieTestCase):
    def test_empty_state(self):
        html = self.client.get(LIST).content.decode()
        self.assertIn("Aucune catégorie trouvée", html)
        self.assertIn("Commencez par ajouter une nouvelle catégorie.", html)

    def test_rows_counter_and_actions(self):
        self.make((2, "Lunetterie"), (3, "Contactologie"))
        html = self.client.get(LIST).content.decode()
        self.assertIn("Nombre de catégories", html)
        self.assertEqual(html.count('class="id-pill"'), 2)
        for expected in ("Lunetterie", "Contactologie", "Catégorie produit optique", edit(2), delete(3), ADD, PRINT):
            self.assertIn(expected, html)
        self.assertEqual(html.count('data-confirm="Confirmer la suppression ?"'), 2)

    def test_sorted_by_id(self):
        self.make((30, "C"), (2, "A"), (9, "B"))
        html = self.client.get(LIST).content.decode()
        self.assertTrue(html.index(edit(2)) < html.index(edit(9)) < html.index(edit(30)))

    def test_html_in_names_is_escaped(self):
        self.make((1, "<script>alert(1)</script>"))
        html = self.client.get(LIST).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)


class AddTests(CategorieTestCase):
    def test_form_displays_original_labels_and_csrf(self):
        html = self.client.get(ADD).content.decode()
        for expected in ("Formulaire Catégorie", "ID CATÉGORIE", "NOM CATÉGORIE", "bg-primary text-white", "Enregistrer", "csrfmiddlewaretoken"):
            self.assertIn(expected, html)

    def test_valid_post_creates_and_redirects_to_the_list(self):
        r = self.client.post(ADD, {"id_categorie": "12", "nom_categorie": "Accessoires"})
        self.assertRedirects(r, LIST)
        self.assertEqual(Categorie.objects.get(pk=12).nom_categorie, "Accessoires")

    def test_negative_and_zero_ids_are_accepted_like_the_original(self):
        for pk in ("-5", "0"):
            self.client.post(ADD, {"id_categorie": pk, "nom_categorie": f"n{pk}"})
        self.assertEqual(sorted(Categorie.objects.values_list("pk", flat=True)), [-5, 0])
        self.assertEqual(self.client.get(edit(-5)).status_code, 200)

    def test_id_already_used_is_refused_with_a_message(self):
        self.make((2, "Lunetterie"))
        r = self.client.post(ADD, {"id_categorie": "2", "nom_categorie": "Autre"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cet ID existe déjà.")
        self.assertEqual(Categorie.objects.get(pk=2).nom_categorie, "Lunetterie")
        self.assertEqual(Categorie.objects.count(), 1)

    def test_invalid_input_is_refused_and_nothing_is_saved(self):
        cases = {
            "ID vide": ({"id_categorie": "", "nom_categorie": "x"}, "Ce champ est obligatoire"),
            "ID non numérique": ({"id_categorie": "abc", "nom_categorie": "x"}, "nombre entier"),
            "ID décimal": ({"id_categorie": "1.5", "nom_categorie": "x"}, "nombre entier"),
            "ID trop grand": ({"id_categorie": "99999999999", "nom_categorie": "x"}, "inférieure ou égale"),
            "nom vide": ({"id_categorie": "1", "nom_categorie": ""}, "Ce champ est obligatoire"),
            "nom d'espaces": ({"id_categorie": "1", "nom_categorie": "   "}, "Ce champ est obligatoire"),
            "nom trop long": ({"id_categorie": "1", "nom_categorie": "x" * 51}, "50"),
        }
        for label, (data, message) in cases.items():
            with self.subTest(label):
                r = self.client.post(ADD, data)
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, message)
                self.assertContains(r, "is-invalid")
        self.assertEqual(Categorie.objects.count(), 0)

    def test_name_with_exactly_50_characters_is_accepted(self):
        self.client.post(ADD, {"id_categorie": "1", "nom_categorie": "é" * 50})
        self.assertEqual(Categorie.objects.get(pk=1).nom_categorie, "é" * 50)

    def test_sql_injection_attempt_is_stored_as_plain_text(self):
        evil = "x'); DROP TABLE categorie; --"
        self.client.post(ADD, {"id_categorie": "1", "nom_categorie": evil})
        self.assertEqual(Categorie.objects.get(pk=1).nom_categorie, evil)
        self.assertIn("categorie", connection.introspection.table_names())

    def test_a_collision_after_validation_never_overwrites_an_existing_row(self):
        """Deux personnes valident le même ID en même temps : la seconde reçoit une erreur, la première n'est pas écrasée."""
        from .forms import CategorieForm
        form = CategorieForm(data={"id_categorie": "7", "nom_categorie": "Seconde"})
        self.assertTrue(form.is_valid())
        self.make((7, "Première"))                       # la première personne enregistre entre-temps
        with self.assertRaises(IntegrityError), transaction.atomic():
            form.save()
        self.assertEqual(Categorie.objects.get(pk=7).nom_categorie, "Première")

    def test_post_without_csrf_token_is_rejected(self):
        r = Client(enforce_csrf_checks=True).post(ADD, {"id_categorie": "1", "nom_categorie": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Categorie.objects.count(), 0)

    def test_accents_and_apostrophes_survive_a_round_trip(self):
        self.client.post(ADD, {"id_categorie": "1", "nom_categorie": "Lunettes d'enfant « été »"})
        self.assertContains(self.client.get(LIST), "Lunettes d&#x27;enfant « été »")


class EditTests(CategorieTestCase):
    def test_form_is_prefilled_and_the_id_is_editable(self):
        self.make((2, "Lunetterie"))
        html = self.client.get(edit(2)).content.decode()
        for expected in ("Modifier catégorie", "bg-warning text-dark", "ID catégorie", "Nom catégorie", 'value="2"', 'value="Lunetterie"'):
            self.assertIn(expected, html)
        self.assertNotIn("disabled", html.split("<form")[1].split("</form>")[0])
        self.assertNotIn("readonly", html)

    def test_return_link_goes_to_the_list(self):
        self.make((2, "Lunetterie"))
        html = self.client.get(edit(2)).content.decode()
        self.assertIn(f'href="{LIST}" class="btn btn-secondary"', html)    # l'original pointait vers un fichier inexistant

    def test_change_only_the_name(self):
        self.make((2, "Lunetterie"))
        r = self.client.post(edit(2), {"id_categorie": "2", "nom_categorie": "Optique"})
        self.assertRedirects(r, LIST)
        self.assertEqual(Categorie.objects.get(pk=2).nom_categorie, "Optique")
        self.assertEqual(Categorie.objects.count(), 1)

    def test_change_the_id_moves_the_row_without_creating_a_copy(self):
        self.make((2, "Lunetterie"), (3, "Contactologie"))
        r = self.client.post(edit(2), {"id_categorie": "50", "nom_categorie": "Optique"})
        self.assertRedirects(r, LIST)
        self.assertFalse(Categorie.objects.filter(pk=2).exists())
        self.assertEqual(Categorie.objects.get(pk=50).nom_categorie, "Optique")
        self.assertEqual(Categorie.objects.count(), 2)
        self.assertEqual(Categorie.objects.get(pk=3).nom_categorie, "Contactologie")

    def test_change_the_id_to_an_existing_one_is_refused_and_nothing_changes(self):
        self.make((2, "Lunetterie"), (3, "Contactologie"))
        r = self.client.post(edit(2), {"id_categorie": "3", "nom_categorie": "Écrasement"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cet ID existe déjà.")
        self.assertEqual(Categorie.objects.get(pk=2).nom_categorie, "Lunetterie")
        self.assertEqual(Categorie.objects.get(pk=3).nom_categorie, "Contactologie")

    def test_invalid_edit_keeps_the_original_row(self):
        self.make((2, "Lunetterie"))
        for data in ({"id_categorie": "", "nom_categorie": "x"}, {"id_categorie": "2", "nom_categorie": ""}, {"id_categorie": "zz", "nom_categorie": "x"}):
            self.assertEqual(self.client.post(edit(2), data).status_code, 200)
        self.assertEqual(list(Categorie.objects.values_list("pk", "nom_categorie")), [(2, "Lunetterie")])

    def test_unknown_or_malformed_ids_give_404(self):
        for pk in ("999", "abc", "1.5"):
            self.assertEqual(self.client.get(edit(pk)).status_code, 404, pk)
            self.assertEqual(self.client.post(edit(pk), {"id_categorie": "1", "nom_categorie": "x"}).status_code, 404, pk)

    def test_post_without_csrf_token_is_rejected(self):
        self.make((2, "Lunetterie"))
        r = Client(enforce_csrf_checks=True).post(edit(2), {"id_categorie": "2", "nom_categorie": "Piraté"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Categorie.objects.get(pk=2).nom_categorie, "Lunetterie")


class DeleteTests(CategorieTestCase):
    def test_confirmation_page_shows_the_element_and_deletes_nothing(self):
        self.make((2, "Lunetterie"))
        html = self.client.get(delete(2)).content.decode()
        for expected in ("Confirmation de suppression", "supprimer cette catégorie", 'value="Lunetterie"', "Oui, Supprimer", "Annuler", "csrfmiddlewaretoken", "border-danger"):
            self.assertIn(expected, html)
        self.assertNotIn("service", html.lower())
        self.assertEqual(Categorie.objects.count(), 1)

    def test_delete_requires_post(self):
        self.make((2, "Lunetterie"), (3, "Contactologie"))
        self.client.get(delete(2))
        self.assertEqual(Categorie.objects.count(), 2, "un simple lien (GET) ne supprime plus rien")
        r = self.client.post(delete(2))
        self.assertRedirects(r, LIST)
        self.assertEqual(list(Categorie.objects.values_list("pk", flat=True)), [3])

    def test_post_without_csrf_token_is_rejected(self):
        self.make((2, "Lunetterie"))
        self.assertEqual(Client(enforce_csrf_checks=True).post(delete(2)).status_code, 403)
        self.assertEqual(Categorie.objects.count(), 1)

    def test_unknown_id_gives_404_for_both_methods(self):
        self.assertEqual(self.client.get(delete(999)).status_code, 404)
        self.assertEqual(self.client.post(delete(999)).status_code, 404)

    def test_cancel_returns_to_the_list(self):
        self.make((2, "Lunetterie"))
        self.assertIn(f'href="{LIST}" class="btn btn-secondary"', self.client.get(delete(2)).content.decode())


class PdfTests(CategorieTestCase):
    def test_pdf_is_displayed_inline_with_the_right_name(self):
        r = self.client.get(PRINT)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["Content-Disposition"], 'inline; filename="liste_categories.pdf"')
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_pdf_contains_every_category_and_the_total(self):
        self.make((2, "Lunetterie"), (30, "Essai"), (9, "9999"))
        reader = PdfReader(io.BytesIO(self.client.get(PRINT).content))
        text = reader.pages[0].extract_text()
        for expected in ("Liste des catégories", "ID catégorie", "Nom de la catégorie", "Lunetterie", "Essai", "9999", "Nombre total de catégories : 3", "Page 1 / 1"):
            self.assertIn(expected, text)
        self.assertNotIn("Services", text)
        self.assertEqual((round(float(reader.pages[0].mediabox.width)), round(float(reader.pages[0].mediabox.height))), (595, 842))

    def test_pdf_lists_in_id_order(self):
        self.make((30, "Cc"), (2, "Aa"), (9, "Bb"))
        text = PdfReader(io.BytesIO(self.client.get(PRINT).content)).pages[0].extract_text()
        self.assertTrue(text.index("Aa") < text.index("Bb") < text.index("Cc"))

    def test_pdf_of_a_long_list_has_several_pages_with_repeated_header(self):
        Categorie.objects.bulk_create(Categorie(id_categorie=i, nom_categorie=f"Catégorie numéro {i}") for i in range(1, 121))
        reader = PdfReader(io.BytesIO(self.client.get(PRINT).content))
        self.assertGreater(len(reader.pages), 2)
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            self.assertIn("ID catégorie", text)
            self.assertIn(f"Page {i} / {len(reader.pages)}", text)
        self.assertIn("Nombre total de catégories : 120", reader.pages[-1].extract_text())

    def test_pdf_never_prints_outside_the_margins(self):
        if not HAS_POPPLER:
            self.skipTest("pdftoppm (poppler) requis")
        Categorie.objects.bulk_create(Categorie(id_categorie=i, nom_categorie="Nom de catégorie " * 3) for i in range(1, 60))
        for img in render_pages(self.client.get(PRINT).content):
            self.assertEqual(ink_in_margins(img), {"gauche": 0, "droite": 0, "haut": 0})


class PageQualityTests(CategorieTestCase):
    def test_every_page_is_well_formed_html_and_loads_the_original_assets(self):
        self.make((2, "Lunetterie"))
        for url in (LIST, ADD, edit(2), delete(2)):
            with self.subTest(url):
                html = self.client.get(url).content.decode()
                self.assertEqual(html_problems(html), [])
                for asset in ("bootstrap@5.3.2", "bootstrap-icons@1.11.1", "/static/css/module.css", "/static/js/app.js"):
                    self.assertIn(asset, html)
                self.assertIn('lang="fr"', html)

    def test_back_to_dashboard_button_on_every_page(self):
        self.make((2, "Lunetterie"))
        for url in (LIST, ADD, edit(2), delete(2)):
            with self.subTest(url):
                html = self.client.get(url).content.decode()
                self.assertIn("Retour au tableau de bord", html)
                self.assertIn('href="/" class="btn-back-dashboard"', html)

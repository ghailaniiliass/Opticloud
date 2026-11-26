"""
Batterie de tests commune à tous les modules (Marques, Fournisseurs, puis Verres, Lentilles et Montures au jalon J4).

Un module hérite de `ModuleBehaviour` + `TestCase` et ne fournit que sa configuration (URL, modèle, textes, colonnes du PDF) :
les mêmes comportements sont ainsi contrôlés à l'identique pour chaque module.
"""
import io

from django.db import IntegrityError, connection, transaction
from django.test import Client
from pypdf import PdfReader

from apps.core.tests.html_utils import html_problems
from apps.core.tests.test_pdf import HAS_POPPLER, ink_in_margins, render_pages


class ModuleBehaviour:
    # ---------------------------------------------------------------- configuration à fournir ----------
    prefix = ""                     # ex. "/marques/"
    model = None
    form_class = None
    pk_name = ""
    pk_kind = "str"                 # "str" (texte), "int" (entier saisi) ou "autoint" (auto-incrément saisi à la main)
    pk_prefix = "M"                 # préfixe des ID de test (modules à ID texte)
    pk_max_length = 10              # modules à ID texte
    pk_editable = True              # l'ID est-il modifiable à la modification ?
    required = ()                   # champs (hors ID) obligatoires dans les formulaires d'origine
    max_lengths = {}                # champ -> longueur maximale
    nullable = ()                   # champs pouvant être NULL en base
    select_fields = ()              # champs affichés en liste déroulante (ENUM d'origine)
    numeric_fields = ()             # champs numériques (une chaîne d'espaces y est « invalide » plutôt que « obligatoire »)
    row_marker = 'class="id-pill"'  # balise qui apparaît une fois par ligne dans la liste
    row_marker_per_row = 1          # nombre de fois par ligne
    text_field = "nom"
    add_labels = ()
    edit_labels = ()
    add_header = ""
    edit_header = ""
    list_texts = ()
    empty_texts = ()
    confirm_texts = ()
    pdf_title = ""
    pdf_headers = ()
    pdf_total = ""
    pdf_filename = ""
    pdf_landscape = False

    # ---------------------------------------------------------------- à définir par le module -----------
    def fields(self, i=1, **over) -> dict:
        raise NotImplementedError

    # ---------------------------------------------------------------- outils ---------------------------
    def pk_value(self, i):
        return f"{self.pk_prefix}{900 + i}" if self.pk_kind == "str" else 900 + i

    def valid_data(self, i=1, **over) -> dict:
        return {k: str(v) for k, v in self.fields(i, **over).items()}

    def make(self, i=1, **over):
        return self.model.objects.create(**self.fields(i, **over))

    def url(self, suffix=""):
        return f"{self.prefix}{suffix}"

    def edit_url(self, pk):
        return f"{self.prefix}{pk}/modifier/"

    def delete_url(self, pk):
        return f"{self.prefix}{pk}/supprimer/"

    def page(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.content.decode()

    def pdf_text(self):
        reader = PdfReader(io.BytesIO(self.client.get(self.url("imprimer/")).content))
        return reader, "\n".join(p.extract_text() for p in reader.pages)

    # ================================================================ LISTE ===========================
    def test_list_empty_state(self):
        html = self.page(self.url())
        for text in self.empty_texts:
            self.assertIn(text, html)

    def test_list_rows_counter_and_actions(self):
        a, b = self.make(1), self.make(2)
        html = self.page(self.url())
        for text in self.list_texts:
            self.assertIn(text, html)
        self.assertEqual(html.count(self.row_marker), 2 * self.row_marker_per_row)
        for expected in (self.edit_url(a.pk), self.delete_url(b.pk), self.url("ajouter/"), self.url("imprimer/")):
            self.assertIn(expected, html)
        self.assertEqual(html.count('data-confirm="Confirmer la suppression ?"'), 2)

    def test_list_is_sorted_by_id(self):
        for i in (3, 1, 2):
            self.make(i)
        html = self.page(self.url())
        positions = [html.index(self.edit_url(self.pk_value(i))) for i in (1, 2, 3)]
        self.assertEqual(positions, sorted(positions))

    def test_empty_values_are_printed_as_empty_never_as_none(self):
        self.model.objects.create(**{self.pk_name: self.pk_value(1), **{f: None for f in self.nullable},
                                     **{f: v for f, v in self.fields(1).items() if f not in self.nullable and f != self.pk_name}})
        for url in (self.url(), self.edit_url(self.pk_value(1)), self.delete_url(self.pk_value(1))):
            self.assertNotIn("None", self.page(url), url)
        self.assertNotIn("None", self.pdf_text()[1])

    def test_html_in_text_is_escaped_everywhere(self):
        evil = "<script>alert(1)</script>"
        obj = self.make(1, **{self.text_field: evil})
        for url in (self.url(), self.edit_url(obj.pk), self.delete_url(obj.pk)):
            html = self.page(url)
            self.assertNotIn(evil, html, url)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html, url)

    # ================================================================ AJOUT ===========================
    def test_add_form_displays_original_labels_and_csrf(self):
        html = self.page(self.url("ajouter/"))
        for text in (self.add_header, "bg-primary text-white", "Enregistrer", "csrfmiddlewaretoken", *self.add_labels):
            self.assertIn(text, html)

    def test_add_valid_creates_and_redirects_to_the_list(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1))
        self.assertRedirects(r, self.url())
        self.assertEqual(self.model.objects.count(), 1)
        saved = self.model.objects.get(pk=self.pk_value(1))
        for name, value in self.fields(1).items():
            self.assertEqual(str(getattr(saved, name)), str(value), name)

    def test_add_required_fields_are_enforced(self):
        for name in self.required:
            blanks = ("",) if name in self.select_fields or name in self.numeric_fields else ("", "   ")
            for empty in blanks:
                with self.subTest(field=name, value=repr(empty)):
                    r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{name: empty}))
                    self.assertEqual(r.status_code, 200)
                    self.assertContains(r, "Ce champ est obligatoire")
        self.assertEqual(self.model.objects.count(), 0)

    def test_add_without_id_is_refused(self):
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{self.pk_name: ""}))
        self.assertContains(r, "Ce champ est obligatoire")
        self.assertEqual(self.model.objects.count(), 0)

    def test_add_too_long_values_are_refused(self):
        for name, limit in self.max_lengths.items():
            with self.subTest(field=name):
                over = "x" * (limit + 1)
                if name == "email":
                    over = "a" * (limit - 8) + "@ex.ma" + "bbbbbb"        # adresse bien formée mais trop longue
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{name: over}))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "is-invalid")
        self.assertEqual(self.model.objects.count(), 0)

    def test_add_values_at_the_exact_limit_are_accepted(self):
        for name, limit in self.max_lengths.items():
            with self.subTest(field=name):
                self.model.objects.all().delete()
                value = "é" * limit if name != "email" else "a" * (limit - 7) + "@ex.com"
                self.assertEqual(len(value), limit)
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{name: value}))
                self.assertRedirects(r, self.url())
                self.assertEqual(getattr(self.model.objects.get(pk=self.pk_value(1)), name), value)

    def test_add_invalid_id_is_refused(self):
        if self.pk_kind == "str":
            bad = {"ID trop long": "x" * (self.pk_max_length + 1)}
            message = str(self.pk_max_length)
        else:
            bad = {"ID non numérique": "abc", "ID décimal": "1.5", "ID trop grand": "99999999999"}
            message = None
        for label, value in bad.items():
            with self.subTest(label):
                r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{self.pk_name: value}))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "is-invalid")
                if message:
                    self.assertContains(r, message)
        self.assertEqual(self.model.objects.count(), 0)

    def test_add_id_already_used_is_refused_with_a_message(self):
        existing = self.make(1)
        existing.refresh_from_db()                     # valeurs relues en base (Decimal, entiers…), pas celles passées au constructeur
        before = {f: getattr(existing, f) for f in self.fields(1)}
        r = self.client.post(self.url("ajouter/"), self.valid_data(1, **{self.text_field: "Écrasement"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cet ID existe déjà.")
        self.assertEqual(self.model.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual({f: getattr(existing, f) for f in self.fields(1)}, before, "la ligne existante ne doit pas changer")

    def test_add_sql_injection_attempt_is_stored_as_plain_text(self):
        evil = "x'); DROP TABLE " + self.model._meta.db_table + "; --"
        self.client.post(self.url("ajouter/"), self.valid_data(1, **{self.text_field: evil}))
        self.assertEqual(getattr(self.model.objects.get(pk=self.pk_value(1)), self.text_field), evil)
        self.assertIn(self.model._meta.db_table, connection.introspection.table_names())

    def test_add_without_csrf_token_is_rejected(self):
        r = Client(enforce_csrf_checks=True).post(self.url("ajouter/"), self.valid_data(1))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.model.objects.count(), 0)

    def test_add_accents_and_apostrophes_survive_a_round_trip(self):
        self.client.post(self.url("ajouter/"), self.valid_data(1, **{self.text_field: "L'été « é » ï"}))
        self.assertEqual(getattr(self.model.objects.get(pk=self.pk_value(1)), self.text_field), "L'été « é » ï")

    def test_a_collision_after_validation_never_overwrites_an_existing_row(self):
        form = self.form_class(data=self.valid_data(1, **{self.text_field: "Seconde"}))
        self.assertTrue(form.is_valid(), form.errors)
        self.make(1, **{self.text_field: "Première"})                 # la première personne enregistre entre-temps
        with self.assertRaises(IntegrityError), transaction.atomic():
            form.save()
        self.assertEqual(getattr(self.model.objects.get(pk=self.pk_value(1)), self.text_field), "Première")

    # ================================================================ MODIFICATION ====================
    def test_edit_form_is_prefilled(self):
        obj = self.make(1)
        html = self.page(self.edit_url(obj.pk))
        for text in (self.edit_header, "bg-warning text-dark", *self.edit_labels, f'value="{obj.pk}"', f'value="{self.fields(1)[self.text_field]}"'):
            self.assertIn(text, html)
        self.assertIn(f'href="{self.url()}" class="btn btn-secondary"', html)     # l'original pointait parfois vers un fichier inexistant

    def test_edit_id_field_follows_the_original_rule(self):
        obj = self.make(1)
        form_html = self.page(self.edit_url(obj.pk)).split("<form")[1].split("</form>")[0]
        id_input = form_html[form_html.index(f'name="{self.pk_name}"') - 40: form_html.index(f'name="{self.pk_name}"') + 220]
        if self.pk_editable:
            self.assertNotIn("disabled", id_input)
        else:
            self.assertIn("readonly", id_input)
            self.assertNotIn("disabled", id_input)

    def test_edit_changing_only_a_text_field(self):
        obj = self.make(1)
        r = self.client.post(self.edit_url(obj.pk), self.valid_data(1, **{self.text_field: "Nouveau texte"}))
        self.assertRedirects(r, self.url())
        self.assertEqual(getattr(self.model.objects.get(pk=obj.pk), self.text_field), "Nouveau texte")
        self.assertEqual(self.model.objects.count(), 1)

    def test_edit_changing_the_id_moves_the_row_without_creating_a_copy(self):
        if not self.pk_editable:
            self.skipTest("l'ID n'est pas modifiable dans ce module")
        a, b = self.make(1), self.make(2)
        new_pk = self.pk_value(50)
        r = self.client.post(self.edit_url(a.pk), self.valid_data(50, **{self.text_field: "Déplacé"}))
        self.assertRedirects(r, self.url())
        self.assertFalse(self.model.objects.filter(pk=a.pk).exists())
        self.assertEqual(getattr(self.model.objects.get(pk=new_pk), self.text_field), "Déplacé")
        self.assertEqual(self.model.objects.count(), 2)
        self.assertEqual(getattr(self.model.objects.get(pk=b.pk), self.text_field), self.fields(2)[self.text_field])

    def test_edit_changing_the_id_to_an_existing_one_is_refused_and_nothing_changes(self):
        if not self.pk_editable:
            self.skipTest("l'ID n'est pas modifiable dans ce module")
        a, b = self.make(1), self.make(2)
        r = self.client.post(self.edit_url(a.pk), self.valid_data(2, **{self.text_field: "Écrasement"}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cet ID existe déjà.")
        self.assertEqual(getattr(self.model.objects.get(pk=a.pk), self.text_field), self.fields(1)[self.text_field])
        self.assertEqual(getattr(self.model.objects.get(pk=b.pk), self.text_field), self.fields(2)[self.text_field])

    def test_edit_readonly_id_is_never_changed_even_if_posted(self):
        if self.pk_editable:
            self.skipTest("l'ID est modifiable dans ce module")
        a = self.make(1)
        self.client.post(self.edit_url(a.pk), self.valid_data(50, **{self.text_field: "Nouveau"}))
        self.assertEqual(list(self.model.objects.values_list("pk", flat=True)), [a.pk])
        self.assertEqual(getattr(self.model.objects.get(pk=a.pk), self.text_field), "Nouveau")

    def test_edit_invalid_input_keeps_the_original_row(self):
        obj = self.make(1)
        for name in self.required:
            with self.subTest(field=name):
                r = self.client.post(self.edit_url(obj.pk), self.valid_data(1, **{name: ""}))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "Ce champ est obligatoire")
        self.assertEqual({f: str(getattr(self.model.objects.get(pk=obj.pk), f)) for f in self.fields(1)},
                         {f: str(v) for f, v in self.fields(1).items()})

    def test_edit_unknown_or_malformed_ids_give_404(self):
        bad = ["introuvable-1", "999999"] if self.pk_kind == "str" else ["abc", "1.5", "999999"]
        for pk in bad:
            self.assertEqual(self.client.get(self.edit_url(pk)).status_code, 404, pk)
            self.assertEqual(self.client.post(self.edit_url(pk), self.valid_data(1)).status_code, 404, pk)

    def test_edit_without_csrf_token_is_rejected(self):
        obj = self.make(1)
        r = Client(enforce_csrf_checks=True).post(self.edit_url(obj.pk), self.valid_data(1, **{self.text_field: "Piraté"}))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(getattr(self.model.objects.get(pk=obj.pk), self.text_field), self.fields(1)[self.text_field])

    # ================================================================ SUPPRESSION =====================
    def test_delete_confirmation_page_shows_the_element_and_deletes_nothing(self):
        obj = self.make(1)
        html = self.page(self.delete_url(obj.pk))
        for text in ("Confirmation de suppression", "Oui, Supprimer", "Annuler", "csrfmiddlewaretoken", "border-danger",
                     f'value="{obj.pk}"', f'value="{self.fields(1)[self.text_field]}"', *self.confirm_texts):
            self.assertIn(text, html)
        self.assertNotIn("service", html.lower())
        self.assertEqual(self.model.objects.count(), 1)

    def test_delete_requires_post(self):
        a, b = self.make(1), self.make(2)
        self.client.get(self.delete_url(a.pk))
        self.assertEqual(self.model.objects.count(), 2, "un simple lien (GET) ne supprime rien")
        self.assertRedirects(self.client.post(self.delete_url(a.pk)), self.url())
        self.assertEqual(list(self.model.objects.values_list("pk", flat=True)), [b.pk])

    def test_delete_without_csrf_token_is_rejected(self):
        obj = self.make(1)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.delete_url(obj.pk)).status_code, 403)
        self.assertEqual(self.model.objects.count(), 1)

    def test_delete_unknown_id_gives_404_for_both_methods(self):
        pk = "introuvable-1" if self.pk_kind == "str" else "999999"
        self.assertEqual(self.client.get(self.delete_url(pk)).status_code, 404)
        self.assertEqual(self.client.post(self.delete_url(pk)).status_code, 404)

    def test_delete_cancel_link_returns_to_the_list(self):
        obj = self.make(1)
        self.assertIn(f'href="{self.url()}" class="btn btn-secondary"', self.page(self.delete_url(obj.pk)))

    # ================================================================ PDF =============================
    def test_pdf_is_displayed_inline_with_the_right_name(self):
        r = self.client.get(self.url("imprimer/"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["Content-Disposition"], f'inline; filename="{self.pdf_filename}"')
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_pdf_has_the_right_orientation_title_columns_rows_and_total(self):
        self.make(1), self.make(2)
        reader, text = self.pdf_text()
        w, h = (round(float(reader.pages[0].mediabox.width)), round(float(reader.pages[0].mediabox.height)))
        self.assertEqual((w, h), (842, 595) if self.pdf_landscape else (595, 842))
        self.assertEqual(len(reader.pages), 1)
        for expected in (self.pdf_title, *self.pdf_headers, self.fields(1)[self.text_field], self.fields(2)[self.text_field],
                         f"{self.pdf_total} : 2", "Page 1 / 1", "Date :"):
            self.assertIn(expected, text)

    def test_pdf_of_an_empty_table_prints_header_and_zero_total(self):
        _, text = self.pdf_text()
        self.assertIn(f"{self.pdf_total} : 0", text)
        for header in self.pdf_headers:
            self.assertIn(header, text)

    def test_pdf_lists_in_id_order(self):
        for i in (3, 1, 2):
            self.make(i, **{self.text_field: f"Texte-{i}-ordre"})
        text = self.pdf_text()[1]
        self.assertTrue(text.index("Texte-1-ordre") < text.index("Texte-2-ordre") < text.index("Texte-3-ordre"))

    def test_pdf_of_a_long_list_repeats_the_header_and_numbers_the_pages(self):
        self.model.objects.bulk_create(self.model(**self.fields(i)) for i in range(1, 121))
        reader = PdfReader(io.BytesIO(self.client.get(self.url("imprimer/")).content))
        self.assertGreater(len(reader.pages), 2)
        for n, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            self.assertIn(self.pdf_headers[0], text)
            self.assertIn(self.pdf_headers[-1], text)
            self.assertIn(f"Page {n} / {len(reader.pages)}", text)
        self.assertIn(f"{self.pdf_total} : 120", reader.pages[-1].extract_text())

    def test_pdf_never_prints_outside_the_margins(self):
        if not HAS_POPPLER:
            self.skipTest("pdftoppm (poppler) requis")
        long_text = "Texte très long à retourner à la ligne " * 3
        self.model.objects.bulk_create(self.model(**self.fields(i, **{self.text_field: long_text[:self.max_lengths.get(self.text_field, 100)]}))
                                       for i in range(1, 40))
        for img in render_pages(self.client.get(self.url("imprimer/")).content):
            self.assertEqual(ink_in_margins(img), {"gauche": 0, "droite": 0, "haut": 0})

    # ================================================================ QUALITÉ DES PAGES ==============
    def test_every_page_is_well_formed_has_the_original_assets_and_a_way_back(self):
        obj = self.make(1)
        for url in (self.url(), self.url("ajouter/"), self.edit_url(obj.pk), self.delete_url(obj.pk)):
            with self.subTest(url):
                html = self.page(url)
                self.assertEqual(html_problems(html), [])
                for asset in ("bootstrap@5.3.2", "bootstrap-icons@1.11.1", "/static/css/module.css", "/static/js/app.js"):
                    self.assertIn(asset, html)
                self.assertIn('href="/" class="btn-back-dashboard"', html)
                self.assertIn("Retour au tableau de bord", html)
                self.assertNotIn(".php", html)

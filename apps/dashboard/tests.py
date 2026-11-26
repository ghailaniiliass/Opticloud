"""Tests du tableau de bord et du parcours de tous les liens du site."""
from datetime import date
from unittest import mock

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings

from apps.categories.models import Categorie
from apps.core.tests.html_utils import html_problems, internal_links
from apps.fournisseurs.models import Fournisseur
from apps.lentilles.models import Lentille
from apps.marques.models import Marque
from apps.montures.models import Monture
from apps.verres.models import Verre

import re


def counters(html: str) -> dict:
    return dict(re.findall(r'<h3>([^<]+)</h3><div class="number">(\d+)</div>', html))


class DashboardTests(TestCase):
    def test_counters_are_read_from_the_database(self):
        Fournisseur.objects.bulk_create([Fournisseur(idfournisseur=i, nom=f"F{i}") for i in (1, 2)])
        Monture.objects.create(reference="R1")
        Marque.objects.bulk_create([Marque(idmarque=f"M{i}") for i in range(3)])
        Verre.objects.create(code_verre="V1", nom="n", type_verre="t", indice="1.5", prix=1)
        Lentille.objects.bulk_create([Lentille(idlentille=f"L{i}", nom="n") for i in range(5)])
        self.assertEqual(counters(self.client.get("/").content.decode()),
                         {"Fournisseurs": "2", "Montures": "1", "Marques": "3", "Verres": "1", "Lentilles": "5"})

    def test_counters_follow_changes(self):
        self.assertEqual(counters(self.client.get("/").content.decode())["Montures"], "0")
        Monture.objects.create(reference="R1")
        self.assertEqual(counters(self.client.get("/").content.decode())["Montures"], "1")

    def test_original_structure_is_reproduced(self):
        html = self.client.get("/").content.decode()
        for expected in ("<title>Opti Cloud - Tableau de bord</title>", "Gestion d'optique", "Navigation", "Organisation", "Gestion plus rapide",
                         "Bienvenue dans votre espace professionnel Opti Cloud.", "Plateforme optique moderne",
                         "Gérez votre boutique d'optique avec plus de clarté.", "Accès rapide", "Données structurées", "Accès aux modules",
                         "Recherche rapide...", "Voir les montures", "Gérer fournisseurs", "Interface de gestion d'optique professionnelle"):
            self.assertIn(expected, html)
        self.assertEqual(html.count('class="side-link'), 7)
        self.assertEqual(html.count('class="module"'), 6)
        self.assertEqual(html.count('class="stat-card"'), 5)
        self.assertIn("font-awesome/6.5.1", html)
        self.assertNotIn("bootstrap", html.lower())
        self.assertIn("/static/css/dashboard.css", html)

    def test_shows_today_s_date(self):
        self.assertIn(date.today().strftime("%d/%m/%Y"), self.client.get("/").content.decode())

    def test_html_is_well_formed(self):
        self.assertEqual(html_problems(self.client.get("/").content.decode()), [])

    def test_no_php_leftover(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn(".php", html)
        self.assertNotIn("<?php", html)

    def test_every_module_link_leads_to_a_real_page(self):
        html = self.client.get("/").content.decode()
        links = internal_links(html)
        self.assertEqual(links, {"/", "/fournisseurs/", "/montures/", "/verres/", "/lentilles/", "/marques/", "/categories/"})
        for link in links:
            self.assertEqual(self.client.get(link).status_code, 200, link)


class SiteCrawlTests(TestCase):
    """Parcourt tout le site à partir du tableau de bord : aucun lien cassé, aucune page sans retour."""

    def test_no_broken_link_anywhere(self):
        Categorie.objects.bulk_create([Categorie(id_categorie=2, nom_categorie="A"), Categorie(id_categorie=30, nom_categorie="B")])
        Marque.objects.create(idmarque="M001", nom="Ray-Ban", pays="USA", description="d")
        Fournisseur.objects.create(idfournisseur=3, nom="Optic", responsable="r", adresse="a", ville="v", telephone="1", email="a@b.ma")
        Verre.objects.create(code_verre="V1", nom="n", type_verre="t", indice="1.5", prix=1)
        Lentille.objects.create(idlentille="L1", nom="n")
        Monture.objects.create(idmonture=11, reference="R")
        seen, queue = set(), ["/"]
        while queue:
            url = queue.pop()
            if url in seen:
                continue
            seen.add(url)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, f"lien cassé : {url}")
            if r["Content-Type"].startswith("text/html"):
                html = r.content.decode()
                self.assertEqual(html_problems(html), [], url)
                self.assertNotIn(".php", html, url)
                if url != "/":
                    self.assertIn('href="/" class="btn-back-dashboard"', html, f"pas de retour au tableau de bord : {url}")
                queue.extend(internal_links(html) - seen)
        for expected in ("/categories/", "/categories/ajouter/", "/categories/2/modifier/", "/categories/30/supprimer/", "/categories/imprimer/",
                         "/marques/", "/marques/ajouter/", "/marques/M001/modifier/", "/marques/M001/supprimer/", "/marques/imprimer/",
                         "/fournisseurs/", "/fournisseurs/ajouter/", "/fournisseurs/3/modifier/", "/fournisseurs/3/supprimer/", "/fournisseurs/imprimer/",
                         "/verres/", "/verres/ajouter/", "/verres/V1/modifier/", "/verres/V1/supprimer/", "/verres/imprimer/",
                         "/lentilles/", "/lentilles/ajouter/", "/lentilles/L1/modifier/", "/lentilles/L1/supprimer/", "/lentilles/imprimer/",
                         "/montures/", "/montures/ajouter/", "/montures/11/modifier/", "/montures/11/supprimer/", "/montures/imprimer/"):
            self.assertIn(expected, seen)

    def test_static_files_exist(self):
        for path in ("css/dashboard.css", "css/module.css", "js/app.js"):
            self.assertIsNotNone(finders.find(path), path)

    def test_delete_confirmation_script_matches_the_markup(self):
        js = open(finders.find("js/app.js"), encoding="utf-8").read()
        self.assertIn("data-confirm", js)
        self.assertIn("window.confirm", js)


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ErrorPageTests(TestCase):
    def test_404_page_has_the_site_style_and_a_way_back(self):
        r = self.client.get("/page-qui-n-existe-pas/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Page introuvable", status_code=404)
        self.assertContains(r, "Retour au tableau de bord", status_code=404)

    def test_500_page_has_the_site_style_and_a_way_back(self):
        self.client.raise_request_exception = False
        with mock.patch("apps.dashboard.views.DashboardView.get", side_effect=RuntimeError("boom")):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "Une erreur est survenue", status_code=500)
        self.assertContains(r, "Retour au tableau de bord", status_code=500)

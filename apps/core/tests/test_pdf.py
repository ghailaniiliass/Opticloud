"""Tests du moteur PDF : contenu, orientation, marges (mesurées sur le rendu image), en-tête répété, colonnes non coupées."""
import io
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

from django.test import SimpleTestCase
from pypdf import PdfReader

from apps.core.pdf import HEADER_FILL, MARGIN, PdfColumn, PdfSpec, render_pdf
from apps.core.tests.helpers import rmtree

MM = 72 / 25.4      # points par millimètre
HAS_POPPLER = shutil.which("pdftoppm") is not None


def spec(columns, landscape=False, **kw):
    return PdfSpec(title="Liste des essais", filename="essais.pdf", total_label="Nombre total d'essais",
                   columns=tuple(columns), landscape=landscape, **kw)


def pages_text(pdf: bytes) -> list[str]:
    return [p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages]


def render_pages(pdf: bytes, dpi=72) -> list:
    from PIL import Image
    tmp = Path(tempfile.mkdtemp(prefix="opticloud_pdf_"))
    try:
        (tmp / "f.pdf").write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(tmp / "f.pdf"), str(tmp / "p")], check=True)
        return [Image.open(f).convert("RGB").copy() for f in sorted(tmp.glob("p-*.png"))]
    finally:
        rmtree(tmp)


def ink_in_margins(img, dpi=72) -> dict:
    """Compte les pixels non blancs dans les marges gauche, droite et haute (10 mm, moins 1 mm de tolérance)."""
    w, h = img.size
    band = int(9 * dpi / 25.4)
    px = img.load()
    count = {"gauche": 0, "droite": 0, "haut": 0}
    for y in range(h):
        for x in range(band):
            count["gauche"] += sum(px[x, y]) < 700
            count["droite"] += sum(px[w - 1 - x, y]) < 700
    for y in range(band):
        for x in range(w):
            count["haut"] += sum(px[x, y]) < 700
    return count


COLS = [PdfColumn("ID", 40, "a", "C"), PdfColumn("Nom", 140, "b", "L")]


class PdfContentTests(SimpleTestCase):
    def test_is_a_valid_a4_portrait_pdf_with_title_date_header_rows_total_and_page_number(self):
        pdf = render_pdf(spec(COLS), [NS(a=1, b="Alpha"), NS(a=22, b="Béta d'été")], today=date(2026, 11, 8))
        self.assertTrue(pdf.startswith(b"%PDF"))
        reader = PdfReader(io.BytesIO(pdf))
        page = reader.pages[0]
        self.assertEqual((round(float(page.mediabox.width)), round(float(page.mediabox.height))), (595, 842))
        text = pages_text(pdf)[0]
        for expected in ("Liste des essais", "Date : 08/11/2026", "ID", "Nom", "Alpha", "Béta d'été", "Nombre total d'essais : 2", "Page 1 / 1"):
            self.assertIn(expected, text)
        self.assertEqual(reader.metadata.title, "Liste des essais")

    def test_landscape_is_a4_landscape(self):
        page = PdfReader(io.BytesIO(render_pdf(spec(COLS, landscape=True), []))).pages[0]
        self.assertEqual((round(float(page.mediabox.width)), round(float(page.mediabox.height))), (842, 595))

    def test_empty_list_still_prints_header_and_zero_total(self):
        text = pages_text(render_pdf(spec(COLS), []))[0]
        self.assertIn("Nombre total d'essais : 0", text)
        self.assertIn("Nom", text)

    def test_markup_and_special_characters_are_printed_literally(self):
        text = pages_text(render_pdf(spec(COLS), [NS(a="1", b="<b>gras</b> & 'x' \"y\" « z » ½ ¿ ï")]))[0]
        self.assertIn("<b>gras</b> & 'x'", text)
        self.assertIn("½ ¿ ï", text)

    def test_none_values_print_as_empty_cells(self):
        text = pages_text(render_pdf(spec(COLS), [NS(a=None, b=None)]))[0]
        self.assertNotIn("None", text)

    def test_value_can_come_from_a_function(self):
        cols = [PdfColumn("Prix", 40, lambda o: f"{o.p} DH", "R")]
        self.assertIn("25.50 DH", pages_text(render_pdf(spec(cols), [NS(p="25.50")]))[0])

    def test_footer_numbers_every_page_and_the_total_appears_once_on_the_last_page(self):
        rows = [NS(a=i, b=f"Ligne {i}") for i in range(120)]
        texts = pages_text(render_pdf(spec(COLS), rows))
        n = len(texts)
        self.assertGreater(n, 2)
        for i, t in enumerate(texts, 1):
            self.assertIn(f"Page {i} / {n}", t)
            self.assertIn("ID", t, "l'en-tête du tableau doit être répété sur chaque page")
            self.assertIn("Nom", t)
        self.assertEqual(sum("Nombre total d'essais : 120" in t for t in texts), 1)
        self.assertIn("Nombre total d'essais : 120", texts[-1])
        self.assertEqual(sum(f"Ligne {i}" in " ".join(texts) for i in range(120)), 120, "aucune ligne perdue")

    def test_wide_table_is_scaled_so_that_no_column_is_cut(self):
        heads = ["ID", "Nom", "Marque", "Type", "Matériau", "Correction", "Couleur", "Diam.", "Rayon", "Min", "Max", "Prix", "Stock", "Fourn."]
        widths = [20, 30, 25, 25, 30, 25, 20, 20, 20, 20, 20, 20, 20, 25]      # 320 mm : déborde de la page A4 paysage d'origine
        cols = [PdfColumn(h, w, f"c{i}", "C") for i, (h, w) in enumerate(zip(heads, widths))]
        rows = [NS(**{f"c{i}": f"v{i}" for i in range(14)}) for _ in range(3)]
        text = pages_text(render_pdf(spec(cols, landscape=True, header_size=9, row_size=8), rows))[0]
        for h in heads:
            self.assertIn(h, text)
        self.assertIn("v13", text, "la dernière colonne doit être imprimée")


@__import__("unittest").skipUnless(HAS_POPPLER, "pdftoppm (poppler) requis pour mesurer le rendu")
class PdfRenderingTests(SimpleTestCase):
    def test_nothing_is_printed_in_the_side_and_top_margins(self):
        for landscape, widths in ((False, [40, 140]), (True, [20, 30, 25, 25, 30, 25, 20, 20, 20, 20, 20, 20, 20, 25])):
            with self.subTest(landscape=landscape):
                cols = [PdfColumn(f"Col {i}", w, "t", "C") for i, w in enumerate(widths)]
                rows = [NS(t="Texte très long à retourner à la ligne " * 3) for _ in range(40)]
                pdf = render_pdf(spec(cols, landscape=landscape), rows)
                pages = render_pages(pdf)
                self.assertGreater(len(pages), 1)
                for number, img in enumerate(pages, 1):
                    self.assertEqual(ink_in_margins(img), {"gauche": 0, "droite": 0, "haut": 0}, f"page {number}")

    def test_header_is_the_original_blue(self):
        img = render_pages(render_pdf(spec(COLS), [NS(a=1, b="x")]), dpi=100)[0]
        want = tuple(round(c * 255) for c in (HEADER_FILL.red, HEADER_FILL.green, HEADER_FILL.blue))
        self.assertEqual(want, (52, 152, 219))
        close = sum(1 for px in img.getdata() if all(abs(a - b) <= 6 for a, b in zip(px, want)))
        self.assertGreater(close, 2000, "l'en-tête bleu RGB(52,152,219) doit être visible")

    def test_table_lines_start_at_the_10mm_margin(self):
        img = render_pages(render_pdf(spec(COLS), [NS(a=1, b="x")]), dpi=144)[0]
        px, (w, h) = img.load(), img.size
        dark_x = [x for x in range(w) if any(sum(px[x, y]) < 150 for y in range(int(h * 0.1), int(h * 0.3)))]
        self.assertAlmostEqual(min(dark_x) / (144 / 25.4), 10, delta=0.8)

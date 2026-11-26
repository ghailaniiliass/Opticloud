"""
Générateur de PDF « liste » réutilisé par tous les modules (Catégories maintenant, les autres aux jalons J3 et J4).

Reproduit la présentation des PDF PHP d'origine (FPDF) :
  * A4, marges de 10 mm, saut de page à 20 mm du bas ;
  * titre centré en gras 16 pt, date en haut à droite, ligne de total en bas ;
  * en-tête de tableau bleu RGB(52, 152, 219) en texte blanc gras, cellules encadrées ;
  * pied de page « Page x / y » centré en italique 9 pt.

Corrections par rapport à l'original (décision validée, « option A ») :
  * aucune colonne n'est coupée : si le tableau dépasse la zone utile, les largeurs sont réduites proportionnellement ;
  * aucun texte ne sort des marges : le texte long passe à la ligne au lieu d'être tronqué ;
  * l'en-tête du tableau est répété sur chaque page ;
  * police Liberation Sans (équivalent métrique d'Arial) intégrée : accents et caractères Unicode corrects.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

FONT_DIR = Path(__file__).resolve().parent / "fonts"
HEADER_FILL = colors.Color(52 / 255, 152 / 255, 219 / 255)     # bleu de l'en-tête d'origine
MARGIN = 10 * mm            # marges gauche, droite et haute (défaut FPDF)
BOTTOM_MARGIN = 20 * mm     # saut de page automatique à 2 cm du bas (défaut FPDF)
LINE_WIDTH = 0.2 * mm       # épaisseur des traits d'origine
_ALIGN = {"L": TA_LEFT, "C": TA_CENTER, "R": TA_RIGHT}
_registered = False


_FONT_MAP = {
    "OptiSans": "OptiSans",
    "OptiSans-Bold": "OptiSans-Bold",
    "OptiSans-Italic": "OptiSans-Italic",
    "OptiSans-BoldItalic": "OptiSans-BoldItalic",
}


def register_fonts() -> None:
    global _registered
    if _registered:
        return
    fonts = (
        ("OptiSans", "LiberationSans-Regular.ttf", "Helvetica"),
        ("OptiSans-Bold", "LiberationSans-Bold.ttf", "Helvetica-Bold"),
        ("OptiSans-Italic", "LiberationSans-Italic.ttf", "Helvetica-Oblique"),
        ("OptiSans-BoldItalic", "LiberationSans-BoldItalic.ttf", "Helvetica-BoldOblique"),
    )
    if all((FONT_DIR / fname).is_file() for _, fname, _ in fonts):
        for name, filename, _ in fonts:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
        pdfmetrics.registerFontFamily("OptiSans", normal="OptiSans", bold="OptiSans-Bold",
                                      italic="OptiSans-Italic", boldItalic="OptiSans-BoldItalic")
    else:
        for name, _, builtin in fonts:
            _FONT_MAP[name] = builtin
    _registered = True


@dataclass(frozen=True)
class PdfColumn:
    header: str
    width_mm: float                       # largeur de l'original, réduite automatiquement si le tableau déborde
    attr: str | Callable                  # nom de l'attribut du modèle, ou fonction(objet) -> valeur
    align: str = "L"                      # alignement des données : L, C ou R (l'en-tête est toujours centré)


@dataclass(frozen=True)
class PdfSpec:
    title: str
    filename: str
    total_label: str                      # ex. « Nombre total de catégories » (affiché suivi de « : N »)
    columns: tuple[PdfColumn, ...]
    landscape: bool = False
    header_size: float = 12
    row_size: float = 11


class _NumberedCanvas(canvas.Canvas):
    """Pied de page « Page x / y » : le nombre total de pages n'est connu qu'à la fin."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict] = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self.setFont(_FONT_MAP["OptiSans-Italic"], 9)
            self.setFillColor(colors.black)
            self.drawCentredString(self._pagesize[0] / 2, 9 * mm, f"Page {self._pageNumber} / {total}")
            super().showPage()
        super().save()


def _text(value) -> str:
    if value is None:
        return ""
    return escape(str(value)).replace("\r\n", "\n").replace("\n", "<br/>")


def _style(name: str, size: float, font="OptiSans", align="L", color=colors.black, **extra) -> ParagraphStyle:
    return ParagraphStyle(name, fontName=_FONT_MAP.get(font, font), fontSize=size, leading=size * 1.25, alignment=_ALIGN[align],
                          textColor=color, splitLongWords=1, **extra)


def render_pdf(spec: PdfSpec, rows: Iterable, today: date | None = None) -> bytes:
    """Construit le PDF et le renvoie sous forme d'octets."""
    register_fonts()
    rows = list(rows)
    pagesize = (A4[1], A4[0]) if spec.landscape else A4
    usable = pagesize[0] - 2 * MARGIN

    widths = [c.width_mm * mm for c in spec.columns]
    if sum(widths) > usable:                       # ne jamais couper de colonne : réduction proportionnelle
        factor = usable / sum(widths)
        widths = [w * factor for w in widths]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=pagesize, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                          bottomMargin=BOTTOM_MARGIN, title=spec.title, author="Opti Cloud", creator="Opti Cloud")
    frame = Frame(MARGIN, BOTTOM_MARGIN, usable, pagesize[1] - MARGIN - BOTTOM_MARGIN, id="corps",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="liste", frames=[frame], pagesize=pagesize)])

    head = _style("entete", spec.header_size, "OptiSans-Bold", "C", colors.white)
    cells = [[Paragraph(_text(c.header), head) for c in spec.columns]]
    for obj in rows:
        line = []
        for c in spec.columns:
            value = c.attr(obj) if callable(c.attr) else getattr(obj, c.attr)
            line.append(Paragraph(_text(value), _style(f"d{c.header}", spec.row_size, "OptiSans", c.align)))
        cells.append(line)

    pad_head = max((10 * mm - spec.header_size * 1.25) / 2, 2)      # hauteur mini d'origine : 10 mm
    pad_row = max((8 * mm - spec.row_size * 1.25) / 2, 2)           # hauteur mini d'origine : 8 mm
    table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("GRID", (0, 0), (-1, -1), LINE_WIDTH, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), pad_head), ("BOTTOMPADDING", (0, 0), (-1, 0), pad_head),
        ("TOPPADDING", (0, 1), (-1, -1), pad_row), ("BOTTOMPADDING", (0, 1), (-1, -1), pad_row),
    ]))

    day = (today or date.today()).strftime("%d/%m/%Y")
    story = [
        Paragraph(_text(spec.title), _style("titre", 16, "OptiSans-Bold", "C")),
        Spacer(1, 3 * mm),
        Paragraph(f"Date : {day}", _style("date", 10, "OptiSans", "R")),
        Spacer(1, 5 * mm),
        table,
        Spacer(1, 5 * mm),
        Paragraph(f"{_text(spec.total_label)} : {len(rows)}", _style("total", 11, "OptiSans-Bold", "L")),
    ]
    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()

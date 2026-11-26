from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes de verre_print.php, dans le même ordre ; paysage, comme l'original.
# Les largeurs d'origine (30+40+35+25+40+25+35+60 = 290 mm) dépassaient la page : elles sont redistribuées pour totaliser 277 mm.
VERRES_PDF = PdfSpec(
    title="Liste des verres",
    filename="liste_verres.pdf",
    total_label="Nombre total de verres",
    landscape=True,
    header_size=11,
    row_size=10,
    columns=(
        PdfColumn("Code", 24, "code_verre", "C"),
        PdfColumn("Nom", 42, "nom", "L"),
        PdfColumn("Type", 34, "type_verre", "L"),
        PdfColumn("Indice", 20, "indice", "C"),
        PdfColumn("Traitement", 36, "traitement", "L"),
        PdfColumn("Prix", 22, "prix", "C"),
        PdfColumn("Fournisseur", 30, "code_fournisseur", "C"),
        PdfColumn("Description", 69, "description", "L"),
    ),
)

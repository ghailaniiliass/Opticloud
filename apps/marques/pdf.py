from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes et largeurs de marque_print.php (20 + 40 + 40 + 90 = 190 mm) ; portrait, comme l'original.
MARQUES_PDF = PdfSpec(
    title="Liste des marques",                       # original : « Liste des marque »
    filename="liste_marques.pdf",
    total_label="Nombre total de marques",           # original : « Nombre total de  marque »
    columns=(
        PdfColumn("ID", 20, "idmarque", "C"),
        PdfColumn("Nom", 40, "nom", "L"),
        PdfColumn("Pays", 40, "pays", "L"),
        PdfColumn("Description", 90, "description", "L"),
    ),
)

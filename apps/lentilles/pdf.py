from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes de lentille_print.php, dans le même ordre ; paysage, comme l'original.
# Les largeurs d'origine totalisent 320 mm : la colonne « Fourn. » était entièrement hors de la page et « Stock » coupée.
# Elles sont ici réduites proportionnellement pour tenir dans les marges (277 mm).
LENTILLES_PDF = PdfSpec(
    title="Liste des lentilles",
    filename="liste_lentilles.pdf",
    total_label="Nombre total de lentilles",
    landscape=True,
    header_size=10,
    row_size=8,
    columns=(
        PdfColumn("ID", 20, "idlentille", "C"),
        PdfColumn("Nom", 30, "nom", "L"),
        PdfColumn("Marque", 25, "marque", "L"),
        PdfColumn("Type", 25, "type", "L"),
        PdfColumn("Matériau", 30, "materiau", "L"),           # original : « Materiau »
        PdfColumn("Correction", 25, "correction", "L"),
        PdfColumn("Couleur", 20, "couleur", "L"),
        PdfColumn("Diam", 20, "diametre", "L"),
        PdfColumn("Rayon", 20, "rayon_courbure", "L"),
        PdfColumn("P.Min", 20, "puissance_min", "L"),
        PdfColumn("P.Max", 20, "puissance_max", "L"),
        PdfColumn("Prix", 20, "prix", "L"),
        PdfColumn("Stock", 20, "stock", "L"),
        PdfColumn("Fourn.", 25, "idfournisseur", "L"),
    ),
)

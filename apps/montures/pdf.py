from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes de monture_print.php, dans le même ordre ; paysage, comme l'original.
# Les largeurs d'origine totalisent 300 mm : la colonne « Cat. » était à moitié hors de la page.
# Elles sont ici réduites proportionnellement pour tenir dans les marges (277 mm).
MONTURES_PDF = PdfSpec(
    title="Liste des montures",
    filename="liste_montures.pdf",
    total_label="Nombre total de montures",
    landscape=True,
    header_size=10,
    row_size=9,
    columns=(
        PdfColumn("ID", 20, "idmonture", "C"),
        PdfColumn("Ref", 25, "reference", "L"),
        PdfColumn("Modèle", 35, "modele", "L"),                # original : « Modele »
        PdfColumn("Couleur", 25, "couleur", "L"),
        PdfColumn("Matériau", 30, "materiau", "L"),            # original : « Materiau »
        PdfColumn("Genre", 25, "genre", "L"),
        PdfColumn("Prix", 25, "prix", "L"),
        PdfColumn("Stock", 25, "stock", "L"),
        PdfColumn("Marque", 30, "idmarque", "C"),
        PdfColumn("Fourn.", 30, "idfournisseur", "C"),
        PdfColumn("Cat.", 30, "idcategorie", "C"),
    ),
)

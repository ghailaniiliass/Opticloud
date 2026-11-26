from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes et largeurs de categorie_print.php (40 + 140 mm) ; portrait, comme l'original.
CATEGORIES_PDF = PdfSpec(
    title="Liste des catégories",                    # original : « Liste des Services » (texte copié d'un autre projet)
    filename="liste_categories.pdf",
    total_label="Nombre total de catégories",
    columns=(
        PdfColumn("ID catégorie", 40, "id_categorie", "C"),
        PdfColumn("Nom de la catégorie", 140, "nom_categorie", "L"),
    ),
)

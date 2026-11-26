from apps.core.pdf import PdfColumn, PdfSpec

# Colonnes de Fornisseurs_print.php, dans le même ordre ; paysage, comme l'original.
# Les largeurs d'origine (30+45+45+45+35+35+50 = 285 mm) dépassaient la zone utile (277 mm) et coupaient les e-mails longs :
# elles sont redistribuées (colonne ID réduite, colonne Email élargie) pour totaliser exactement 277 mm.
FOURNISSEURS_PDF = PdfSpec(
    title="Liste des fournisseurs",
    filename="liste_fournisseurs.pdf",
    total_label="Nombre total de fournisseurs",
    landscape=True,
    columns=(
        PdfColumn("ID", 20, "idfournisseur", "C"),
        PdfColumn("Nom", 42, "nom", "L"),
        PdfColumn("Responsable", 42, "responsable", "L"),
        PdfColumn("Adresse", 48, "adresse", "L"),
        PdfColumn("Ville", 32, "ville", "L"),
        PdfColumn("Téléphone", 33, "telephone", "L"),          # original : « Telephone »
        PdfColumn("Email", 60, "email", "L"),
    ),
)

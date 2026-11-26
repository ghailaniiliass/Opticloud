"""Liste explicite des 9 tables d'origine et du modèle Django qui reçoit chacune.

Toute table ou colonne du dump absente de cette correspondance ARRÊTE l'import :
aucune donnée ne peut être oubliée en silence.
"""
from django.apps import apps

LEGACY_TABLES = {
    "categorie": "categories.Categorie",
    "client": "clients.Client",
    "fournisseur": "fournisseurs.Fournisseur",
    "lentille": "lentilles.Lentille",
    "marque": "marques.Marque",
    "monture": "montures.Monture",
    "ordonnance": "patients.Ordonnance",
    "patient": "patients.Patient",
    "verre": "verres.Verre",
}
# Applications Django dont les migrations prouvent que la base cible est bien la base Django.
MODEL_APP_LABELS = sorted({label.split(".")[0] for label in LEGACY_TABLES.values()})


def get_model(table: str):
    return apps.get_model(LEGACY_TABLES[table])

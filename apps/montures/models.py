from django.db import models

# Valeurs identiques à l'ENUM MySQL d'origine.
GENRE_CHOICES = [
    ("homme", "Homme"),
    ("femme", "Femme"),
    ("enfant", "Enfant"),
    ("mixte", "Mixte"),
]


class Monture(models.Model):
    idmonture = models.AutoField(primary_key=True)
    reference = models.CharField(max_length=50)
    modele = models.CharField(max_length=100, null=True, blank=True)
    couleur = models.CharField(max_length=50, null=True, blank=True)
    materiau = models.CharField(max_length=50, null=True, blank=True)
    genre = models.CharField(max_length=6, choices=GENRE_CHOICES, null=True, blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(null=True, blank=True, db_default=0)
    # Relations logiques SANS clé étrangère (décision validée) : colonnes simples, indexées comme à l'origine.
    idmarque = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    idfournisseur = models.IntegerField(null=True, blank=True, db_index=True)
    idcategorie = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "monture"
        ordering = ["idmonture"]

    def __str__(self):
        return f"{self.idmonture} – {self.reference}"

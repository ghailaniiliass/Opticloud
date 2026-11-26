from django.db import models

# Valeurs identiques aux ENUM MySQL d'origine (accents compris).
TYPE_CHOICES = [
    ("journalière", "Journalière"),
    ("hebdomadaire", "Hebdomadaire"),
    ("mensuelle", "Mensuelle"),
    ("annuelle", "Annuelle"),
]
CORRECTION_CHOICES = [
    ("sphérique", "Sphérique"),
    ("torique", "Torique"),
    ("multifocale", "Multifocale"),
]


class Lentille(models.Model):
    idlentille = models.CharField(max_length=10, primary_key=True)
    nom = models.CharField(max_length=100)
    marque = models.CharField(max_length=5, null=True, blank=True, db_index=True)
    type = models.CharField(max_length=12, choices=TYPE_CHOICES, null=True, blank=True)
    materiau = models.CharField(max_length=50, null=True, blank=True)
    correction = models.CharField(max_length=11, choices=CORRECTION_CHOICES, null=True, blank=True)
    couleur = models.CharField(max_length=50, null=True, blank=True)
    diametre = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    rayon_courbure = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    puissance_min = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puissance_max = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(null=True, blank=True, db_default=0)
    idfournisseur = models.IntegerField(null=True, blank=True, db_index=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "lentille"
        ordering = ["idlentille"]

    def __str__(self):
        return f"{self.idlentille} – {self.nom}"

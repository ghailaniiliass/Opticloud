from django.db import models


class Marque(models.Model):
    idmarque = models.CharField(max_length=10, primary_key=True)
    nom = models.CharField(max_length=100, null=True, blank=True)
    pays = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "marque"
        ordering = ["idmarque"]

    def __str__(self):
        return f"{self.idmarque} – {self.nom}"

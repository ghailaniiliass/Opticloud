from django.db import models


class Fournisseur(models.Model):
    # Colonne auto-incrémentée, mais l'ID est saisi à la main dans le formulaire d'origine.
    idfournisseur = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100, null=True, blank=True)
    responsable = models.CharField(max_length=100, null=True, blank=True)
    adresse = models.CharField(max_length=200, null=True, blank=True)
    ville = models.CharField(max_length=100, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "fournisseur"
        ordering = ["idfournisseur"]

    def __str__(self):
        return f"{self.idfournisseur} – {self.nom}"

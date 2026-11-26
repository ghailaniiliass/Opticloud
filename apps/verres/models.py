from django.db import models


class Verre(models.Model):
    code_verre = models.CharField(max_length=10, primary_key=True)
    nom = models.CharField(max_length=100)
    type_verre = models.CharField(max_length=50)
    indice = models.CharField(max_length=10)
    traitement = models.CharField(max_length=50, null=True, blank=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    # Relation logique vers fournisseur, sans clé étrangère. Les valeurs actuelles ('ES', 'HO'…) ne correspondent à aucun ID.
    code_fournisseur = models.CharField(max_length=10, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "verre"
        ordering = ["code_verre"]

    def __str__(self):
        return f"{self.code_verre} – {self.nom}"

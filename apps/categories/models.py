from django.db import models


class Categorie(models.Model):
    # Table d'origine sans clé primaire, mais avec UNIQUE KEY(id_categorie) NOT NULL :
    # cette colonne devient la clé primaire (décision validée). Aucune colonne `id` ajoutée.
    # Saisie manuelle de l'ID, comme dans l'application PHP.
    id_categorie = models.IntegerField(primary_key=True)
    nom_categorie = models.CharField(max_length=50)

    class Meta:
        db_table = "categorie"
        ordering = ["id_categorie"]

    def __str__(self):
        return f"{self.id_categorie} – {self.nom_categorie}"

from django.db import models


class Client(models.Model):
    # Même situation que `categorie` : UNIQUE KEY(id_client) NOT NULL devient la clé primaire.
    # Table vide à ce jour, aucun écran pour l'instant (phase 2).
    id_client = models.IntegerField(primary_key=True)
    nom_client = models.CharField(max_length=100)

    class Meta:
        db_table = "client"
        ordering = ["id_client"]

    def __str__(self):
        return f"{self.id_client} – {self.nom_client}"

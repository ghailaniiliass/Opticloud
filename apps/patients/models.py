from django.db import models
from django.db.models.functions import Now

# Valeurs identiques à l'ENUM MySQL d'origine.
SEXE_CHOICES = [("M", "M"), ("F", "F"), ("Autre", "Autre")]


class Patient(models.Model):
    """Table conservée avec ses données ; aucun écran pour l'instant (décision validée)."""

    id = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=50)
    prenom = models.CharField(max_length=50)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=5, choices=SEXE_CHOICES, null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    email = models.CharField(max_length=100, null=True, blank=True)
    adresse = models.TextField(null=True, blank=True)
    code_postal = models.CharField(max_length=10, null=True, blank=True)
    ville = models.CharField(max_length=50, null=True, blank=True)
    numero_securite_sociale = models.CharField(max_length=15, null=True, blank=True)
    nom_mutuelle = models.CharField(max_length=100, null=True, blank=True)
    numero_adherent_mutuelle = models.CharField(max_length=50, null=True, blank=True)
    # Origine : TIMESTAMP DEFAULT CURRENT_TIMESTAMP. Le défaut reste porté par la base.
    date_creation = models.DateTimeField(db_default=Now())
    notes_importantes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "patient"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} – {self.nom} {self.prenom}"


class Ordonnance(models.Model):
    """Table conservée avec ses données ; aucun écran pour l'instant (décision validée)."""

    idordonnance = models.AutoField(primary_key=True)
    # Relations logiques SANS clé étrangère, indexées comme à l'origine.
    idpatient = models.IntegerField(db_index=True)
    date_ordonnance = models.DateField()
    medecin = models.CharField(max_length=100, null=True, blank=True)
    od_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    od_cylindre = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    od_axe = models.IntegerField(null=True, blank=True)
    od_addition = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    og_sphere = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    og_cylindre = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    og_axe = models.IntegerField(null=True, blank=True)
    og_addition = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    ecart_pupillaire_vl = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    ecart_pupillaire_vp = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    idmonture = models.IntegerField(null=True, blank=True, db_index=True)
    idverre_od = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    idverre_og = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    idlentille = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    remarques = models.TextField(null=True, blank=True)
    date_creation = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "ordonnance"
        ordering = ["idordonnance"]

    def __str__(self):
        return f"Ordonnance {self.idordonnance} (patient {self.idpatient})"

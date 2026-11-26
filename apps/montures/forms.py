from django import forms

from apps.core.forms import ModuleForm, decimal_field

from .models import Monture


class MontureForm(ModuleForm):
    # Règles d'ID de l'original : saisi à la main à l'ajout (colonne auto-incrémentée), EN LECTURE SEULE à la modification.
    pk_name = "idmonture"
    pk_editable = False

    # Champ déclaré à la main : Django n'affiche jamais une colonne auto-incrémentée dans un formulaire.
    idmonture = forms.IntegerField(min_value=-2147483648, max_value=2147483647, widget=forms.TextInput())
    prix = decimal_field(10, 2, min_value=0)
    stock = forms.IntegerField(min_value=0, widget=forms.TextInput())
    # Relations conservées comme de simples colonnes (aucune clé étrangère, décision validée) : champs texte comme l'original.
    idfournisseur = forms.IntegerField(widget=forms.TextInput())

    class Meta:
        model = Monture
        fields = ["idmonture", "reference", "modele", "couleur", "materiau", "genre", "prix", "stock",
                  "idmarque", "idfournisseur", "idcategorie", "description"]
        widgets = {name: forms.TextInput() for name in ("reference", "modele", "couleur", "materiau", "idmarque", "idcategorie", "description")}
        # ENUM d'origine : liste déroulante avec les valeurs valides (décision validée).
        widgets["genre"] = forms.Select(attrs={"class": "form-select"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dans les formulaires PHP, tous les champs sont obligatoires sauf la description.
        for name in ("modele", "couleur", "materiau", "genre", "idmarque", "idcategorie"):
            self.fields[name].required = True

from django import forms

from apps.core.forms import ModuleForm, decimal_field

from .models import Lentille

_SELECT = forms.Select(attrs={"class": "form-select"})


class LentilleForm(ModuleForm):
    # Règles d'ID de l'original : saisi à l'ajout (10 caractères au plus), EN LECTURE SEULE à la modification.
    pk_name = "idlentille"
    pk_editable = False

    diametre = decimal_field(4, 1)
    rayon_courbure = decimal_field(4, 2)
    puissance_min = decimal_field(5, 2)
    puissance_max = decimal_field(5, 2)
    prix = decimal_field(10, 2, min_value=0)
    stock = forms.IntegerField(min_value=0, widget=forms.TextInput())
    idfournisseur = forms.IntegerField(widget=forms.TextInput())

    class Meta:
        model = Lentille
        fields = ["idlentille", "nom", "marque", "type", "materiau", "correction", "couleur", "diametre", "rayon_courbure",
                  "puissance_min", "puissance_max", "prix", "stock", "idfournisseur", "description"]
        widgets = {name: forms.TextInput() for name in ("idlentille", "nom", "marque", "materiau", "couleur", "description")}
        # ENUM d'origine : listes déroulantes avec les valeurs valides (décision validée).
        widgets.update(type=_SELECT, correction=_SELECT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dans les formulaires PHP, seuls la couleur et la description sont facultatives.
        for name in ("marque", "type", "materiau", "correction"):
            self.fields[name].required = True

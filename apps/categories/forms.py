from django import forms

from apps.core.forms import ModuleForm

from .models import Categorie


class CategorieForm(ModuleForm):
    # Règles d'ID de l'original : saisi à l'ajout, MODIFIABLE à la modification.
    pk_name = "id_categorie"
    pk_editable = True

    id_categorie = forms.IntegerField(min_value=-2147483648, max_value=2147483647, widget=forms.TextInput())

    class Meta:
        model = Categorie
        fields = ["id_categorie", "nom_categorie"]
        widgets = {
            "nom_categorie": forms.TextInput(),
        }

from django import forms

from apps.core.forms import ModuleForm

from .models import Marque


class MarqueForm(ModuleForm):
    # Règles d'ID de l'original : saisi à l'ajout (texte libre, 10 caractères au plus), MODIFIABLE à la modification.
    pk_name = "idmarque"
    pk_editable = True

    class Meta:
        model = Marque
        fields = ["idmarque", "nom", "pays", "description"]
        widgets = {name: forms.TextInput() for name in ("idmarque", "nom", "pays", "description")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Les quatre champs sont obligatoires dans les formulaires PHP d'origine (même si la base accepte NULL).
        for name in ("nom", "pays", "description"):
            self.fields[name].required = True

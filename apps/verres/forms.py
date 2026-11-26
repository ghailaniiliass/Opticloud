from django import forms

from apps.core.forms import ModuleForm, decimal_field

from .models import Verre


class VerreForm(ModuleForm):
    # Règles d'ID de l'original : « Code Verre » saisi à l'ajout (10 caractères au plus), EN LECTURE SEULE à la modification.
    pk_name = "code_verre"
    pk_editable = False

    prix = decimal_field(10, 2, min_value=0)       # champ texte comme dans le formulaire PHP ; point ou virgule acceptés

    class Meta:
        model = Verre
        fields = ["code_verre", "nom", "type_verre", "indice", "traitement", "prix", "code_fournisseur", "description"]
        widgets = {name: forms.TextInput() for name in ("code_verre", "nom", "type_verre", "indice", "traitement", "code_fournisseur")}
        # Description : zone de texte (comme le formulaire d'ajout d'origine), y compris à la modification pour ne pas écraser les retours à la ligne.
        widgets["description"] = forms.Textarea(attrs={"rows": 2})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dans le formulaire PHP, seule la description est facultative (même si la base accepte NULL pour ces colonnes).
        self.fields["traitement"].required = True
        self.fields["code_fournisseur"].required = True
        self.fields["description"].required = False

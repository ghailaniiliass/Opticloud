from django import forms

from apps.core.forms import ModuleForm

from .models import Fournisseur


class FournisseurForm(ModuleForm):
    # Règles d'ID de l'original : saisi à l'ajout (même si la colonne est auto-incrémentée), MODIFIABLE à la modification.
    pk_name = "idfournisseur"
    pk_editable = True

    # Champ déclaré à la main : Django n'affiche jamais une colonne auto-incrémentée dans un formulaire.
    idfournisseur = forms.IntegerField(min_value=-2147483648, max_value=2147483647, widget=forms.TextInput())
    # Champ texte comme dans le formulaire PHP, mais le format de l'adresse e-mail est maintenant contrôlé.
    email = forms.EmailField(max_length=100, widget=forms.TextInput())

    class Meta:
        model = Fournisseur
        fields = ["idfournisseur", "nom", "responsable", "adresse", "ville", "telephone", "email"]
        widgets = {name: forms.TextInput() for name in ("nom", "responsable", "adresse", "ville", "telephone")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tous les champs sont obligatoires dans les formulaires PHP d'origine (même si la base accepte NULL).
        for name in ("nom", "responsable", "adresse", "ville", "telephone"):
            self.fields[name].required = True

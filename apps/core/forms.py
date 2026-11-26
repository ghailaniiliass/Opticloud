"""Base commune des formulaires de modules : style Bootstrap, validation de la clé saisie à la main, clé modifiable."""
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import models, transaction


_PLAIN_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")


class CommaDecimalField(forms.DecimalField):
    """
    Nombre décimal acceptant la virgule comme séparateur (« 350,50 »), comme on l'écrit en français.
    Seule l'écriture usuelle est acceptée : pas de notation scientifique (« 1e3 ») ni de soulignés (« 1_000 »), que Python tolérerait.
    """

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if value and not _PLAIN_NUMBER.fullmatch(value):
                raise ValidationError(self.error_messages["invalid"], code="invalid")
        return super().to_python(value)


def decimal_field(max_digits: int, decimal_places: int, *, min_value=None, required=True) -> CommaDecimalField:
    """Champ décimal affiché comme un champ texte (comme dans les formulaires PHP) et accepté avec un point ou une virgule."""
    return CommaDecimalField(max_digits=max_digits, decimal_places=decimal_places, min_value=min_value,
                             required=required, localize=False, widget=forms.TextInput())


class ModuleForm(forms.ModelForm):
    """
    Reproduit les règles d'ID de l'application PHP d'origine :
      * l'ID est saisi à la main à l'ajout ;
      * `pk_editable = True`  : l'ID reste modifiable à la modification (Fournisseurs, Marques, Catégories) ;
      * `pk_editable = False` : l'ID est affiché en lecture seule à la modification (Montures, Verres, Lentilles).
    Contrairement à l'original, un ID déjà utilisé est refusé avec un message d'erreur (au lieu d'un échec silencieux).
    """

    pk_name: str | None = None
    pk_editable: bool = True
    pk_exists_message = "Cet ID existe déjà."
    pk_zero_message = "L'ID ne peut pas être 0."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_pk = None if self.instance._state.adding else self.instance.pk
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        if self.original_pk is not None and self.pk_name in self.fields:
            self.initial.setdefault(self.pk_name, self.original_pk)
            if not self.pk_editable:
                # ID en lecture seule (attribut `readonly`, comme l'original) : la valeur envoyée par le navigateur est ignorée,
                # l'ID d'origine est toujours conservé, même si quelqu'un forge la requête.
                self.fields[self.pk_name].widget.attrs["readonly"] = "readonly"
                if self.is_bound:
                    data = self.data.copy()
                    data[self.add_prefix(self.pk_name)] = str(self.original_pk)
                    self.data = data

    # -- clé auto-incrémentée saisie à la main (Fournisseurs, Montures) -------------------------------------------
    @property
    def pk_is_autofield(self) -> bool:
        return isinstance(self._meta.model._meta.pk, models.AutoField)

    def _post_clean(self):
        # Django ignore les AutoField dans les formulaires : l'ID saisi (champ déclaré dans le formulaire) est donc posé ici.
        if self.pk_name and self.pk_is_autofield and self.cleaned_data.get(self.pk_name) is not None:
            setattr(self.instance, self._meta.model._meta.pk.attname, self.cleaned_data[self.pk_name])
        super()._post_clean()

    # -- validation ---------------------------------------------------------------------------------------------
    def full_clean(self):
        super().full_clean()
        if self.is_bound:
            for name in self.errors:
                if name in self.fields:
                    widget = self.fields[name].widget
                    widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()

    def validate_unique(self):
        """Le contrôle d'unicité de la clé est fait dans clean() : celui de Django exclurait à tort la ligne en cours d'édition."""
        exclude = self._get_validation_exclusions()
        if self.pk_name:
            exclude.add(self.pk_name)
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as exc:
            self._update_errors(exc)

    def clean(self):
        cleaned = super().clean()
        if self.pk_name and self.pk_name in cleaned and cleaned[self.pk_name] is not None:
            if self.pk_is_autofield and cleaned[self.pk_name] == 0:
                # MySQL remplacerait 0 par le numéro suivant : l'ID saisi serait ignoré en silence (comme avec l'ancien MySQL).
                self.add_error(self.pk_name, self.pk_zero_message)
                return cleaned
            clash = self._meta.model.objects.filter(pk=cleaned[self.pk_name])
            if self.original_pk is not None:
                clash = clash.exclude(pk=self.original_pk)
            if clash.exists():
                self.add_error(self.pk_name, self.pk_exists_message)
        return cleaned

    # -- enregistrement -----------------------------------------------------------------------------------------
    @property
    def pk_changed(self) -> bool:
        return self.original_pk is not None and self.instance.pk != self.original_pk

    def save(self, commit=True):
        """
        * Ajout : INSERT forcé. Sans cela, Django ferait d'abord un UPDATE quand la clé est fournie et ÉCRASERAIT en silence
          une ligne existante portant le même ID (collision entre deux utilisateurs, par exemple) ; on préfère une erreur.
        * Modification avec changement d'ID : on réécrit la clé de la ligne existante (UPDATE) au lieu d'en créer une nouvelle.
        """
        if self.original_pk is None and commit:
            if self.errors:
                raise ValueError("Le formulaire n'est pas valide : enregistrement impossible.")
            self.instance.save(force_insert=True)
            self._save_m2m()
            return self.instance
        if not self.pk_changed:
            return super().save(commit=commit)
        model = self._meta.model
        values = {f.attname: getattr(self.instance, f.attname) for f in model._meta.concrete_fields}
        with transaction.atomic():
            updated = model.objects.filter(pk=self.original_pk).update(**values)
            if updated != 1:
                raise ValidationError("L'élément à modifier n'existe plus.")
        self.instance._state.adding = False
        return self.instance

"""Vues génériques CRUD + PDF, réutilisées par chaque module. Un module = quelques attributs (modèle, formulaire, textes)."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .pdf import render_pdf


def get_by_pk_or_404(model, raw_pk):
    """Retrouve un élément à partir de la valeur de l'URL ; une valeur invalide pour le type de la clé donne un 404."""
    try:
        pk = model._meta.pk.to_python(raw_pk)
    except ValidationError:
        raise Http404("Identifiant invalide")
    return get_object_or_404(model, pk=pk)


class ModuleMixin:
    namespace: str = ""          # espace de noms des URLs du module, ex. « categories »

    def url(self, name, *args):
        return reverse(f"{self.namespace}:{name}", args=args)


class ModuleListView(ModuleMixin, ListView):
    context_object_name = "objects"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["count"] = len(ctx["objects"])
        return ctx


class ModuleCreateView(ModuleMixin, CreateView):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(mode="add", list_url=self.url("list"))
        return ctx

    def get_success_url(self):
        return self.url("list")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:           # ID pris entre la validation et l'enregistrement
            form.add_error(form.pk_name, form.pk_exists_message)
            return self.form_invalid(form)


class ModuleUpdateView(ModuleMixin, UpdateView):
    def get_object(self, queryset=None):
        return get_by_pk_or_404(self.model, self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(mode="edit", list_url=self.url("list"))
        return ctx

    def get_success_url(self):
        return self.url("list")

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except IntegrityError:
            form.add_error(form.pk_name, form.pk_exists_message)
            return self.form_invalid(form)


class ModuleDeleteView(ModuleMixin, View):
    """GET : page de confirmation (ne supprime rien). POST : suppression (protégée par le jeton CSRF)."""

    model = None
    template_name = ""

    def get(self, request, pk):
        obj = get_by_pk_or_404(self.model, pk)
        return render(request, self.template_name, {"object": obj, "list_url": self.url("list"), "delete_url": self.url("delete", obj.pk)})

    def post(self, request, pk):
        get_by_pk_or_404(self.model, pk).delete()
        return redirect(self.url("list"))


class ModulePdfView(ModuleMixin, View):
    """Impression : le PDF s'affiche dans le navigateur (comme `Output('I', …)` de FPDF)."""

    model = None
    pdf_spec = None

    def get(self, request):
        content = render_pdf(self.pdf_spec, self.model.objects.all())
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{self.pdf_spec.filename}"'
        return response

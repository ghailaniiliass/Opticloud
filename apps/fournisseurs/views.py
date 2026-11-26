from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import FournisseurForm
from .models import Fournisseur
from .pdf import FOURNISSEURS_PDF

NAMESPACE = "fournisseurs"


class FournisseurListView(ModuleListView):
    namespace = NAMESPACE
    model = Fournisseur
    template_name = "fournisseurs/list.html"


class FournisseurCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "fournisseurs/form.html"


class FournisseurUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "fournisseurs/form.html"


class FournisseurDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Fournisseur
    template_name = "fournisseurs/confirm_delete.html"


class FournisseurPdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Fournisseur
    pdf_spec = FOURNISSEURS_PDF

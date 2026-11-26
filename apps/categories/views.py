from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import CategorieForm
from .models import Categorie
from .pdf import CATEGORIES_PDF

NAMESPACE = "categories"


class CategorieListView(ModuleListView):
    namespace = NAMESPACE
    model = Categorie
    template_name = "categories/list.html"


class CategorieCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Categorie
    form_class = CategorieForm
    template_name = "categories/form.html"


class CategorieUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Categorie
    form_class = CategorieForm
    template_name = "categories/form.html"


class CategorieDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Categorie
    template_name = "categories/confirm_delete.html"


class CategoriePdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Categorie
    pdf_spec = CATEGORIES_PDF

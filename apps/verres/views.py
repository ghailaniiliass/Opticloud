from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import VerreForm
from .models import Verre
from .pdf import VERRES_PDF

NAMESPACE = "verres"


class VerreListView(ModuleListView):
    namespace = NAMESPACE
    model = Verre
    template_name = "verres/list.html"


class VerreCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Verre
    form_class = VerreForm
    template_name = "verres/form.html"


class VerreUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Verre
    form_class = VerreForm
    template_name = "verres/form.html"


class VerreDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Verre
    template_name = "verres/confirm_delete.html"


class VerrePdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Verre
    pdf_spec = VERRES_PDF

from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import LentilleForm
from .models import Lentille
from .pdf import LENTILLES_PDF

NAMESPACE = "lentilles"


class LentilleListView(ModuleListView):
    namespace = NAMESPACE
    model = Lentille
    template_name = "lentilles/list.html"


class LentilleCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Lentille
    form_class = LentilleForm
    template_name = "lentilles/form.html"


class LentilleUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Lentille
    form_class = LentilleForm
    template_name = "lentilles/form.html"


class LentilleDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Lentille
    template_name = "lentilles/confirm_delete.html"


class LentillePdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Lentille
    pdf_spec = LENTILLES_PDF

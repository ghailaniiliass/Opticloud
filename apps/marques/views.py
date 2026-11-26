from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import MarqueForm
from .models import Marque
from .pdf import MARQUES_PDF

NAMESPACE = "marques"


class MarqueListView(ModuleListView):
    namespace = NAMESPACE
    model = Marque
    template_name = "marques/list.html"


class MarqueCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Marque
    form_class = MarqueForm
    template_name = "marques/form.html"


class MarqueUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Marque
    form_class = MarqueForm
    template_name = "marques/form.html"


class MarqueDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Marque
    template_name = "marques/confirm_delete.html"


class MarquePdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Marque
    pdf_spec = MARQUES_PDF

from apps.core.views import ModuleCreateView, ModuleDeleteView, ModuleListView, ModulePdfView, ModuleUpdateView

from .forms import MontureForm
from .models import Monture
from .pdf import MONTURES_PDF

NAMESPACE = "montures"


class MontureListView(ModuleListView):
    namespace = NAMESPACE
    model = Monture
    template_name = "montures/list.html"


class MontureCreateView(ModuleCreateView):
    namespace = NAMESPACE
    model = Monture
    form_class = MontureForm
    template_name = "montures/form.html"


class MontureUpdateView(ModuleUpdateView):
    namespace = NAMESPACE
    model = Monture
    form_class = MontureForm
    template_name = "montures/form.html"


class MontureDeleteView(ModuleDeleteView):
    namespace = NAMESPACE
    model = Monture
    template_name = "montures/confirm_delete.html"


class MonturePdfView(ModulePdfView):
    namespace = NAMESPACE
    model = Monture
    pdf_spec = MONTURES_PDF

from django.views.generic import TemplateView

from apps.fournisseurs.models import Fournisseur
from apps.lentilles.models import Lentille
from apps.marques.models import Marque
from apps.montures.models import Monture
from apps.verres.models import Verre


class DashboardView(TemplateView):
    """Tableau de bord : les cinq compteurs sont lus en base à chaque affichage (comme home.php)."""

    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            nb_fournisseurs=Fournisseur.objects.count(),
            nb_montures=Monture.objects.count(),
            nb_marques=Marque.objects.count(),
            nb_verres=Verre.objects.count(),
            nb_lentilles=Lentille.objects.count(),
        )
        return ctx

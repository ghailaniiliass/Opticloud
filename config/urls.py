"""URLs d'Opti Cloud : le tableau de bord et les six modules (tous reconstruits)."""
from django.urls import include, path

handler404 = "apps.core.errors.page_not_found"
handler500 = "apps.core.errors.server_error"

urlpatterns = [
    path("", include("apps.dashboard.urls")),
    path("fournisseurs/", include("apps.fournisseurs.urls")),
    path("montures/", include("apps.montures.urls")),
    path("verres/", include("apps.verres.urls")),
    path("lentilles/", include("apps.lentilles.urls")),
    path("marques/", include("apps.marques.urls")),
    path("categories/", include("apps.categories.urls")),
]

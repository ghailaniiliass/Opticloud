from django.urls import path

from . import views

app_name = "fournisseurs"
urlpatterns = [
    path("", views.FournisseurListView.as_view(), name="list"),
    path("ajouter/", views.FournisseurCreateView.as_view(), name="add"),
    path("imprimer/", views.FournisseurPdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.FournisseurUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.FournisseurDeleteView.as_view(), name="delete"),
]

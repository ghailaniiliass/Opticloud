from django.urls import path

from . import views

app_name = "lentilles"
urlpatterns = [
    path("", views.LentilleListView.as_view(), name="list"),
    path("ajouter/", views.LentilleCreateView.as_view(), name="add"),
    path("imprimer/", views.LentillePdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.LentilleUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.LentilleDeleteView.as_view(), name="delete"),
]

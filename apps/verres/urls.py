from django.urls import path

from . import views

app_name = "verres"
urlpatterns = [
    path("", views.VerreListView.as_view(), name="list"),
    path("ajouter/", views.VerreCreateView.as_view(), name="add"),
    path("imprimer/", views.VerrePdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.VerreUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.VerreDeleteView.as_view(), name="delete"),
]

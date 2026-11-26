from django.urls import path

from . import views

app_name = "marques"
urlpatterns = [
    path("", views.MarqueListView.as_view(), name="list"),
    path("ajouter/", views.MarqueCreateView.as_view(), name="add"),
    path("imprimer/", views.MarquePdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.MarqueUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.MarqueDeleteView.as_view(), name="delete"),
]

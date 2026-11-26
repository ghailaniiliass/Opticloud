from django.urls import path

from . import views

app_name = "categories"
urlpatterns = [
    path("", views.CategorieListView.as_view(), name="list"),
    path("ajouter/", views.CategorieCreateView.as_view(), name="add"),
    path("imprimer/", views.CategoriePdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.CategorieUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.CategorieDeleteView.as_view(), name="delete"),
]

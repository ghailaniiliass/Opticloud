from django.urls import path

from . import views

app_name = "montures"
urlpatterns = [
    path("", views.MontureListView.as_view(), name="list"),
    path("ajouter/", views.MontureCreateView.as_view(), name="add"),
    path("imprimer/", views.MonturePdfView.as_view(), name="print"),
    path("<path:pk>/modifier/", views.MontureUpdateView.as_view(), name="edit"),
    path("<path:pk>/supprimer/", views.MontureDeleteView.as_view(), name="delete"),
]

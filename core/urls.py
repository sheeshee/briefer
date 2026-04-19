from django.urls import path

from core import views

urlpatterns = [
    path("", views.stack, name="stack"),
    path("history/", views.history, name="history"),
    path("fetch/", views.fetch, name="fetch"),
    path("reset/", views.reset, name="reset"),
    path("items/<int:item_id>/action/", views.item_action, name="item-action"),
]

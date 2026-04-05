from django.urls import path

from core import views

urlpatterns = [
    path("", views.stack, name="stack"),
    path("items/<int:item_id>/action/", views.item_action, name="item-action"),
]

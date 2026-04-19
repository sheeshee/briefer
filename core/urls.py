from django.urls import path

from core import views

urlpatterns = [
    path("", views.stack, name="stack"),
    path("history/", views.history, name="history"),
    path("errors/", views.action_errors, name="action-errors"),
    path("errors/<int:error_id>/", views.action_error_detail, name="action-error-detail"),
    path("fetch/", views.fetch, name="fetch"),
    path("reset/", views.reset, name="reset"),
    path("items/<int:item_id>/action/", views.item_action, name="item-action"),
]

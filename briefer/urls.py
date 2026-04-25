from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(http_method_names=["post"]), name="logout"),
]

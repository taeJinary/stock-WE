from django.urls import include, path

from .views import profile

app_name = "accounts"

urlpatterns = [
    path("profile/", profile, name="profile"),
    path("", include("django.contrib.auth.urls")),
]

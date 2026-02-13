from django.urls import include, path

from .views import profile, signup

app_name = "accounts"

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("", include("django.contrib.auth.urls")),
]

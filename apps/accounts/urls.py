from django.urls import include, path

from .views import logout_redirect_home, profile, signup

app_name = "accounts"

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("logout/", logout_redirect_home, name="logout"),
    path("", include("django.contrib.auth.urls")),
]

from django.urls import path

from .views import watchlist_list

app_name = "watchlist"

urlpatterns = [
    path("", watchlist_list, name="list"),
]

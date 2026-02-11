from django.urls import path

from .views import (
    watchlist_add_item,
    watchlist_create,
    watchlist_delete,
    watchlist_list,
    watchlist_remove_item,
)

app_name = "watchlist"

urlpatterns = [
    path("", watchlist_list, name="list"),
    path("create/", watchlist_create, name="create"),
    path("<int:watchlist_id>/delete/", watchlist_delete, name="delete"),
    path("stocks/<str:symbol>/add/", watchlist_add_item, name="add-item"),
    path("stocks/<str:symbol>/remove/", watchlist_remove_item, name="remove-item"),
]

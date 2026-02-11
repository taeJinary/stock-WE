from django.urls import path

from .views import briefing_list

app_name = "briefing"

urlpatterns = [
    path("", briefing_list, name="list"),
]

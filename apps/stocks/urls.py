from django.urls import path

from .views import stock_detail, stock_list

app_name = "stocks"

urlpatterns = [
    path("", stock_list, name="list"),
    path("<str:symbol>/", stock_detail, name="detail"),
]

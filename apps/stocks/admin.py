from django.contrib import admin

from .models import Interest, NewsItem, Price, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "market", "sector", "is_active")
    search_fields = ("symbol", "name", "sector")
    list_filter = ("market", "is_active")


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("stock", "traded_at", "close_price", "volume")
    list_filter = ("traded_at",)
    search_fields = ("stock__symbol",)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("stock", "source", "recorded_at", "mentions", "sentiment_score")
    list_filter = ("source", "recorded_at")
    search_fields = ("stock__symbol",)


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ("stock", "source", "publisher", "published_at", "created_at")
    list_filter = ("source", "publisher", "published_at")
    search_fields = ("stock__symbol", "title", "publisher")

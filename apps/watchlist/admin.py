from django.contrib import admin

from .models import Watchlist, WatchlistItem


class WatchlistItemInline(admin.TabularInline):
    model = WatchlistItem
    extra = 1


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_default", "updated_at")
    search_fields = ("name", "user__username")
    list_filter = ("is_default",)
    inlines = [WatchlistItemInline]


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("watchlist", "stock", "created_at")
    search_fields = ("watchlist__name", "stock__symbol")

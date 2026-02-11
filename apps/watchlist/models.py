from django.conf import settings
from django.db import models

from apps.stocks.models import Stock


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="watchlists",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=120)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("user", "name")

    def __str__(self):
        return f"{self.user.username} / {self.name}"


class WatchlistItem(models.Model):
    watchlist = models.ForeignKey(
        Watchlist,
        related_name="items",
        on_delete=models.CASCADE,
    )
    stock = models.ForeignKey(
        Stock,
        related_name="watchlist_items",
        on_delete=models.CASCADE,
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("watchlist", "stock")

    def __str__(self):
        return f"{self.watchlist.name} / {self.stock.symbol}"

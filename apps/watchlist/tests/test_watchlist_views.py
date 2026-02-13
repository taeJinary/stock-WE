from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.stocks.models import Stock
from apps.watchlist.models import Watchlist, WatchlistItem


class WatchlistViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="watchlist-user",
            email="watchlist-user@example.com",
            password="pass1234",
        )
        self.stock = Stock.objects.create(
            symbol="WLV1",
            name="Watchlist View One",
            market=Stock.Market.USA,
            sector="Tech",
            is_active=True,
        )

    def test_watchlist_list_requires_login(self):
        response = self.client.get(reverse("watchlist:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_watchlist_create_creates_default_and_falls_back_on_unsafe_next(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("watchlist:create"),
            {"name": "Core", "next": "https://evil.example.com/redirect"},
        )

        self.assertRedirects(response, reverse("watchlist:list"))
        watchlist = Watchlist.objects.get(user=self.user, name="Core")
        self.assertTrue(watchlist.is_default)

    def test_watchlist_create_blocks_when_free_limit_reached(self):
        self.client.force_login(self.user)
        for idx in range(3):
            Watchlist.objects.create(user=self.user, name=f"List {idx}", is_default=(idx == 0))

        response = self.client.post(reverse("watchlist:create"), {"name": "Overflow"})

        self.assertRedirects(response, reverse("watchlist:list"))
        self.assertEqual(Watchlist.objects.filter(user=self.user).count(), 3)
        self.assertFalse(Watchlist.objects.filter(user=self.user, name="Overflow").exists())

    def test_watchlist_add_item_creates_default_watchlist_when_missing(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("watchlist:add-item", kwargs={"symbol": self.stock.symbol}),
            {"note": "focus"},
        )

        self.assertEqual(response.status_code, 302)
        watchlist = Watchlist.objects.get(user=self.user)
        self.assertTrue(watchlist.is_default)
        item = WatchlistItem.objects.get(watchlist=watchlist, stock=self.stock)
        self.assertEqual(item.note, "focus")

    def test_watchlist_add_item_updates_note_for_existing_item(self):
        self.client.force_login(self.user)
        watchlist = Watchlist.objects.create(user=self.user, name="Main", is_default=True)
        item = WatchlistItem.objects.create(watchlist=watchlist, stock=self.stock, note="old note")

        response = self.client.post(
            reverse("watchlist:add-item", kwargs={"symbol": self.stock.symbol}),
            {"watchlist_id": watchlist.id, "note": "new note"},
        )

        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.note, "new note")

    def test_watchlist_delete_reassigns_default_watchlist(self):
        self.client.force_login(self.user)
        default_watchlist = Watchlist.objects.create(user=self.user, name="Default", is_default=True)
        replacement = Watchlist.objects.create(user=self.user, name="Backup", is_default=False)

        response = self.client.post(reverse("watchlist:delete", kwargs={"watchlist_id": default_watchlist.id}))

        self.assertRedirects(response, reverse("watchlist:list"))
        self.assertFalse(Watchlist.objects.filter(id=default_watchlist.id).exists())
        replacement.refresh_from_db()
        self.assertTrue(replacement.is_default)

    def test_watchlist_remove_item_requires_watchlist_id(self):
        self.client.force_login(self.user)
        watchlist = Watchlist.objects.create(user=self.user, name="Main", is_default=True)
        WatchlistItem.objects.create(watchlist=watchlist, stock=self.stock, note="keep")

        response = self.client.post(reverse("watchlist:remove-item", kwargs={"symbol": self.stock.symbol}))

        self.assertRedirects(response, reverse("watchlist:list"))
        self.assertTrue(WatchlistItem.objects.filter(watchlist=watchlist, stock=self.stock).exists())

    def test_watchlist_remove_item_deletes_existing_item(self):
        self.client.force_login(self.user)
        watchlist = Watchlist.objects.create(user=self.user, name="Main", is_default=True)
        WatchlistItem.objects.create(watchlist=watchlist, stock=self.stock, note="remove")

        response = self.client.post(
            reverse("watchlist:remove-item", kwargs={"symbol": self.stock.symbol}),
            {"watchlist_id": watchlist.id},
        )

        self.assertRedirects(response, reverse("watchlist:list"))
        self.assertFalse(WatchlistItem.objects.filter(watchlist=watchlist, stock=self.stock).exists())

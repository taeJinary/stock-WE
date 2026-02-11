from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Subscription
from apps.watchlist.models import Watchlist
from services.watchlist_service import (
    DEFAULT_WATCHLIST_NAME,
    can_user_create_watchlist,
    ensure_default_watchlist,
    get_watchlist_limit,
)


class WatchlistServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="watcher",
            email="watcher@example.com",
            password="pass1234",
        )

    def test_can_user_create_watchlist_respects_free_limit(self):
        for idx in range(3):
            Watchlist.objects.create(user=self.user, name=f"List {idx}")

        can_create, limit = can_user_create_watchlist(self.user)

        self.assertFalse(can_create)
        self.assertEqual(limit, 3)

    def test_get_watchlist_limit_is_unlimited_for_pro(self):
        today = timezone.localdate()
        Subscription.objects.create(
            user=self.user,
            plan=Subscription.Plan.PRO,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            is_active=True,
        )

        limit = get_watchlist_limit(self.user)

        self.assertIsNone(limit)

    def test_ensure_default_watchlist_promotes_first_existing_watchlist(self):
        first = Watchlist.objects.create(user=self.user, name="First", is_default=False)
        Watchlist.objects.create(user=self.user, name="Second", is_default=False)

        resolved = ensure_default_watchlist(self.user)

        first.refresh_from_db()
        self.assertEqual(resolved.id, first.id)
        self.assertTrue(first.is_default)

    def test_ensure_default_watchlist_creates_new_default_when_empty(self):
        resolved = ensure_default_watchlist(self.user)

        self.assertEqual(resolved.name, DEFAULT_WATCHLIST_NAME)
        self.assertTrue(resolved.is_default)

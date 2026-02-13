from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Subscription


class AccountViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="account-viewer",
            email="account-viewer@example.com",
            password="pass1234",
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_profile_includes_active_subscription_in_context(self):
        today = timezone.localdate()
        active_subscription = Subscription.objects.create(
            user=self.user,
            plan=Subscription.Plan.PRO,
            is_active=True,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
        )
        Subscription.objects.create(
            user=self.user,
            plan=Subscription.Plan.FREE,
            is_active=False,
            start_date=today - timedelta(days=60),
            end_date=today - timedelta(days=30),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["subscription"].id, active_subscription.id)

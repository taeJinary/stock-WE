from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.authtoken.models import Token

from apps.accounts.models import Subscription


class BootstrapLoadtestCommandTests(TestCase):
    @patch("apps.accounts.management.commands.bootstrap_loadtest.ensure_index_stocks")
    def test_command_creates_user_subscription_and_token(self, mock_seed):
        mock_seed.return_value = []
        out = StringIO()

        call_command(
            "bootstrap_loadtest",
            "--username",
            "load-user",
            "--password",
            "pass1234",
            "--email",
            "load-user@example.com",
            "--plan",
            Subscription.Plan.PRO,
            "--create-token",
            stdout=out,
        )

        User = get_user_model()
        user = User.objects.get(username="load-user")
        self.assertTrue(user.check_password("pass1234"))
        self.assertEqual(user.email, "load-user@example.com")
        self.assertTrue(
            Subscription.objects.filter(
                user=user,
                plan=Subscription.Plan.PRO,
                is_active=True,
            ).exists()
        )
        self.assertEqual(Token.objects.filter(user=user).count(), 1)
        mock_seed.assert_called_once()

    @patch("apps.accounts.management.commands.bootstrap_loadtest.ensure_index_stocks")
    def test_command_deactivates_existing_subscription_and_skips_seed(self, mock_seed):
        User = get_user_model()
        user = User.objects.create_user(
            username="existing-user",
            email="old@example.com",
            password="oldpass",
        )
        old_subscription = Subscription.objects.create(
            user=user,
            plan=Subscription.Plan.FREE,
            is_active=True,
        )
        out = StringIO()

        call_command(
            "bootstrap_loadtest",
            "--username",
            "existing-user",
            "--password",
            "newpass1234",
            "--plan",
            Subscription.Plan.ENTERPRISE,
            "--no-seed-indexes",
            stdout=out,
        )

        old_subscription.refresh_from_db()
        self.assertFalse(old_subscription.is_active)
        self.assertTrue(
            Subscription.objects.filter(
                user=user,
                plan=Subscription.Plan.ENTERPRISE,
                is_active=True,
            ).exists()
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpass1234"))
        mock_seed.assert_not_called()

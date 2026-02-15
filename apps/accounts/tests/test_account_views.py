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

    def test_signup_get_renders_form_for_anonymous_user(self):
        response = self.client.get(reverse("accounts:signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "회원가입")

    def test_signup_redirects_authenticated_user_to_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:signup"))

        self.assertRedirects(response, reverse("dashboard:home"))

    def test_signup_post_creates_user_login_and_free_subscription(self):
        response = self.client.post(
            reverse("accounts:signup"),
            data={
                "username": "new-user",
                "email": "new-user@example.com",
                "password1": "strong-pass-123!",
                "password2": "strong-pass-123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard:home"))

        created_user = get_user_model().objects.get(username="new-user")
        self.assertEqual(created_user.email, "new-user@example.com")
        self.assertTrue(created_user.subscriptions.exists())
        self.assertEqual(
            created_user.subscriptions.first().plan,
            Subscription.Plan.FREE,
        )

        profile_response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.context["user"].id, created_user.id)

    def test_signup_rejects_duplicate_email(self):
        response = self.client.post(
            reverse("accounts:signup"),
            data={
                "username": "other-user",
                "email": "account-viewer@example.com",
                "password1": "strong-pass-123!",
                "password2": "strong-pass-123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이미 사용 중인 이메일입니다.")

    def test_logout_get_redirects_home_and_logs_user_out(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("dashboard:home"))
        profile_response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(profile_response.status_code, 302)
        self.assertIn(reverse("accounts:login"), profile_response.url)

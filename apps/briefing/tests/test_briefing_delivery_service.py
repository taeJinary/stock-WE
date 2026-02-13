from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Subscription
from apps.briefing.models import DailyBriefing
from services.briefing_delivery_service import send_daily_briefing_email


class BriefingDeliveryServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.briefing = DailyBriefing.objects.create(
            briefing_date=self.today,
            title="Daily Briefing",
            summary="Summary text",
            discussed_symbols=["AAPL", "NVDA"],
        )

    def _create_active_subscriber(self, username, email):
        user = get_user_model().objects.create_user(
            username=username,
            email=email,
            password="pass1234",
        )
        Subscription.objects.create(
            user=user,
            plan=Subscription.Plan.FREE,
            is_active=True,
            start_date=self.today - timedelta(days=1),
            end_date=self.today + timedelta(days=30),
        )
        return user

    @patch("services.briefing_delivery_service._send_briefing_messages", return_value=(1, []))
    def test_send_daily_briefing_email_marks_sent_status(self, mock_send_messages):
        self._create_active_subscriber("user1", "user1@example.com")

        result = send_daily_briefing_email(briefing_date=self.today)
        self.briefing.refresh_from_db()

        mock_send_messages.assert_called_once()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["target_count"], 1)
        self.assertEqual(self.briefing.email_status, DailyBriefing.EmailStatus.SENT)
        self.assertEqual(self.briefing.email_sent_count, 1)
        self.assertEqual(self.briefing.email_target_count, 1)
        self.assertIsNotNone(self.briefing.email_sent_at)

    def test_send_daily_briefing_email_skips_when_no_active_recipients(self):
        result = send_daily_briefing_email(briefing_date=self.today)
        self.briefing.refresh_from_db()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "NO_ACTIVE_RECIPIENTS")
        self.assertEqual(result["sent_count"], 0)
        self.assertEqual(result["target_count"], 0)
        self.assertEqual(self.briefing.email_status, DailyBriefing.EmailStatus.SKIPPED)
        self.assertEqual(self.briefing.email_failure_reason, "NO_ACTIVE_RECIPIENTS")

    @patch(
        "services.briefing_delivery_service._send_briefing_messages",
        return_value=(1, [{"email": "fail@example.com", "error": "smtp failure"}]),
    )
    def test_send_daily_briefing_email_marks_partial_when_some_fail(self, mock_send_messages):
        self._create_active_subscriber("ok-user", "ok@example.com")
        self._create_active_subscriber("fail-user", "fail@example.com")

        result = send_daily_briefing_email(briefing_date=self.today)
        self.briefing.refresh_from_db()

        mock_send_messages.assert_called_once()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["target_count"], 2)
        self.assertEqual(result["email_status"], DailyBriefing.EmailStatus.PARTIAL)
        self.assertEqual(self.briefing.email_status, DailyBriefing.EmailStatus.PARTIAL)
        self.assertEqual(self.briefing.email_sent_count, 1)
        self.assertEqual(self.briefing.email_target_count, 2)
        self.assertIn("fail@example.com", self.briefing.email_failure_reason)

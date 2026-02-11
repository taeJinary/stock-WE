from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.briefing.models import DailyBriefing


class BriefingViewsTests(TestCase):
    def test_briefing_list_returns_latest_rows(self):
        for idx in range(3):
            DailyBriefing.objects.create(
                briefing_date=timezone.localdate() - timedelta(days=idx),
                title=f"Briefing {idx}",
                summary="Summary",
                discussed_symbols=["AAPL"],
            )

        response = self.client.get(reverse("briefing:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["briefings"]), 3)
